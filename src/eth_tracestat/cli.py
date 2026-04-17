"""CLI entry point for eth-tracestat."""

import argparse
import json
import sys

import requests

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None

from .rpc import rpc, rpc_batch, latest_block
from .trace_processor import process_block_traces
from .aggregate import summarize_block
from .text_report import print_result, print_summary
from .html_report import write_html_report
from .cache import TraceCache
from .results import ResultsDB


def parse_args():
    p = argparse.ArgumentParser(
        description="Ethereum storage slot & account access analyzer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--rpc", help="Node RPC URL (not needed with --from-cache)")
    p.add_argument("--block", type=int, help="Single block to analyze")
    p.add_argument("--blocks", type=int, default=1,
                   help="Number of recent blocks (default: 1)")
    p.add_argument("--start", type=int, help="Start block for a range")
    p.add_argument("--count", type=int, default=10,
                   help="Number of blocks when using --start")
    p.add_argument("--cache", metavar="PATH",
                   help="SQLite trace cache — fetched traces are stored here "
                        "and reused on subsequent runs")
    p.add_argument("--from-cache", metavar="PATH",
                   help="Analyze from a trace cache only (no RPC needed). "
                        "Uses all cached blocks unless --start/--block narrow the range.")
    p.add_argument("--results-db", metavar="PATH",
                   help="Write full per-key counts to a SQLite results database")
    p.add_argument("--json-out", help="Write summary JSON results to file")
    p.add_argument("--html-out",
                   help="Write HTML report with charts")
    p.add_argument("--warm-report", metavar="DB",
                   help="Print warm-rate summary stats from a results.db and exit")
    return p.parse_args()


def resolve_blocks(args, cache: TraceCache | None = None) -> list[int]:
    if args.from_cache and cache:
        cached = cache.cached_blocks()
        if not cached:
            print("Cache is empty.", file=sys.stderr)
            sys.exit(1)
        if args.block:
            return [args.block]
        elif args.start:
            return [b for b in cached if args.start <= b < args.start + args.count]
        else:
            return cached

    if not args.rpc:
        print("--rpc is required (unless using --from-cache)", file=sys.stderr)
        sys.exit(1)

    if args.block:
        return [args.block]
    elif args.start:
        return list(range(args.start, args.start + args.count))
    else:
        tip = latest_block(args.rpc)
        return list(range(tip - args.blocks - 2, tip - 2))


def fetch_block(url: str, block_num: int) -> tuple[dict, list]:
    block_data = rpc(url, "eth_getBlockByNumber", [hex(block_num), True])
    trace_opts = {
        "disableMemory": True,
        "disableReturnData": True,
        "disableStack": False,
    }
    try:
        traces = rpc(url, "debug_traceBlockByNumber",
                      [hex(block_num), trace_opts], timeout=600)
    except requests.exceptions.ChunkedEncodingError:
        # Block trace too large — fall back to per-transaction tracing
        tx_hashes = [tx["hash"] for tx in block_data.get("transactions", [])]
        print(f"\n  Block {block_num}: block trace too large, "
              f"falling back to per-tx tracing ({len(tx_hashes)} txs)",
              file=sys.stderr)
        traces = []
        for tx_hash in tx_hashes:
            trace = rpc(url, "debug_traceTransaction", [tx_hash, trace_opts], timeout=600)
            traces.append(trace)
    return block_data, traces


def fetch_or_cache(url: str | None, block_num: int, cache: TraceCache | None) -> tuple[dict, list]:
    if cache and cache.has_block(block_num):
        return cache.load_block(block_num)

    if not url:
        raise RuntimeError(f"Block {block_num} not in cache and no --rpc provided")

    block_data, traces = fetch_block(url, block_num)

    if cache:
        cache.store_block(block_num, block_data, traces)

    return block_data, traces


