#!/usr/bin/env python3
"""
Ethereum Storage Slot Sharing Analyzer

For each block, counts SLOAD/SSTORE operations on each (contract, slot)
pair and CALL-family invocations on each contract — reads OR writes,
no distinction needed. Also reports the same counts per transaction.

Uses the structLogger (default debug tracer) which captures every
SLOAD and SSTORE opcode. The slot key is always stack[-1] at that point.

Contract attribution follows EVM storage semantics:
  - Entry point: tx.to (fetched via eth_getBlockByNumber)
  - CALL / STATICCALL: new frame's storage is the callee
  - DELEGATECALL / CALLCODE: storage inherits from the caller
  - CREATE / CREATE2: synthetic per-frame placeholder
    (exact address computation skipped)

Requirements:
    pip install requests tqdm matplotlib

Node requirements:
    - debug_traceBlockByNumber must be enabled
    - Archive node for historical blocks
    - Alchemy/QuickNode work on paid plans; self-hosted Geth/Erigon ideal

Usage:
    # Single block
    python slot_sharing.py --rpc <url> --block 22000000

    # 10 recent blocks
    python slot_sharing.py --rpc <url> --blocks 10

    # Range
    python slot_sharing.py --rpc <url> --start 22000000 --count 20
"""

import argparse
import json
import sys
from collections import defaultdict

import requests

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None


# ── RPC ──────────────────────────────────────────────────────────────────────

def rpc(url: str, method: str, params: list, timeout: int = 300) -> object:
    resp = requests.post(
        url,
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
        headers={"Content-Type": "application/json"},
        timeout=timeout,
    )
    resp.raise_for_status()
    body = resp.json()
    if "error" in body:
        raise RuntimeError(f"RPC error {body['error']['code']}: {body['error']['message']}")
    return body["result"]


def latest_block(url: str) -> int:
    return int(rpc(url, "eth_blockNumber", []), 16)


# ── core analysis ─────────────────────────────────────────────────────────────

# For CALL / STATICCALL, the new frame operates on the callee's own storage.
# For DELEGATECALL / CALLCODE, the callee's code runs in the CALLER's storage.
CALL_OPS_OWN_STORAGE = {"CALL", "STATICCALL"}
CALL_OPS_INHERIT_STORAGE = {"DELEGATECALL", "CALLCODE"}
CREATE_OPS = {"CREATE", "CREATE2"}

# Precompile addresses — pre-warmed since EIP-2929 (Berlin) / EIP-4844 (Cancun).
# Calls to these always pay the warm cost, so they're excluded from account
# distributions that measure warming opportunity.
PRECOMPILES = {"0x" + f"{i:040x}" for i in range(1, 0x0b)}  # 0x01..0x0a


def normalize_addr(raw: str) -> str:
    """Normalize a hex string (as pulled from the stack) to a 20-byte 0x address."""
    h = raw.lower()
    if h.startswith("0x"):
        h = h[2:]
    if len(h) < 40:
        h = h.zfill(40)
    else:
        h = h[-40:]
    return "0x" + h


