"""Pre-compute all views from results.db into a small JSON for the WASM app.

Uses `connect_with_sample` so every subsequent query auto-filters to the
stratified sample when sample_blocks.csv is present in the working dir.
"""

import json
import sys


def main():
    db_path = sys.argv[1] if len(sys.argv) > 1 else "data/results.db"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "docs/data.json"

    from eth_tracestat.sample import connect_with_sample, sample_info

    conn = connect_with_sample(db_path, "sample_blocks.csv")
    _samp = sample_info(conn)

    r = conn.execute(
        "SELECT MIN(block_num), MAX(block_num) FROM blocks "
        "WHERE block_num IN (SELECT block_num FROM sample_blocks)"
    ).fetchone()
    n_blocks = conn.execute(
        "SELECT COUNT(*) FROM blocks "
        "WHERE block_num IN (SELECT block_num FROM sample_blocks)"
    ).fetchone()[0]
    n_txs = conn.execute(
        "SELECT SUM(n_txs) FROM blocks "
        "WHERE block_num IN (SELECT block_num FROM sample_blocks)"
    ).fetchone()[0] or 0
    n_storage = conn.execute(
        "SELECT COUNT(*) FROM storage_ops "
        "WHERE block_num IN (SELECT block_num FROM sample_blocks)"
    ).fetchone()[0]
    n_calls = conn.execute(
        "SELECT COUNT(*) FROM calls "
        "WHERE block_num IN (SELECT block_num FROM sample_blocks)"
    ).fetchone()[0]
    print(f"Sample: {_samp}  |  meta: {n_blocks} blocks, {n_txs} txs")

    def query_dist(sql):
        return [[row[0], row[1]] for row in conn.execute(sql).fetchall()]

    # Shared filter fragment used everywhere — restricts to sampled blocks only.
    FILT = "AND block_num IN (SELECT block_num FROM sample_blocks)"
    FILT_W = "WHERE block_num IN (SELECT block_num FROM sample_blocks)"

    data = {
        "meta": {
            "block_min": r[0], "block_max": r[1],
            "n_blocks": n_blocks, "n_txs": n_txs,
            "n_storage": n_storage, "n_calls": n_calls,
        },
        "sample_info": _samp,
        "distributions": {
            "ns_b": query_dist(
                "SELECT op_count AS n, COUNT(*) AS cnt FROM ("
                "  SELECT SUM(sload_count + sstore_count) AS op_count"
                f"  FROM storage_ops {FILT_W} GROUP BY block_num, address, slot"
                ") GROUP BY n ORDER BY n"
            ),
            "na_b": query_dist(
                "SELECT call_count AS n, COUNT(*) AS cnt FROM ("
                "  SELECT SUM(call_count) AS call_count"
                f"  FROM calls {FILT_W} GROUP BY block_num, address"
                ") GROUP BY n ORDER BY n"
            ),
            "ns_t": query_dist(
                "SELECT sload_count + sstore_count AS n, COUNT(*) AS cnt"
                f" FROM storage_ops {FILT_W} GROUP BY n ORDER BY n"
            ),
            "na_t": query_dist(
                "SELECT call_count AS n, COUNT(*) AS cnt"
                f" FROM calls {FILT_W} GROUP BY n ORDER BY n"
            ),
        },
        "extra_stats": {
            "max_slots_block": conn.execute(
                "SELECT MAX(cnt) FROM ("
                "  SELECT COUNT(DISTINCT address || '|' || slot) AS cnt"
                f"  FROM storage_ops {FILT_W} GROUP BY block_num)"
            ).fetchone()[0] or 0,
            "max_addrs_block": conn.execute(
                "SELECT MAX(cnt) FROM ("
                "  SELECT COUNT(DISTINCT address) AS cnt"
                f"  FROM calls {FILT_W} GROUP BY block_num)"
            ).fetchone()[0] or 0,
            "max_slots_tx": conn.execute(
                "SELECT MAX(cnt) FROM ("
                "  SELECT COUNT(DISTINCT address || '|' || slot) AS cnt"
                f"  FROM storage_ops {FILT_W} GROUP BY block_num, tx_idx)"
            ).fetchone()[0] or 0,
            "max_addrs_tx": conn.execute(
                "SELECT MAX(cnt) FROM ("
                "  SELECT COUNT(DISTINCT address) AS cnt"
                f"  FROM calls {FILT_W} GROUP BY block_num, tx_idx)"
            ).fetchone()[0] or 0,
        },
        "top_slots": [
            {"address": row[0], "slot": row[1], "sloads": row[2], "sstores": row[3], "total": row[4]}
            for row in conn.execute(
                "SELECT address, slot, SUM(sload_count), SUM(sstore_count), "
                "SUM(sload_count + sstore_count) AS total "
                f"FROM storage_ops {FILT_W} GROUP BY address, slot ORDER BY total DESC LIMIT 30"
            ).fetchall()
        ],
        "top_accounts": [
            {"address": row[0], "total_calls": row[1], "blocks_present": row[2]}
            for row in conn.execute(
                "SELECT address, SUM(call_count) AS total, COUNT(DISTINCT block_num) AS blocks "
                f"FROM calls {FILT_W} GROUP BY address ORDER BY total DESC LIMIT 30"
            ).fetchall()
        ],
        "per_block": [
            {"block": row[0], "txs": row[1], "unique_slots": row[2], "unique_addrs": row[3]}
            for row in conn.execute(
                "SELECT b.block_num, b.n_txs,"
                "  (SELECT COUNT(DISTINCT s.address || '|' || s.slot) FROM storage_ops s WHERE s.block_num = b.block_num),"
                "  (SELECT COUNT(DISTINCT c.address) FROM calls c WHERE c.block_num = b.block_num)"
                f" FROM blocks b {FILT_W.replace('block_num', 'b.block_num')} ORDER BY b.block_num"
            ).fetchall()
        ],
    }

    # Warm analysis (Phases 1–4) — delegate to warm_analysis module which
    # auto-filters via the sample_blocks table registered on `conn`.
    from eth_tracestat.warm_analysis import (
        per_block_warm as _pbw,
        per_block_concentration as _pbc,
        access_frequency_pool as _afp,
        warm_by_contract as _wbc,
    )
    data["warm_analysis"] = {
        "per_block_warm": [
            {**r, "warm_rate": round(r["warm_rate"], 6),
             "within_rate": round(r["within_rate"], 6),
             "cross_rate": round(r["cross_rate"], 6)}
            for r in _pbw(conn)
        ],
        "per_block_concentration": [
            {**r, "unique_ratio": round(r["unique_ratio"], 6),
             "top10_share": round(r["top10_share"], 6),
             "top50_share": round(r["top50_share"], 6)}
            for r in _pbc(conn)
        ],
        "access_frequency_pool": _afp(conn),
        "warm_by_contract": _wbc(conn),
    }

    # Stratification (Phase 5) — reuses stratification module for consistency
    try:
        from eth_tracestat.stratification import (
            stratified_mean as _strat_mean,
            warm_rate_grid as _strat_grid,
            blocks_by_tercile as _strat_byterc,
            per_stratum_stats as _strat_per,
        )

        def _mean_info_dict(info):
            return {
                "mean": info["mean"],
                "sem": info["sem"],
                "ci95_low": info["ci95_low"],
                "ci95_high": info["ci95_high"],
                "naive_mean": info["naive_mean"],
                "n_populated": info["n_strata_populated"],
                "n_blocks": info["n_blocks"],
            }

        _mean_info_slot = _strat_mean(conn, "warm_rate", domain="slot")
        _cross_slot     = _strat_mean(conn, "cross_rate", domain="slot")
        _mean_info_acct = _strat_mean(conn, "warm_rate", domain="account")
        _cross_acct     = _strat_mean(conn, "cross_rate", domain="account")

        data["stratification"] = {
            "per_stratum": _strat_per(conn, "warm_rate", domain="slot"),
            "grid": _strat_grid(conn, "warm_rate", domain="slot"),
            "by_tercile": {str(k): v for k, v in _strat_byterc(conn, "warm_rate", domain="slot").items()},
            "mean_info": _mean_info_dict(_mean_info_slot),
        }
        data["stratification_extras"] = {
            "slot_cross":    _mean_info_dict(_cross_slot),
            "account_mean":  _mean_info_dict(_mean_info_acct),
            "account_cross": _mean_info_dict(_cross_acct),
        }
    except Exception as _e:
        data["stratification"] = {}
        data["stratification_extras"] = {}
        print(f"Stratification skipped: {_e}")

    # Account-level analysis (Phase 2 companion)
    try:
        from eth_tracestat.warm_analysis import per_block_warm_accounts as _pbwa
        data["account_analysis"] = {
            "per_block_warm": _pbwa(conn),
        }
    except Exception as _e:
        data["account_analysis"] = {}
        print(f"Account analysis skipped: {_e}")

    # Reuse correlation scatter data (block, tercile, slot_warm, acct_warm).
    # Uses the sample_blocks table (CSV-defined strata) as ground truth for
    # block membership and tercile labels.
    try:
        scatter_rows = conn.execute("""
            WITH slot AS (
                SELECT block_num,
                       SUM(sload_count + sstore_count) AS T,
                       COUNT(DISTINCT address || '|' || slot) AS U
                FROM storage_ops
                WHERE block_num IN (SELECT block_num FROM sample_blocks)
                GROUP BY block_num
            ),
            acct AS (
                SELECT block_num,
                       SUM(call_count) AS T,
                       COUNT(DISTINCT address) AS U
                FROM calls
                WHERE block_num IN (SELECT block_num FROM sample_blocks)
                GROUP BY block_num
            )
            SELECT sb.block_num, sb.gas_tercile,
                   (slot.T - slot.U) * 1.0 / slot.T,
                   (acct.T - acct.U) * 1.0 / acct.T
            FROM sample_blocks sb
            JOIN slot ON slot.block_num = sb.block_num AND slot.T > 0
            JOIN acct ON acct.block_num = sb.block_num AND acct.T > 0
            ORDER BY sb.block_num
        """).fetchall()
        data["reuse_correlation"] = [
            {
                "block": r[0], "tercile": r[1],
                "slot_warm": round(r[2], 6), "acct_warm": round(r[3], 6),
            }
            for r in scatter_rows
        ]
    except Exception as _e:
        data["reuse_correlation"] = []
        print(f"Reuse correlation skipped: {_e}")

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