def _print_warm_report(db_path: str) -> None:
    import sqlite3
    from .warm_analysis import per_block_warm, warm_by_contract

    conn = sqlite3.connect(db_path)
    rows = per_block_warm(conn)
    if not rows:
        print("No data in results DB.", file=sys.stderr)
        conn.close()
        return

    warm_rates = [r["warm_rate"] for r in rows]
    within_rates = [r["within_rate"] for r in rows]
    cross_rates = [r["cross_rate"] for r in rows]
    n = len(warm_rates)

    def _stats(vals, label):
        s = sorted(vals)
        mean = sum(s) / len(s)
        p5 = s[max(0, int(0.05 * len(s)) - 1)]
        p50 = s[len(s) // 2]
        p95 = s[min(len(s) - 1, int(0.95 * len(s)))]
        print(f"  {label:<22}  mean={mean:.4f}  p5={p5:.4f}  p50={p50:.4f}  p95={p95:.4f}")

    total_T = sum(r["T"] for r in rows)
    total_warm = sum(r["within_warm"] + r["cross_warm"] for r in rows)
    total_within = sum(r["within_warm"] for r in rows)
    total_cross = sum(r["cross_warm"] for r in rows)

    print(f"\n=== Warm-rate report — {n} blocks ===")
    print(f"\n  Total accesses     : {total_T:,}")
    print(f"  Total warm         : {total_warm:,}  ({total_warm / total_T:.4f})")
    print(f"  Within-tx warm     : {total_within:,}  ({total_within / total_T:.4f})")
    print(f"  Cross-tx warm      : {total_cross:,}  ({total_cross / total_T:.4f})")
    print(f"  Cross / total warm : {total_cross / total_warm:.4f}" if total_warm else "")
    print()
    _stats(warm_rates, "Warm rate")
    _stats(within_rates, "Within-tx rate")
    _stats(cross_rates, "Cross-tx rate")

    contracts = warm_by_contract(conn)[:10]
    if contracts:
        print(f"\n  Top 10 contracts by warm accesses:")
        for i, c in enumerate(contracts, 1):
            print(f"  {i:>2}. {c['address']}  warm={c['warm_accesses']:,}")

    conn.close()


def main():
    args = parse_args()

    if args.warm_report:
        _print_warm_report(args.warm_report)
        return

    # Open cache / results DB
    cache = None
    if args.cache:
        cache = TraceCache(args.cache)
    elif args.from_cache:
        cache = TraceCache(args.from_cache)

    results_db = None
    if args.results_db:
        results_db = ResultsDB(args.results_db)

    blocks = resolve_blocks(args, cache)

    print(f"Analyzing blocks {blocks[0]} -> {blocks[-1]}  ({len(blocks)} total)")
    if args.from_cache:
        print("Source: trace cache (offline)\n")
    else:
        print("Tracer: structLogger  |  ops: SLOAD + SSTORE")
        print("Note: large blocks can produce 50-200 MB responses.")
        print("If you hit timeouts, use a self-hosted node or a smaller block range.\n")

    results = []
    iterator = tqdm(blocks, desc="blocks") if tqdm else blocks

    for bn in iterator:
        try:
            block_data, traces = fetch_or_cache(args.rpc, bn, cache)
            counts = process_block_traces(block_data, traces, bn)

            if results_db:
                results_db.store_block_counts(counts)

            summary = summarize_block(counts)
            results.append(summary)
            print_result(summary)
        except Exception as e:
            print(f"\n  Block {bn}: FAILED — {type(e).__name__}: {e}", file=sys.stderr)

    print_summary(results)

    if results_db:
        br = results_db.block_range()
        if br:
            print(f"\nResults DB: {results_db.block_count()} blocks ({br[0]}-{br[1]})")

    if args.json_out:
        with open(args.json_out, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nFull results written to {args.json_out}")

    if args.html_out:
        write_html_report(results, args.html_out)

    # Cleanup
    if cache:
        cache.close()
    if results_db:
        results_db.close()


if __name__ == "__main__":
    main()