def analyze_block(url: str, block_num: int) -> dict:
    """
    Trace every transaction in a block and collect all SLOAD/SSTORE accesses.

    Returns a dict with slot sharing statistics and the raw N(s,B) distribution.
    """

    # Fetch the block's transaction list so we know each tx's entry-point `to`.
    block_data = rpc(url, "eth_getBlockByNumber", [hex(block_num), True])
    tx_entry_addrs = []
    for i, tx in enumerate(block_data.get("transactions", [])):
        to = tx.get("to")
        tx_entry_addrs.append(to.lower() if to else f"0xcreate_tx{i}")

    # Trace the full block. disableMemory/disableReturnData keep response smaller.
    # We need the stack (for slot key at SLOAD/SSTORE and callee addr at CALLs).
    traces = rpc(
        url,
        "debug_traceBlockByNumber",
        [
            hex(block_num),
            {
                "disableMemory": True,
                "disableReturnData": True,
                "disableStack": False,
            },
        ],
        timeout=600,
    )

    # Per-block op counts
    # slot_ops: (contract, slot_hex) -> total SLOAD+SSTORE ops in the block
    slot_ops: dict = defaultdict(int)
    # account_calls: contract address -> total calls in the block
    # (entry point + every CALL/STATICCALL/DELEGATECALL/CALLCODE)
    account_calls: dict = defaultdict(int)

    # Per-tx op counts
    # tx_slot_access: (tx_idx, contract, slot_hex) -> SLOAD/SSTORE ops in that tx
    tx_slot_access: dict = defaultdict(int)
    # tx_account_call: (tx_idx, contract) -> calls (entry + CALL-family) in that tx
    tx_account_call: dict = defaultdict(int)

    for tx_idx, tx_trace in enumerate(traces):
        result = tx_trace.get("result", tx_trace)
        struct_logs = result.get("structLogs", [])

        entry = tx_entry_addrs[tx_idx] if tx_idx < len(tx_entry_addrs) else "unknown"
        storage_stack = [entry]  # storage_stack[d-1] = storage context at depth d
        if entry not in PRECOMPILES:
            account_calls[entry] += 1
            tx_account_call[(tx_idx, entry)] += 1  # entry-point counts as 1 call

        prev_op = None
        prev_stack = None
        prev_depth = 1
        create_counter = 0

        for step in struct_logs:
            op = step.get("op", "")
            depth = step.get("depth", 1)
            stack = step.get("stack", [])

            # Record the target of any CALL-family opcode as a called account.
            # Precompiles are excluded — they're pre-warmed by the protocol.
            if op in CALL_OPS_OWN_STORAGE or op in CALL_OPS_INHERIT_STORAGE:
                if len(stack) >= 2:
                    target = normalize_addr(stack[-2])
                    if target not in PRECOMPILES:
                        account_calls[target] += 1
                        tx_account_call[(tx_idx, target)] += 1

            # A frame was just entered — push the appropriate storage context
            # based on what opcode caused the entry.
            if depth > prev_depth:
                if prev_op in CALL_OPS_OWN_STORAGE and prev_stack and len(prev_stack) >= 2:
                    storage_stack.append(normalize_addr(prev_stack[-2]))
                elif prev_op in CALL_OPS_INHERIT_STORAGE:
                    storage_stack.append(storage_stack[-1])
                elif prev_op in CREATE_OPS:
                    create_counter += 1
                    storage_stack.append(f"0xcreate_tx{tx_idx}_{create_counter}")
                else:
                    # Shouldn't normally happen; fall back to parent's context.
                    storage_stack.append(storage_stack[-1])
            elif depth < prev_depth:
                while len(storage_stack) > depth:
                    storage_stack.pop()

            if op in ("SLOAD", "SSTORE") and stack:
                # slot key is always stack[-1] (top of stack) at SLOAD/SSTORE
                raw_slot = stack[-1]
                # normalize to 32-byte hex without 0x prefix
                slot_hex = raw_slot.lstrip("0x").zfill(64).lower()

                contract = storage_stack[-1] if storage_stack else "unknown"
                slot_ops[(contract, slot_hex)] += 1
                tx_slot_access[(tx_idx, contract, slot_hex)] += 1

            prev_op = op
            prev_stack = stack
            prev_depth = depth

    # ── compute statistics ────────────────────────────────────────────────────

    n_txs = len(traces)
    total_unique_slots = len(slot_ops)

    # N(s,B) distribution: how many SLOAD/SSTORE ops hit each (contract, slot) in the block
    n_distribution: dict = defaultdict(int)
    for cnt in slot_ops.values():
        n_distribution[cnt] += 1

    multi_access_slots = sum(1 for cnt in slot_ops.values() if cnt > 1)

    # Top (contract, slot) pairs by op count
    top_shared = sorted(
        [(key, cnt) for key, cnt in slot_ops.items() if cnt > 1],
        key=lambda x: x[1],
        reverse=True,
    )[:15]

    # N(c,B) distribution for accounts
    total_unique_accounts = len(account_calls)
    account_n_distribution: dict = defaultdict(int)
    for cnt in account_calls.values():
        account_n_distribution[cnt] += 1

    multi_call_accounts = sum(1 for cnt in account_calls.values() if cnt > 1)

    top_shared_accounts = sorted(
        [(addr, cnt) for addr, cnt in account_calls.items() if cnt > 1],
        key=lambda x: x[1],
        reverse=True,
    )[:15]

    # Per-tx N(s,T) distribution: how many SLOAD/SSTORE a tx did on a given slot
    tx_slot_distribution: dict = defaultdict(int)
    for cnt in tx_slot_access.values():
        tx_slot_distribution[cnt] += 1

    # Per-tx N(c,T) distribution: how many times a tx called a given contract
    tx_account_distribution: dict = defaultdict(int)
    for cnt in tx_account_call.values():
        tx_account_distribution[cnt] += 1

    return {
        "block": block_num,
        "total_txs": n_txs,
        "total_unique_slots": total_unique_slots,
        "multi_access_slots": multi_access_slots,
        "multi_access_rate": multi_access_slots / total_unique_slots if total_unique_slots else 0,
        "n_distribution": dict(sorted(n_distribution.items())),
        "top_shared_slots": [
            {"contract": key[0], "slot": key[1], "n_ops": n}
            for key, n in top_shared
        ],
        "total_unique_accounts": total_unique_accounts,
        "multi_call_accounts": multi_call_accounts,
        "multi_call_rate": multi_call_accounts / total_unique_accounts if total_unique_accounts else 0,
        "account_n_distribution": dict(sorted(account_n_distribution.items())),
        "top_shared_accounts": [
            {"account": addr, "n_calls": n}
            for addr, n in top_shared_accounts
        ],
        "tx_slot_distribution": dict(sorted(tx_slot_distribution.items())),
        "tx_account_distribution": dict(sorted(tx_account_distribution.items())),
        "total_tx_slot_entries": sum(tx_slot_distribution.values()),
        "total_tx_account_entries": sum(tx_account_distribution.values()),
    }


