"""Pre-compute all views from results.db into a small JSON for the WASM app."""

import json
import sqlite3
import sys


def main():
    db_path = sys.argv[1] if len(sys.argv) > 1 else "data/results.db"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "docs/data.json"

    conn = sqlite3.connect(db_path)

    r = conn.execute("SELECT MIN(block_num), MAX(block_num) FROM blocks").fetchone()
    n_blocks = conn.execute("SELECT COUNT(*) FROM blocks").fetchone()[0]
    n_txs = conn.execute("SELECT SUM(n_txs) FROM blocks").fetchone()[0] or 0
    n_storage = conn.execute("SELECT COUNT(*) FROM storage_ops").fetchone()[0]
    n_calls = conn.execute("SELECT COUNT(*) FROM calls").fetchone()[0]

    def query_dist(sql):
        return [[row[0], row[1]] for row in conn.execute(sql).fetchall()]

    data = {
        "meta": {
            "block_min": r[0], "block_max": r[1],
            "n_blocks": n_blocks, "n_txs": n_txs,
            "n_storage": n_storage, "n_calls": n_calls,
        },
        "distributions": {
            "ns_b": query_dist(
                "SELECT op_count AS n, COUNT(*) AS cnt FROM ("
                "  SELECT SUM(sload_count + sstore_count) AS op_count"
                "  FROM storage_ops GROUP BY block_num, address, slot"
                ") GROUP BY n ORDER BY n"
            ),
            "na_b": query_dist(
                "SELECT call_count AS n, COUNT(*) AS cnt FROM ("
                "  SELECT SUM(call_count) AS call_count"
                "  FROM calls GROUP BY block_num, address"
                ") GROUP BY n ORDER BY n"
            ),
            "ns_t": query_dist(
                "SELECT sload_count + sstore_count AS n, COUNT(*) AS cnt"
                " FROM storage_ops GROUP BY n ORDER BY n"
            ),
            "na_t": query_dist(
                "SELECT call_count AS n, COUNT(*) AS cnt"
                " FROM calls GROUP BY n ORDER BY n"
            ),
        },
        "extra_stats": {
            "max_slots_block": conn.execute(
                "SELECT MAX(cnt) FROM ("
                "  SELECT COUNT(DISTINCT address || '|' || slot) AS cnt"
                "  FROM storage_ops GROUP BY block_num)"
            ).fetchone()[0] or 0,
            "max_addrs_block": conn.execute(
                "SELECT MAX(cnt) FROM ("
                "  SELECT COUNT(DISTINCT address) AS cnt"
                "  FROM calls GROUP BY block_num)"
            ).fetchone()[0] or 0,
            "max_slots_tx": conn.execute(
                "SELECT MAX(cnt) FROM ("
                "  SELECT COUNT(DISTINCT address || '|' || slot) AS cnt"
                "  FROM storage_ops GROUP BY block_num, tx_idx)"
            ).fetchone()[0] or 0,
            "max_addrs_tx": conn.execute(
                "SELECT MAX(cnt) FROM ("
                "  SELECT COUNT(DISTINCT address) AS cnt"
                "  FROM calls GROUP BY block_num, tx_idx)"
            ).fetchone()[0] or 0,
        },
        "top_slots": [
            {"address": row[0], "slot": row[1], "sloads": row[2], "sstores": row[3], "total": row[4]}
            for row in conn.execute(
                "SELECT address, slot, SUM(sload_count), SUM(sstore_count), "
                "SUM(sload_count + sstore_count) AS total "
                "FROM storage_ops GROUP BY address, slot ORDER BY total DESC LIMIT 30"
            ).fetchall()
        ],
        "top_accounts": [
            {"address": row[0], "total_calls": row[1], "blocks_present": row[2]}
            for row in conn.execute(
                "SELECT address, SUM(call_count) AS total, COUNT(DISTINCT block_num) AS blocks "
                "FROM calls GROUP BY address ORDER BY total DESC LIMIT 30"
            ).fetchall()
        ],
        "per_block": [
            {"block": row[0], "txs": row[1], "unique_slots": row[2], "unique_addrs": row[3]}
            for row in conn.execute(
                "SELECT b.block_num, b.n_txs,"
                "  (SELECT COUNT(DISTINCT s.address || '|' || s.slot) FROM storage_ops s WHERE s.block_num = b.block_num),"
                "  (SELECT COUNT(DISTINCT c.address) FROM calls c WHERE c.block_num = b.block_num)"
                " FROM blocks b ORDER BY b.block_num"
            ).fetchall()
        ],
    }

    # Warm analysis (Phases 1–4)
    def _warm_per_block():
        rows = conn.execute("""
            SELECT
                block_num,
                SUM(sload_count + sstore_count)            AS T,
                COUNT(*)                                   AS U_tx,
                COUNT(DISTINCT address || '|' || slot)     AS U_block
            FROM storage_ops
            GROUP BY block_num
            ORDER BY block_num
        """).fetchall()
        out = []
        for block_num, T, U_tx, U_block in rows:
            if T == 0:
                continue
            out.append({
                "block": block_num, "T": T, "U_tx": U_tx, "U_block": U_block,
                "within_warm": T - U_tx,
                "cross_warm": U_tx - U_block,
                "warm_rate": round((T - U_block) / T, 6),
                "within_rate": round((T - U_tx) / T, 6),
                "cross_rate": round((U_tx - U_block) / T, 6),
            })
        return out

    def _concentration():
        totals = {
            row[0]: (row[1], row[2])
            for row in conn.execute("""
                SELECT block_num,
                       SUM(sload_count + sstore_count) AS T,
                       COUNT(DISTINCT address || '|' || slot) AS U_block
                FROM storage_ops GROUP BY block_num
            """).fetchall()
        }
        from collections import defaultdict
        slot_cnts = defaultdict(list)
        for row in conn.execute("""
            SELECT block_num, SUM(sload_count + sstore_count) AS n
            FROM storage_ops
            GROUP BY block_num, address, slot
            ORDER BY block_num, n DESC
        """).fetchall():
            slot_cnts[row[0]].append(row[1])
        out = []
        for block_num, (T, U_block) in sorted(totals.items()):
            if T == 0:
                continue
            cnts = slot_cnts[block_num]
            out.append({
                "block": block_num, "T": T, "U_block": U_block,
                "unique_ratio": round(U_block / T, 6),
                "top10_share": round(sum(cnts[:10]) / T, 6),
                "top50_share": round(sum(cnts[:50]) / T, 6),
            })
        return out

    def _freq_pool():
        rows = conn.execute("""
            SELECT SUM(sload_count + sstore_count) AS n
            FROM storage_ops
            GROUP BY block_num, address, slot
        """).fetchall()
        buckets = {"1": 0, "2": 0, "3-5": 0, "6-10": 0, "11+": 0}
        for (n,) in rows:
            if n == 1:
                buckets["1"] += 1
            elif n == 2:
                buckets["2"] += 1
            elif n <= 5:
                buckets["3-5"] += 1
            elif n <= 10:
                buckets["6-10"] += 1
            else:
                buckets["11+"] += 1
        return buckets

    def _warm_by_contract():
        rows = conn.execute("""
            SELECT address,
                   SUM(total_access)                        AS total_accesses,
                   SUM(unique_slots)                        AS cold_accesses,
                   SUM(total_access - unique_slots)         AS warm_accesses,
                   COUNT(DISTINCT block_num)                AS blocks_present
            FROM (
                SELECT block_num, address,
                       SUM(sload_count + sstore_count)      AS total_access,
                       COUNT(DISTINCT slot)                 AS unique_slots
                FROM storage_ops GROUP BY block_num, address
            ) sub
            GROUP BY address
            ORDER BY warm_accesses DESC
        """).fetchall()
        return [
            {
                "address": r[0],
                "total_accesses": r[1],
                "cold_accesses": r[2],
                "warm_accesses": r[3],
                "blocks_present": r[4],
                "short_addr": r[0][:6] + "…" + r[0][-4:],
            }
            for r in rows if r[3] and r[3] > 0
        ]

    data["warm_analysis"] = {
        "per_block_warm": _warm_per_block(),
        "per_block_concentration": _concentration(),
        "access_frequency_pool": _freq_pool(),
        "warm_by_contract": _warm_by_contract(),
    }

    conn.close()

    # Write JSON
    with open(out_path, "w") as f:
        json.dump(data, f, separators=(",", ":"))

    # Also write as a Python module next to app.py (for WASM bundling)
    py_path = "data.py"
    with open(py_path, "w") as f:
        f.write("# Auto-generated by scripts/precompute.py — do not edit\n")
        f.write(f"DATA = {json.dumps(data, separators=(',', ':'))}\n")

    import os
    size_kb = os.path.getsize(out_path) / 1024
    print(f"Wrote {out_path} ({size_kb:.0f} KB)")
    print(f"Wrote {py_path} ({os.path.getsize(py_path) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
