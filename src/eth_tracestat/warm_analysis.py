"""SQL-backed warm-rate metric functions.

Definitions (per block):
  T        = total accesses (sum of sload+sstore across all tx rows)
  U_tx     = unique (tx_idx, address, slot) rows
  U_block  = unique (address, slot) pairs

  within_tx_warm  = T - U_tx          (repeat accesses inside one tx, EIP-2929)
  cross_tx_warm   = U_tx - U_block    (first-in-tx but already touched by earlier tx, EIP-7863)
  cold            = U_block
  warm_rate       = (T - U_block) / T
"""

import sqlite3
from collections import defaultdict


def per_block_warm(conn: sqlite3.Connection) -> list[dict]:
    """Return per-block warm-rate decomposition.

    Each dict: {block, T, U_tx, U_block, within_warm, cross_warm,
                warm_rate, within_rate, cross_rate}
    """
    rows = conn.execute("""
        SELECT
            block_num,
            SUM(sload_count + sstore_count)                      AS T,
            COUNT(*)                                             AS U_tx,
            COUNT(DISTINCT address || '|' || slot)               AS U_block
        FROM storage_ops
        GROUP BY block_num
        ORDER BY block_num
    """).fetchall()

    result = []
    for block_num, T, U_tx, U_block in rows:
        if T == 0:
            continue
        within_warm = T - U_tx
        cross_warm = U_tx - U_block
        result.append({
            "block": block_num,
            "T": T,
            "U_tx": U_tx,
            "U_block": U_block,
            "within_warm": within_warm,
            "cross_warm": cross_warm,
            "warm_rate": (T - U_block) / T,
            "within_rate": within_warm / T,
            "cross_rate": cross_warm / T,
        })
    return result


def per_block_concentration(conn: sqlite3.Connection) -> list[dict]:
    """Return per-block concentration metrics.

    Each dict: {block, T, U_block, unique_ratio, top10_share, top50_share}
    """
    # Per block: total accesses and unique slots
    totals = {
        row[0]: (row[1], row[2])
        for row in conn.execute("""
            SELECT block_num,
                   SUM(sload_count + sstore_count) AS T,
                   COUNT(DISTINCT address || '|' || slot) AS U_block
            FROM storage_ops
            GROUP BY block_num
        """).fetchall()
    }

    # Per (block, address, slot): total accesses — used to compute top-N dominance
    slot_counts = defaultdict(list)
    for row in conn.execute("""
        SELECT block_num, SUM(sload_count + sstore_count) AS n
        FROM storage_ops
        GROUP BY block_num, address, slot
        ORDER BY block_num, n DESC
    """).fetchall():
        slot_counts[row[0]].append(row[1])

    result = []
    for block_num, (T, U_block) in sorted(totals.items()):
        if T == 0:
            continue
        counts = slot_counts[block_num]  # already sorted desc
        top10 = sum(counts[:10]) / T
        top50 = sum(counts[:50]) / T
        result.append({
            "block": block_num,
            "T": T,
            "U_block": U_block,
            "unique_ratio": U_block / T,
            "top10_share": top10,
            "top50_share": top50,
        })
    return result


def access_frequency_pool(conn: sqlite3.Connection) -> dict[str, int]:
    """Count (block, address, slot) groups by access frequency, pooled across all blocks.

    Returns dict with keys: '1', '2', '3-5', '6-10', '11+'
    """
    rows = conn.execute("""
        SELECT SUM(sload_count + sstore_count) AS n
        FROM storage_ops
        GROUP BY block_num, address, slot
    """).fetchall()

    buckets: dict[str, int] = {"1": 0, "2": 0, "3-5": 0, "6-10": 0, "11+": 0}
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


def warm_by_contract(conn: sqlite3.Connection) -> list[dict]:
    """Per-contract warm access totals across all blocks.

    warm_accesses for a contract in a block =
      total_accesses - unique_(address,slot) for that (block, address).

    Returns list of dicts sorted by warm_accesses desc:
      {address, warm_accesses, total_accesses, cold_accesses, blocks_present}
    """
    rows = conn.execute("""
        SELECT
            address,
            SUM(total_access)                              AS total_accesses,
            SUM(unique_slots)                              AS cold_accesses,
            SUM(total_access - unique_slots)               AS warm_accesses,
            COUNT(DISTINCT block_num)                      AS blocks_present
        FROM (
            SELECT
                block_num,
                address,
                SUM(sload_count + sstore_count)            AS total_access,
                COUNT(DISTINCT slot)                       AS unique_slots
            FROM storage_ops
            GROUP BY block_num, address
        ) sub
        GROUP BY address
        ORDER BY warm_accesses DESC
    """).fetchall()

    return [
        {
            "address": row[0],
            "total_accesses": row[1],
            "cold_accesses": row[2],
            "warm_accesses": row[3],
            "blocks_present": row[4],
            "short_addr": row[0][:6] + "…" + row[0][-4:],
        }
        for row in rows
        if row[3] and row[3] > 0
    ]