# ── reporting ─────────────────────────────────────────────────────────────────

def print_result(r: dict):
    print(f"\n{'═'*58}")
    print(f"  Block {r['block']}")
    print(f"{'═'*58}")
    print(f"  Transactions            : {r['total_txs']:>8,}")
    print(f"  Unique (contract,slot)  : {r['total_unique_slots']:>8,}")
    print(f"  Multi-access slots (N≥2): {r['multi_access_slots']:>8,}")
    print(f"  Multi-access rate       : {r['multi_access_rate']:>8.1%}")
    print(f"  Unique accounts called  : {r['total_unique_accounts']:>8,}")
    print(f"  Multi-call accounts(N≥2): {r['multi_call_accounts']:>8,}")
    print(f"  Multi-call rate         : {r['multi_call_rate']:>8.1%}")

    print(f"\n  N(s,B) distribution (SLOAD+SSTORE ops per (contract,slot) in block)")
    print(f"  {'N':>4}  {'slots':>8}  {'% of total':>10}  histogram")
    print(f"  {'─'*4}  {'─'*8}  {'─'*10}  {'─'*30}")
    total = r['total_unique_slots']
    for n, count in sorted(r['n_distribution'].items()):
        pct = count / total if total else 0
        bar = '▓' * int(pct * 60)
        print(f"  {n:>4}  {count:>8,}  {pct:>9.1%}  {bar}")

    print(f"\n  N(c,B) distribution (calls per account in block)")
    print(f"  {'N':>4}  {'accts':>8}  {'% of total':>10}  histogram")
    print(f"  {'─'*4}  {'─'*8}  {'─'*10}  {'─'*30}")
    total_a = r['total_unique_accounts']
    for n, count in sorted(r['account_n_distribution'].items()):
        pct = count / total_a if total_a else 0
        bar = '▓' * int(pct * 60)
        print(f"  {n:>4}  {count:>8,}  {pct:>9.1%}  {bar}")

    print(f"\n  Top (contract, slot) pairs by ops")
    print(f"  {'Contract':<42}  {'Slot prefix':<14}  N")
    print(f"  {'─'*42}  {'─'*14}  {'─'*4}")
    for s in r['top_shared_slots']:
        print(f"  {s['contract']:<42}  {s['slot'][:12]}…  {s['n_ops']}")

    print(f"\n  Top accounts by calls")
    print(f"  {'Account':<42}  N")
    print(f"  {'─'*42}  {'─'*4}")
    for a in r['top_shared_accounts']:
        print(f"  {a['account']:<42}  {a['n_calls']}")

    print(f"\n  N(s,T) distribution (per-tx slot accesses)")
    print(f"  {'N':>4}  {'(tx,slot)':>10}  {'% of total':>10}  histogram")
    print(f"  {'─'*4}  {'─'*10}  {'─'*10}  {'─'*30}")
    total_st = r['total_tx_slot_entries']
    for n, count in sorted(r['tx_slot_distribution'].items()):
        pct = count / total_st if total_st else 0
        bar = '▓' * int(pct * 60)
        print(f"  {n:>4}  {count:>10,}  {pct:>9.1%}  {bar}")

    print(f"\n  N(c,T) distribution (per-tx account calls)")
    print(f"  {'N':>4}  {'(tx,acct)':>10}  {'% of total':>10}  histogram")
    print(f"  {'─'*4}  {'─'*10}  {'─'*10}  {'─'*30}")
    total_ct = r['total_tx_account_entries']
    for n, count in sorted(r['tx_account_distribution'].items()):
        pct = count / total_ct if total_ct else 0
        bar = '▓' * int(pct * 60)
        print(f"  {n:>4}  {count:>10,}  {pct:>9.1%}  {bar}")


