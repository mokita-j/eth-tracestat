"""Structured results database in SQLite. Stores full per-key counts."""

import sqlite3

from .trace_processor import BlockCounts


class ResultsDB:
    def __init__(self, path: str):
        self.conn = sqlite3.connect(path)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()

    def _create_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS blocks (
                block_num    INTEGER PRIMARY KEY,
                n_txs        INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS storage_ops (
                block_num    INTEGER NOT NULL,
                tx_idx       INTEGER NOT NULL,
                contract     TEXT NOT NULL,
                slot         TEXT NOT NULL,
                sload_count  INTEGER NOT NULL DEFAULT 0,
                sstore_count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (block_num, tx_idx, contract, slot)
            );

            CREATE TABLE IF NOT EXISTS calls (
                block_num    INTEGER NOT NULL,
                tx_idx       INTEGER NOT NULL,
                contract     TEXT NOT NULL,
                call_count   INTEGER NOT NULL,
                PRIMARY KEY (block_num, tx_idx, contract)
            );

            CREATE INDEX IF NOT EXISTS idx_storage_ops_contract ON storage_ops(contract);
            CREATE INDEX IF NOT EXISTS idx_storage_ops_block ON storage_ops(block_num);
            CREATE INDEX IF NOT EXISTS idx_calls_contract ON calls(contract);
            CREATE INDEX IF NOT EXISTS idx_calls_block ON calls(block_num);
        """)

    def has_block(self, block_num: int) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM blocks WHERE block_num = ?", (block_num,)
        ).fetchone()
        return row is not None

    def store_block_counts(self, counts: BlockCounts) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO blocks (block_num, n_txs) VALUES (?, ?)",
            (counts.block_num, counts.n_txs),
        )

        # Delete existing rows for this block (idempotent re-analysis)
        self.conn.execute("DELETE FROM storage_ops WHERE block_num = ?", (counts.block_num,))
        self.conn.execute("DELETE FROM calls WHERE block_num = ?", (counts.block_num,))

        # Insert per-tx slot ops
        self.conn.executemany(
            "INSERT INTO storage_ops (block_num, tx_idx, contract, slot, sload_count, sstore_count) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                (counts.block_num, tx_idx, contract, slot, access.sload_count, access.sstore_count)
                for (tx_idx, contract, slot), access in counts.tx_slot_access.items()
            ],
        )

        # Insert per-tx account calls
        self.conn.executemany(
            "INSERT INTO calls (block_num, tx_idx, contract, call_count) VALUES (?, ?, ?, ?)",
            [
                (counts.block_num, tx_idx, contract, count)
                for (tx_idx, contract), count in counts.tx_account_call.items()
            ],
        )

        self.conn.commit()

    def block_range(self) -> tuple[int, int] | None:
        row = self.conn.execute(
            "SELECT MIN(block_num), MAX(block_num) FROM blocks"
        ).fetchone()
        if row is None or row[0] is None:
            return None
        return row[0], row[1]

    def block_count(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) FROM blocks").fetchone()
        return row[0]

    def close(self):
        self.conn.close()
