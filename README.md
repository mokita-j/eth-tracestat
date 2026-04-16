# eth-tracestat

Analyze Ethereum storage slot and account access patterns from block traces.

Fetches `debug_traceBlockByNumber` traces, walks every opcode step to extract SLOAD/SSTORE operations and CALL-family invocations, and produces four distributions:

| Metric | Grouping | What it measures |
|---|---|---|
| **N(s, B)** | Per block | SLOAD+SSTORE ops per (address, slot) in a block |
| **N(a, B)** | Per block | Calls per account address in a block |
| **N(s, T)** | Per tx | SLOAD+SSTORE ops per (address, slot) in a single tx |
| **N(a, T)** | Per tx | Calls per account address in a single tx |

Contract attribution follows EVM storage semantics — DELEGATECALL/CALLCODE inherit the caller's storage context. Precompile addresses (0x01–0x0a) are excluded from account distributions. SLOAD and SSTORE counts are tracked separately.

## Quick start

```bash
pip install -e .

# Fetch and analyze 10 blocks (traces are cached for re-analysis)
python -m eth_tracestat.cli \
  --rpc <your_rpc_url> \
  --start 22000000 --count 10 \
  --cache traces.db \
  --results-db data/results.db

# Interactive exploration
pip install marimo plotly numpy
marimo run app.py
```

## Architecture

```
RPC node ──(slow)──> traces.db (raw cache, local)
                         │
                         │ process (fast, offline)
                         ▼
                     results.db (per-key counts)
                         │
                    ┌────┴────┐
                    ▼         ▼
              Marimo app    CLI reports
```

**traces.db** — SQLite cache of raw RPC responses (zlib-compressed per-tx blobs). Fetch once, re-analyze as many times as you want with different logic.

**results.db** — SQLite with full per-key counts. Three tables:

| Table | Key | Columns |
|---|---|---|
| `blocks` | block_num | n_txs |
| `storage_ops` | (block_num, tx_idx, address, slot) | sload_count, sstore_count |
| `calls` | (block_num, tx_idx, address) | call_count |

Any distribution can be reconstructed from SQL. No data is discarded.

## CLI

```bash
# Single block
python -m eth_tracestat.cli --rpc <url> --block 22000000

# Range of blocks
python -m eth_tracestat.cli --rpc <url> --start 22000000 --count 20

# With caching and results DB
python -m eth_tracestat.cli --rpc <url> --start 22000000 --count 20 \
  --cache traces.db --results-db data/results.db

# Re-analyze from cache (no RPC needed)
python -m eth_tracestat.cli --from-cache traces.db --results-db data/results.db

# Export HTML report
python -m eth_tracestat.cli --rpc <url> --block 22000000 --html-out report.html
```

## Marimo app

The interactive app (`app.py`) has two modes:

**Local mode** (`marimo run app.py`) — reads from `data/results.db`, full block range filtering, SQL explorer for custom queries.

**Static mode** (GitHub Pages) — loads pre-computed data embedded in the page. Charts and tables work, SQL explorer is disabled. Download `results.db.gz` to run locally for full features.

## Deploy to GitHub Pages

```bash
# Populate the database
python -m eth_tracestat.cli --rpc <url> --start 22000000 --count 50 \
  --cache traces.db --results-db data/results.db

# Export static site
./scripts/export_wasm.sh

# Push
git add docs/ && git commit -m "update pages"
git push
```

Enable Pages in repo settings: Source → Deploy from branch → `main` / `/docs`.

## Project structure

```
src/eth_tracestat/
  evm.py              Constants, normalize_addr()
  rpc.py              JSON-RPC helpers
  trace_processor.py  BlockCounts dataclass, process_block_traces()
  cache.py            TraceCache (traces.db)
  results.py          ResultsDB (results.db)
  aggregate.py        Summarize BlockCounts into report dicts
  text_report.py      Terminal output
  html_report.py      Standalone HTML report
  cli.py              CLI entry point
app.py                Marimo interactive app
scripts/
  precompute.py       Generate JSON views from results.db
  export_wasm.sh      Build static site for GitHub Pages
```

## Requirements

- Python >= 3.11
- `requests`, `tqdm`, `matplotlib` (CLI)
- `marimo`, `plotly`, `numpy` (interactive app)
- An Ethereum node with `debug_traceBlockByNumber` enabled (archive node, or Alchemy/QuickNode paid tier)
