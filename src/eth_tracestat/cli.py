"""CLI entry point for eth-tracestat."""

import argparse
import json
import sys

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None

from .rpc import rpc, latest_block
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
    traces = rpc(
        url,
        "debug_traceBlockByNumber",
        [hex(block_num), {
            "disableMemory": True,
            "disableReturnData": True,
            "disableStack": False,
        }],
        timeout=600,
    )
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


def main():
    args = parse_args()

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
            print(f"\n  Block {bn}: FAILED — {e}", file=sys.stderr)

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
