"""Reduce BlockCounts to summary dicts and compute distribution statistics."""

from collections import defaultdict

from .trace_processor import BlockCounts


def summarize_block(counts: BlockCounts) -> dict:
    """Produce a summary dict from BlockCounts.

    This is the backward-compatibility layer — the dict has the same shape
    as the old analyze_block() return value, so existing report functions
    (print_result, print_summary, write_html_report) work unchanged.
    """
    total_unique_slots = len(counts.slot_ops)

    n_distribution: dict = defaultdict(int)
    for access in counts.slot_ops.values():
        n_distribution[access.total] += 1

    multi_access_slots = sum(1 for a in counts.slot_ops.values() if a.total > 1)

    top_shared = sorted(
        [(k, a.total) for k, a in counts.slot_ops.items() if a.total > 1],
        key=lambda x: x[1],
        reverse=True,
    )[:15]

    total_unique_accounts = len(counts.account_calls)

    account_n_distribution: dict = defaultdict(int)
    for cnt in counts.account_calls.values():
        account_n_distribution[cnt] += 1

    multi_call_accounts = sum(1 for c in counts.account_calls.values() if c > 1)

    top_shared_accounts = sorted(
        [(a, c) for a, c in counts.account_calls.items() if c > 1],
        key=lambda x: x[1],
        reverse=True,
    )[:15]

    tx_slot_distribution: dict = defaultdict(int)
    for access in counts.tx_slot_access.values():
        tx_slot_distribution[access.total] += 1

    tx_account_distribution: dict = defaultdict(int)
    for cnt in counts.tx_account_call.values():
        tx_account_distribution[cnt] += 1

    return {
        "block": counts.block_num,
        "total_txs": counts.n_txs,
        "total_unique_slots": total_unique_slots,
        "multi_access_slots": multi_access_slots,
        "multi_access_rate": multi_access_slots / total_unique_slots if total_unique_slots else 0,
        "n_distribution": dict(sorted(n_distribution.items())),
        "top_shared_slots": [
            {"address": k[0], "slot": k[1], "n_ops": n} for k, n in top_shared
        ],
        "total_unique_accounts": total_unique_accounts,
        "multi_call_accounts": multi_call_accounts,
        "multi_call_rate": multi_call_accounts / total_unique_accounts if total_unique_accounts else 0,
        "account_n_distribution": dict(sorted(account_n_distribution.items())),
        "top_shared_accounts": [
            {"address": a, "n_calls": n} for a, n in top_shared_accounts
        ],
        "tx_slot_distribution": dict(sorted(tx_slot_distribution.items())),
        "tx_account_distribution": dict(sorted(tx_account_distribution.items())),
        "total_tx_slot_entries": sum(tx_slot_distribution.values()),
        "total_tx_account_entries": sum(tx_account_distribution.values()),
    }


def agg_distribution(results: list[dict], key: str) -> dict[int, int]:
    agg: dict = defaultdict(int)
    for r in results:
        for n_val, count in r[key].items():
            agg[int(n_val)] += count
    return dict(sorted(agg.items()))


def distribution_stats(d: dict[int, int]) -> dict:
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