def print_summary(results: list):
    if len(results) < 2:
        return
    n = len(results)
    print(f"\n{'═'*58}")
    print(f"  Summary across {n} blocks")
    print(f"{'═'*58}")

    def avg(key):
        return sum(r[key] for r in results) / n

    print(f"  Avg transactions/block  : {avg('total_txs'):>8.1f}")
    print(f"  Avg unique slots/block  : {avg('total_unique_slots'):>8.1f}")
    print(f"  Avg multi-access slots  : {avg('multi_access_slots'):>8.1f}")
    print(f"  Avg multi-access rate   : {avg('multi_access_rate'):>8.1%}")
    print(f"  Avg unique accounts     : {avg('total_unique_accounts'):>8.1f}")
    print(f"  Avg multi-call accounts : {avg('multi_call_accounts'):>8.1f}")
    print(f"  Avg multi-call rate     : {avg('multi_call_rate'):>8.1%}")

    # Aggregate N distributions
    agg: dict = defaultdict(int)
    for r in results:
        for n_val, count in r['n_distribution'].items():
            agg[n_val] += count

    print(f"\n  Aggregated N(s,B) distribution across all blocks")
    total_agg = sum(agg.values())
    print(f"  {'N':>4}  {'slots':>10}  {'%':>8}")
    for n_val in sorted(agg):
        pct = agg[n_val] / total_agg
        print(f"  {n_val:>4}  {agg[n_val]:>10,}  {pct:>7.2%}")

    agg_acc: dict = defaultdict(int)
    for r in results:
        for n_val, count in r['account_n_distribution'].items():
            agg_acc[n_val] += count

    print(f"\n  Aggregated N(c,B) distribution across all blocks")
    total_agg_acc = sum(agg_acc.values())
    print(f"  {'N':>4}  {'accts':>10}  {'%':>8}")
    for n_val in sorted(agg_acc):
        pct = agg_acc[n_val] / total_agg_acc
        print(f"  {n_val:>4}  {agg_acc[n_val]:>10,}  {pct:>7.2%}")

    agg_st: dict = defaultdict(int)
    for r in results:
        for n_val, count in r['tx_slot_distribution'].items():
            agg_st[n_val] += count

    print(f"\n  Aggregated N(s,T) distribution (per-tx slot accesses)")
    total_agg_st = sum(agg_st.values())
    print(f"  {'N':>4}  {'(tx,slot)':>10}  {'%':>8}")
    for n_val in sorted(agg_st):
        pct = agg_st[n_val] / total_agg_st
        print(f"  {n_val:>4}  {agg_st[n_val]:>10,}  {pct:>7.2%}")

    agg_ct: dict = defaultdict(int)
    for r in results:
        for n_val, count in r['tx_account_distribution'].items():
            agg_ct[n_val] += count

    print(f"\n  Aggregated N(c,T) distribution (per-tx account calls)")
    total_agg_ct = sum(agg_ct.values())
    print(f"  {'N':>4}  {'(tx,acct)':>10}  {'%':>8}")
    for n_val in sorted(agg_ct):
        pct = agg_ct[n_val] / total_agg_ct
        print(f"  {n_val:>4}  {agg_ct[n_val]:>10,}  {pct:>7.2%}")


