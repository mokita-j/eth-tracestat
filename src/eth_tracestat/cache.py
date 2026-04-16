"""Raw RPC trace cache in SQLite. Stores compressed JSON blobs per tx."""

import json
import sqlite3
import zlib


class TraceCache:
    def __init__(self, path: str):
        self.conn = sqlite3.connect(path)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()

    def _create_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS blocks (
                block_num   INTEGER PRIMARY KEY,
                block_json  BLOB NOT NULL,
                n_txs       INTEGER NOT NULL,
                fetched_at  TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS tx_traces (
                block_num   INTEGER NOT NULL,
                tx_idx      INTEGER NOT NULL,
                trace_json  BLOB NOT NULL,
                PRIMARY KEY (block_num, tx_idx)
            );
        """)

    def has_block(self, block_num: int) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM blocks WHERE block_num = ?", (block_num,)
        ).fetchone()
        return row is not None

    def store_block(self, block_num: int, block_data: dict, traces: list[dict]) -> None:
        block_blob = zlib.compress(json.dumps(block_data).encode())
        self.conn.execute(
            "INSERT OR REPLACE INTO blocks (block_num, block_json, n_txs) VALUES (?, ?, ?)",
            (block_num, block_blob, len(traces)),
        )
        for tx_idx, tx_trace in enumerate(traces):
            trace_blob = zlib.compress(json.dumps(tx_trace).encode())
            self.conn.execute(
                "INSERT OR REPLACE INTO tx_traces (block_num, tx_idx, trace_json) VALUES (?, ?, ?)",
                (block_num, tx_idx, trace_blob),
            )
        self.conn.commit()

    def load_block(self, block_num: int) -> tuple[dict, list[dict]]:
        row = self.conn.execute(
            "SELECT block_json, n_txs FROM blocks WHERE block_num = ?", (block_num,)
        ).fetchone()
        if row is None:
            raise KeyError(f"Block {block_num} not in cache")

        block_data = json.loads(zlib.decompress(row[0]))
        n_txs = row[1]

        traces = []
        for tx_row in self.conn.execute(
            "SELECT trace_json FROM tx_traces WHERE block_num = ? ORDER BY tx_idx",
            (block_num,),
        ):
            traces.append(json.loads(zlib.decompress(tx_row[0])))

        if len(traces) != n_txs:
            raise KeyError(
                f"Block {block_num}: expected {n_txs} tx traces, found {len(traces)} "
                f"(partial cache — re-fetch needed)"
            )
        return block_data, traces

    def cached_blocks(self) -> list[int]:
        return [
            row[0] for row in
            self.conn.execute("SELECT block_num FROM blocks ORDER BY block_num").fetchall()
        ]

    def close(self):
        self.conn.close()
