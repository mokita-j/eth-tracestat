"""Stratification-aware analysis of warm-rate metrics.

The sampling design is:
  12 time segments × 3 gas terciles = 36 strata
  ~34 blocks per stratum → ~1,224 blocks total

Stratum assignment per block:
  segment     = NTILE(12) OVER (ORDER BY block_num)
  gas_tercile = NTILE(3)  OVER (PARTITION BY segment ORDER BY gas_used)

Given proportional stratified random sampling where each stratum has
(approximately) equal population size, the unbiased estimator for a
population mean Y is:

  ȳ_str = Σ_h w_h · ȳ_h      with w_h = N_h / N

and its variance is:

  Var(ȳ_str) = Σ_h w_h² · (s²_h / n_h) · (1 - n_h / N_h)

For blocks sampled from a 2.7M-block population with n_h ≈ 34 each, the
finite-population correction (1 - n_h/N_h) ≈ 1 and is dropped here.

The implementation works with any dataset that has gas_used populated in
the blocks table — strata are reconstructed from the sample itself, which
is a reasonable approximation since the original sampling used the same
NTILE scheme against the full population.
"""

import math
import sqlite3
from collections import defaultdict


N_SEGMENTS = 12
N_TERCILES = 3


def assign_strata(
    conn: sqlite3.Connection,
    n_segments: int = N_SEGMENTS,
    n_terciles: int = N_TERCILES,
) -> list[dict]:
    """Return per-block stratum assignment reconstructed from the sample.

    Each dict: {block, gas_used, timestamp, segment, gas_tercile, stratum_id}
    stratum_id = (segment - 1) * n_terciles + gas_tercile (1-indexed).
    """
    rows = conn.execute(f"""
        WITH seg AS (
            SELECT
                block_num, gas_used, timestamp,
                NTILE({n_segments}) OVER (ORDER BY block_num) AS segment
            FROM blocks
            WHERE gas_used IS NOT NULL
        ),
        terciled AS (
            SELECT
                block_num, gas_used, timestamp, segment,
                NTILE({n_terciles}) OVER (
                    PARTITION BY segment ORDER BY gas_used
                ) AS gas_tercile
            FROM seg
        )
        SELECT block_num, gas_used, timestamp, segment, gas_tercile
        FROM terciled
        ORDER BY block_num
    """).fetchall()

    return [
        {
            "block": row[0],
            "gas_used": row[1],
            "timestamp": row[2],
            "segment": row[3],
            "gas_tercile": row[4],
            "stratum_id": (row[3] - 1) * n_terciles + row[4],
        }
        for row in rows
    ]


def _warm_rates_by_block(
    conn: sqlite3.Connection,
    domain: str = "slot",
) -> dict[int, dict]:
    """Return {block_num -> {warm_rate, within_rate, cross_rate, T}}.

    domain ∈ {"slot", "account"} selects the underlying table:
      - "slot":    storage_ops grouped by (tx_idx, address, slot)
      - "account": calls       grouped by (tx_idx, address)
    """
    if domain == "account":
        sql = """
            SELECT
                block_num,
                SUM(call_count)           AS T,
                COUNT(*)                  AS U_tx,
                COUNT(DISTINCT address)   AS U_block
            FROM calls
            GROUP BY block_num
        """
    else:
        sql = """
            SELECT
                block_num,
                SUM(sload_count + sstore_count)            AS T,
                COUNT(*)                                   AS U_tx,
                COUNT(DISTINCT address || '|' || slot)     AS U_block
            FROM storage_ops
            GROUP BY block_num
        """
    rows = conn.execute(sql).fetchall()
    out: dict[int, dict] = {}
    for block_num, T, U_tx, U_block in rows:
        if not T:
            continue
        out[block_num] = {
            "T": T,
            "warm_rate": (T - U_block) / T,
            "within_rate": (T - U_tx) / T,
            "cross_rate": (U_tx - U_block) / T,
        }
    return out


def per_stratum_stats(
    conn: sqlite3.Connection,
    metric: str = "warm_rate",
    n_segments: int = N_SEGMENTS,
    n_terciles: int = N_TERCILES,
    domain: str = "slot",
) -> list[dict]:
    """Per-stratum summary for a given metric.

    Returns list of dicts with one entry per (segment, gas_tercile):
      {segment, gas_tercile, n, mean, std, sem}

    metric ∈ {"warm_rate", "within_rate", "cross_rate"}.
    domain ∈ {"slot", "account"}.
    Missing (empty) strata are still emitted with n=0.
    """
    strata = assign_strata(conn, n_segments, n_terciles)
    rates = _warm_rates_by_block(conn, domain)

    groups: dict[tuple[int, int], list[float]] = defaultdict(list)
    for s in strata:
        r = rates.get(s["block"])
        if r is None:
            continue
        groups[(s["segment"], s["gas_tercile"])].append(r[metric])

    out = []
    for seg in range(1, n_segments + 1):
        for terc in range(1, n_terciles + 1):
            vals = groups.get((seg, terc), [])
            n = len(vals)
            if n == 0:
                out.append({
                    "segment": seg, "gas_tercile": terc,
                    "n": 0, "mean": None, "std": None, "sem": None,
                })
                continue
            mean = sum(vals) / n
            if n > 1:
                var = sum((v - mean) ** 2 for v in vals) / (n - 1)
                std = math.sqrt(var)
                sem = std / math.sqrt(n)
            else:
                std = 0.0
                sem = 0.0
            out.append({
                "segment": seg, "gas_tercile": terc,
                "n": n, "mean": mean, "std": std, "sem": sem,
            })
    return out