# ── HTML report ───────────────────────────────────────────────────────────────

def _agg_distribution(results: list, key: str) -> dict:
    agg: dict = defaultdict(int)
    for r in results:
        for n_val, count in r[key].items():
            agg[int(n_val)] += count
    return dict(sorted(agg.items()))


def _distribution_stats(d: dict) -> dict:
    """Summary stats over a histogram dict {N: count}."""
    if not d:
        return {"total": 0, "mean": 0.0, "p50": 0, "p95": 0, "p99": 0,
                "max": 0, "n1_pct": 0.0, "shared_pct": 0.0}
    total = sum(d.values())
    weighted = sum(int(n) * c for n, c in d.items())
    mean = weighted / total if total else 0.0
    cum = 0
    p = {0.50: None, 0.95: None, 0.99: None}
    for k in sorted(d.keys()):
        cum += d[k]
        for pct in p:
            if p[pct] is None and cum / total >= pct:
                p[pct] = k
    n1 = d.get(1, 0)
    shared = sum(c for n, c in d.items() if int(n) >= 2)
    return {
        "total": total,
        "mean": mean,
        "p50": p[0.50] if p[0.50] is not None else 0,
        "p95": p[0.95] if p[0.95] is not None else 0,
        "p99": p[0.99] if p[0.99] is not None else 0,
        "max": max(int(k) for k in d.keys()),
        "n1_pct": n1 / total if total else 0.0,
        "shared_pct": shared / total if total else 0.0,
    }


