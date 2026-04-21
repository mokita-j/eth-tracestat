"""Load the stratified sampling design from sample_blocks.csv and register
it inside a SQLite connection as a temporary table.

Every downstream analysis query should filter by
`block_num IN (SELECT block_num FROM sample_blocks)` when this table is
present. This ensures we never mix sampling designs (the stratified sample
vs. any ad-hoc consecutive-block census).
"""

import csv
import os
import sqlite3


DEFAULT_CSV = "sample_blocks.csv"


def load_sample_csv(csv_path: str = DEFAULT_CSV) -> list[dict]:
    """Read sample_blocks.csv → list of dicts with keys:
    block_num, timestamp, gas_used, base_fee, segment, gas_tercile.

    The CSV columns are (uppercase): NUMBER, TIMESTAMP, GAS_USED,
    BASE_FEE_PER_GAS, SEGMENT, GAS_TERCILE.
    """
    rows: list[dict] = []
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append({
                "block_num": int(r["NUMBER"]),
                "timestamp": r["TIMESTAMP"],
                "gas_used": int(r["GAS_USED"]),
                "base_fee": int(r["BASE_FEE_PER_GAS"]),
                "segment": int(r["SEGMENT"]),
                "gas_tercile": int(r["GAS_TERCILE"]),
            })
    return rows


def register_sample_table(
    conn: sqlite3.Connection,
    csv_path: str = DEFAULT_CSV,
) -> dict:
    """Register `sample_blocks` as a TEMPORARY TABLE in `conn`.

    After this call, every query can filter with:
        WHERE block_num IN (SELECT block_num FROM sample_blocks)

    Or join against it to pull the (segment, gas_tercile) labels:
        JOIN sample_blocks sb ON sb.block_num = b.block_num

    Behavior:
    - If the CSV exists and is readable, populate with its entries using the
      CSV's (SEGMENT, GAS_TERCILE) labels.
    - If the CSV is missing, fall back to recomputing NTILE(12) × NTILE(3)
      over all blocks in the `blocks` table. This means downstream queries
      can unconditionally reference `sample_blocks` — when no CSV exists,
      the filter is effectively a no-op (all blocks included) but strata
      labels are still assigned.

    Returns a dict with {"source": "csv"|"ntile", "n": int} summarizing.
    """
    conn.execute("""
        CREATE TEMP TABLE IF NOT EXISTS sample_blocks (
            block_num    INTEGER PRIMARY KEY,
            segment      INTEGER NOT NULL,
            gas_tercile  INTEGER NOT NULL
        )
    """)
    conn.execute("DELETE FROM sample_blocks")

    csv_rows = None
    if os.path.exists(csv_path):
        try:
            csv_rows = load_sample_csv(csv_path)
        except Exception:
            csv_rows = None

    if csv_rows:
        conn.executemany(
            "INSERT INTO sample_blocks (block_num, segment, gas_tercile) VALUES (?, ?, ?)",
            [(r["block_num"], r["segment"], r["gas_tercile"]) for r in csv_rows],
        )
        conn.commit()
        return {"source": "csv", "n": len(csv_rows)}

    # Fallback: recompute NTILE on the blocks table
    rows = conn.execute("""
        WITH seg AS (
            SELECT block_num, gas_used,
                   NTILE(12) OVER (ORDER BY block_num) AS segment
            FROM blocks
            WHERE gas_used IS NOT NULL
        ),
        terciled AS (
            SELECT block_num, segment,
                   NTILE(3) OVER (PARTITION BY segment ORDER BY gas_used) AS gas_tercile
            FROM seg
        )
        SELECT block_num, segment, gas_tercile FROM terciled
    """).fetchall()
    conn.executemany(
        "INSERT INTO sample_blocks (block_num, segment, gas_tercile) VALUES (?, ?, ?)",
        rows,
    )
    conn.commit()
    return {"source": "ntile", "n": len(rows)}


def has_sample_table(conn: sqlite3.Connection) -> bool:
    """True if a `sample_blocks` temp/regular table exists in `conn`."""
    try:
        conn.execute("SELECT 1 FROM sample_blocks LIMIT 1")
        return True
    except sqlite3.OperationalError:
        return False


def connect_with_sample(
    db_path: str,
    csv_path: str = DEFAULT_CSV,
) -> sqlite3.Connection:
    """Open `db_path` and register `sample_blocks` in one call.

    This is the preferred entry point for CLI and script code — it
    guarantees the filter table is always available.
    """
    conn = sqlite3.connect(db_path)
    register_sample_table(conn, csv_path)
    return conn


def sample_info(conn: sqlite3.Connection) -> dict:
    """Return a summary dict describing the registered sample.

    Keys: n_sample, n_traced, n_extras. `n_extras` = blocks in the DB that
    are NOT in the sample (e.g., ad-hoc consecutive-window census) and
    should be excluded from publication-grade aggregates.
    """
    if not has_sample_table(conn):
        return {}
    row = conn.execute("""
        SELECT
            (SELECT COUNT(*) FROM sample_blocks) AS n_sample,
            (SELECT COUNT(*) FROM blocks WHERE block_num IN (SELECT block_num FROM sample_blocks)) AS n_traced,
            (SELECT COUNT(*) FROM blocks WHERE block_num NOT IN (SELECT block_num FROM sample_blocks)) AS n_extras
    """).fetchone()
    return {"n_sample": row[0], "n_traced": row[1], "n_extras": row[2]}