def stratified_mean(
    conn: sqlite3.Connection,
    metric: str = "warm_rate",
    n_segments: int = N_SEGMENTS,
    n_terciles: int = N_TERCILES,
    domain: str = "slot",
) -> dict:
    """Stratified point estimate + standard error for a metric.

    Uses equal stratum weights w_h = 1/H where H = n_segments * n_terciles,
    which matches the proportional NTILE-based design (each stratum covers
    ~1/H of the population).

    Returns:
        {
            "mean": weighted mean,
            "sem": standard error (sqrt of sum of weighted variances),
            "ci95_low": mean - 1.96 * sem,
            "ci95_high": mean + 1.96 * sem,
            "naive_mean": simple unweighted mean across sampled blocks,
            "n_strata_populated": number of non-empty strata,
            "n_blocks": total sampled blocks,
            "per_stratum": list from per_stratum_stats(...)
        }
    """
    per = per_stratum_stats(conn, metric, n_segments, n_terciles, domain)
    populated = [s for s in per if s["n"] > 0]
    H = n_segments * n_terciles
    w = 1.0 / H

    if not populated:
        return {
            "mean": None, "sem": None,
            "ci95_low": None, "ci95_high": None,
            "naive_mean": None,
            "n_strata_populated": 0,
            "n_blocks": 0,
            "per_stratum": per,
        }

    weighted_mean = sum(w * s["mean"] for s in populated)
    weighted_var = sum((w ** 2) * (s["sem"] ** 2) for s in populated)
    sem = math.sqrt(weighted_var)

    # Naive mean: each block weighted equally, no stratum correction.
    all_vals = []
    strata = assign_strata(conn, n_segments, n_terciles)
    rates = _warm_rates_by_block(conn, domain)
    for s in strata:
        r = rates.get(s["block"])
        if r is not None:
            all_vals.append(r[metric])

    naive_mean = sum(all_vals) / len(all_vals) if all_vals else None

    return {
        "mean": weighted_mean,
        "sem": sem,
        "ci95_low": weighted_mean - 1.96 * sem,
        "ci95_high": weighted_mean + 1.96 * sem,
        "naive_mean": naive_mean,
        "n_strata_populated": len(populated),
        "n_blocks": len(all_vals),
        "per_stratum": per,
    }


def warm_rate_grid(
    conn: sqlite3.Connection,
    metric: str = "warm_rate",
    n_segments: int = N_SEGMENTS,
    n_terciles: int = N_TERCILES,
    domain: str = "slot",
) -> dict:
    """Return a rectangular grid of mean metric values for heatmap plotting.

    Returns:
        {
            "z": [[tercile_1, tercile_2, tercile_3], ...]       # 12 rows × 3 cols
            "n": [[n_segment1_terc1, ...], ...]                 # sample counts per cell
            "x_labels": ["low", "mid", "high"],
            "y_labels": ["S1", "S2", ..., "S12"],
        }
    """
    per = per_stratum_stats(conn, metric, n_segments, n_terciles, domain)
    z: list[list[float | None]] = [[None] * n_terciles for _ in range(n_segments)]
    n: list[list[int]] = [[0] * n_terciles for _ in range(n_segments)]
    for s in per:
        z[s["segment"] - 1][s["gas_tercile"] - 1] = s["mean"]
        n[s["segment"] - 1][s["gas_tercile"] - 1] = s["n"]

    return {
        "z": z, "n": n,
        "x_labels": ["Low gas", "Mid gas", "High gas"],
        "y_labels": [f"Seg {i}" for i in range(1, n_segments + 1)],
    }


def blocks_by_tercile(
    conn: sqlite3.Connection,
    metric: str = "warm_rate",
    n_segments: int = N_SEGMENTS,
    n_terciles: int = N_TERCILES,
    domain: str = "slot",
) -> dict[int, list[float]]:
    """Return {gas_tercile: [metric_values...]} pooled across all segments.

    Useful for grouped-violin plots per tercile.
    """
    strata = assign_strata(conn, n_segments, n_terciles)
    rates = _warm_rates_by_block(conn, domain)
    out: dict[int, list[float]] = {t: [] for t in range(1, n_terciles + 1)}
    for s in strata:
        r = rates.get(s["block"])
        if r is None:
            continue
        out[s["gas_tercile"]].append(r[metric])
    return out