def _chart_png(distribution: dict, title: str, xlabel: str, ylabel: str,
               max_bins: int = 60) -> str:
    """Render a distribution as a base64-encoded PNG bar chart (log y)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from io import BytesIO
    import base64

    fig, ax = plt.subplots(figsize=(10, 4.5))
    if distribution:
        items = sorted(distribution.items(), key=lambda x: int(x[0]))
        # Collapse a long tail into a final "N≥cap" bar to keep things readable.
        if len(items) > max_bins:
            head = items[:max_bins - 1]
            tail_sum = sum(c for _, c in items[max_bins - 1:])
            cap = int(items[max_bins - 1][0])
            xs = [str(int(n)) for n, _ in head] + [f"≥{cap}"]
            ys = [c for _, c in head] + [tail_sum]
        else:
            xs = [str(int(n)) for n, _ in items]
            ys = [c for _, c in items]
        ax.bar(xs, ys, color="#4a7cbf", edgecolor="#1a3a5a", linewidth=0.5)
        if max(ys) > 0 and max(ys) / max(1, min(y for y in ys if y > 0)) > 20:
            ax.set_yscale("log")
        # Keep x labels readable
        if len(xs) > 25:
            for label in ax.get_xticklabels():
                label.set_rotation(60)
                label.set_fontsize(8)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=110)
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _fmt_int(n) -> str:
    return f"{int(n):,}"


def write_html_report(results: list, output_path: str):
    if not results:
        print("No results to report.", file=sys.stderr)
        return

    distributions = [
        ("N(s,B)", "Per-block slot accesses",
         "Total SLOAD/SSTORE ops on each (contract, slot) within a block "
         "(summed across all transactions).",
         "n_distribution", "ops on a slot in the block", "(contract, slot) pairs"),
        ("N(c,B)", "Per-block account calls",
         "Total calls to each contract within a block (entry points + CALL-family ops, "
         "summed across all transactions).",
         "account_n_distribution", "calls to an account in the block", "contracts"),
        ("N(s,T)", "Per-tx slot accesses",
         "Number of SLOAD/SSTORE ops a single transaction performs on a given slot.",
         "tx_slot_distribution", "ops within a tx", "(tx, contract, slot) triples"),
        ("N(c,T)", "Per-tx account calls",
         "Number of times a single transaction calls a given contract (entry + CALL-family).",
         "tx_account_distribution", "calls within a tx", "(tx, contract) pairs"),
    ]

    # Aggregate across blocks
    agg_data = {}
    for short, _, _, key, _, _ in distributions:
        agg_data[short] = _agg_distribution(results, key)

    n_blocks = len(results)
    block_min = min(r["block"] for r in results)
    block_max = max(r["block"] for r in results)
    total_txs = sum(r["total_txs"] for r in results)

    # Aggregate top shared slots/accounts across the window
    slot_totals: dict = defaultdict(int)
    for r in results:
        for s in r["top_shared_slots"]:
            slot_totals[(s["contract"], s["slot"])] += s["n_ops"]
    top_slots_window = sorted(slot_totals.items(), key=lambda x: x[1], reverse=True)[:20]

    acct_totals: dict = defaultdict(int)
    for r in results:
        for a in r["top_shared_accounts"]:
            acct_totals[a["account"]] += a["n_calls"]
    top_accts_window = sorted(acct_totals.items(), key=lambda x: x[1], reverse=True)[:20]

    # Build sections
    sections_html = []
    for short, title, desc, key, xlabel, unit in distributions:
        d = agg_data[short]
        stats = _distribution_stats(d)
        png = _chart_png(d, f"{short} — {title}", xlabel, f"count of {unit}")
        sections_html.append(f"""
        <section class="dist">
          <h2>{short} — {title}</h2>
          <p class="desc">{desc}</p>
          <div class="stats">
            <div><span class="label">Total</span><span class="val">{_fmt_int(stats['total'])}</span></div>
            <div><span class="label">Mean N</span><span class="val">{stats['mean']:.2f}</span></div>
            <div><span class="label">Median N</span><span class="val">{stats['p50']}</span></div>
            <div><span class="label">p95 N</span><span class="val">{stats['p95']}</span></div>
            <div><span class="label">p99 N</span><span class="val">{stats['p99']}</span></div>
            <div><span class="label">Max N</span><span class="val">{_fmt_int(stats['max'])}</span></div>
            <div><span class="label">N=1 share</span><span class="val">{stats['n1_pct']:.1%}</span></div>
            <div><span class="label">N≥2 share</span><span class="val">{stats['shared_pct']:.1%}</span></div>
          </div>
          <img alt="{short} chart" src="data:image/png;base64,{png}"/>
        </section>
        """)

    top_slots_rows = "".join(
        f"<tr><td class='addr'>{c}</td><td class='slot'>0x{s}</td><td class='num'>{_fmt_int(n)}</td></tr>"
        for (c, s), n in top_slots_window
    ) or "<tr><td colspan='3'>No shared slots</td></tr>"

    top_accts_rows = "".join(
        f"<tr><td class='addr'>{a}</td><td class='num'>{_fmt_int(n)}</td></tr>"
        for a, n in top_accts_window
    ) or "<tr><td colspan='2'>No shared accounts</td></tr>"

    per_block_rows = "".join(
        f"<tr><td class='num'>{r['block']}</td>"
        f"<td class='num'>{_fmt_int(r['total_txs'])}</td>"
        f"<td class='num'>{_fmt_int(r['total_unique_slots'])}</td>"
        f"<td class='num'>{_fmt_int(r['multi_access_slots'])}</td>"
        f"<td class='num'>{r['multi_access_rate']:.1%}</td>"
        f"<td class='num'>{_fmt_int(r['total_unique_accounts'])}</td>"
        f"<td class='num'>{_fmt_int(r['multi_call_accounts'])}</td>"
        f"<td class='num'>{r['multi_call_rate']:.1%}</td></tr>"
        for r in results
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>Slot Sharing Analysis — blocks {block_min}–{block_max}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         max-width: 1100px; margin: 2rem auto; padding: 0 1.5rem; color: #222; }}
  h1 {{ border-bottom: 2px solid #1a3a5a; padding-bottom: .3em; }}
  h2 {{ color: #1a3a5a; margin-top: 2.2rem; }}
  .meta {{ color: #666; font-size: .95em; margin-bottom: 2rem; }}
  .meta span {{ margin-right: 1.2em; }}
  .desc {{ color: #555; font-style: italic; }}
  .dist img {{ max-width: 100%; border: 1px solid #ddd; border-radius: 4px; }}
  .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: .5rem; margin: 1rem 0; }}
  .stats div {{ background: #f3f5f8; border-radius: 4px; padding: .5rem .7rem; }}
  .stats .label {{ display: block; color: #666; font-size: .78em; text-transform: uppercase;
                   letter-spacing: .04em; }}
  .stats .val {{ display: block; font-weight: 600; font-size: 1.1em; color: #1a3a5a; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; font-size: .92em; }}
  th, td {{ border-bottom: 1px solid #e4e6eb; padding: .4rem .6rem; text-align: left; }}
  th {{ background: #f3f5f8; font-weight: 600; }}
  td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  td.addr, td.slot {{ font-family: ui-monospace, Menlo, Consolas, monospace;
                      font-size: .85em; }}
  details {{ margin-top: 1.5rem; }}
  summary {{ cursor: pointer; font-weight: 600; color: #1a3a5a; padding: .4rem 0; }}
  @media print {{ details[open] summary {{ page-break-after: avoid; }} }}
</style>
</head>
<body>
  <h1>Storage Slot & Account Sharing Report</h1>
  <div class="meta">
    <span><b>Blocks:</b> {block_min} – {block_max}</span>
    <span><b>Block count:</b> {n_blocks}</span>
    <span><b>Total txs:</b> {_fmt_int(total_txs)}</span>
  </div>

  {''.join(sections_html)}

  <h2>Top (contract, slot) pairs by ops — window total</h2>
  <table>
    <thead><tr><th>Contract</th><th>Slot</th><th>Σ ops (top-15 per block)</th></tr></thead>
    <tbody>{top_slots_rows}</tbody>
  </table>

  <h2>Top accounts by calls — window total</h2>
  <table>
    <thead><tr><th>Account</th><th>Σ calls (top-15 per block)</th></tr></thead>
    <tbody>{top_accts_rows}</tbody>
  </table>

  <details>
    <summary>Per-block breakdown ({n_blocks} blocks)</summary>
    <table>
      <thead><tr>
        <th>Block</th><th>Txs</th>
        <th>Uniq slots</th><th>N≥2 slots</th><th>N≥2 rate</th>
        <th>Uniq accts</th><th>N≥2 accts</th><th>N≥2 rate</th>
      </tr></thead>
      <tbody>{per_block_rows}</tbody>
    </table>
  </details>

  <p class="meta" style="margin-top:2rem;">
    To save as PDF, open this file in a browser and use File → Print → Save as PDF.
  </p>
</body>
</html>"""

    with open(output_path, "w") as f:
        f.write(html)
    print(f"\nHTML report written to {output_path}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--rpc", required=True, help="Node RPC URL")
    p.add_argument("--block", type=int, help="Single block to analyze")
    p.add_argument("--blocks", type=int, default=1,
                   help="Number of recent blocks (default: 1)")
    p.add_argument("--start", type=int, help="Start block for a range")
    p.add_argument("--count", type=int, default=10,
                   help="Number of blocks when using --start")
    p.add_argument("--json-out", help="Write full JSON results to file")
    p.add_argument("--html-out",
                   help="Write HTML report with charts (print to PDF from browser)")
    args = p.parse_args()

    # Determine block list
    if args.block:
        blocks = [args.block]
    elif args.start:
        blocks = list(range(args.start, args.start + args.count))
    else:
        tip = latest_block(args.rpc)
        blocks = list(range(tip - args.blocks - 2, tip - 2))

    print(f"Analyzing blocks {blocks[0]} → {blocks[-1]}  ({len(blocks)} total)")
    print("Tracer: structLogger  |  ops: SLOAD + SSTORE\n")
    print("Note: large blocks can produce 50–200 MB responses.")
    print("If you hit timeouts, use a self-hosted node or a smaller block range.\n")

    results = []
    iterator = tqdm(blocks, desc="blocks") if tqdm else blocks

    for bn in iterator:
        try:
            r = analyze_block(args.rpc, bn)
            results.append(r)
            print_result(r)
        except Exception as e:
            print(f"\n  Block {bn}: FAILED — {e}", file=sys.stderr)

    print_summary(results)

    if args.json_out:
        with open(args.json_out, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nFull results written to {args.json_out}")

    if args.html_out:
        write_html_report(results, args.html_out)


if __name__ == "__main__":
    main()