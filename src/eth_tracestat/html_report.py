"""HTML report with embedded charts."""

import base64
import sys
from collections import defaultdict
from io import BytesIO

from .aggregate import agg_distribution, distribution_stats


def _chart_png(distribution: dict, title: str, xlabel: str, ylabel: str,
               max_bins: int = 60) -> str:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 4.5))
    if distribution:
        items = sorted(distribution.items(), key=lambda x: int(x[0]))
        if len(items) > max_bins:
            head = items[:max_bins - 1]
            tail_sum = sum(c for _, c in items[max_bins - 1:])
            cap = int(items[max_bins - 1][0])
            xs = [str(int(n)) for n, _ in head] + [f"≥{cap}"]
            ys = [c for _, c in head] + [tail_sum]
        else:
            xs = [str(int(n)) for n, _ in items]
            ys = [c for _, c in items]
        ax.bar(xs, ys, color="#4a7cbf", edgecolor="#1a3a5a", linewidth=0.5)
        if max(ys) > 0 and max(ys) / max(1, min(y for y in ys if y > 0)) > 20:
            ax.set_yscale("log")
        if len(xs) > 25:
            for label in ax.get_xticklabels():
                label.set_rotation(60)
                label.set_fontsize(8)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=110)
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _fmt(n) -> str:
    return f"{int(n):,}"


def write_html_report(results: list, output_path: str):
    if not results:
        print("No results to report.", file=sys.stderr)
        return

    distributions = [
        ("N(s,B)", "Per-block slot accesses",
         "Total SLOAD/SSTORE ops on each (contract, slot) within a block "
         "(summed across all transactions).",
         "n_distribution", "ops on a slot in the block", "(contract, slot) pairs"),
        ("N(c,B)", "Per-block account calls",
         "Total calls to each contract within a block (entry points + CALL-family ops, "
         "summed across all transactions).",
         "account_n_distribution", "calls to an account in the block", "contracts"),
        ("N(s,T)", "Per-tx slot accesses",
         "Number of SLOAD/SSTORE ops a single transaction performs on a given slot.",
         "tx_slot_distribution", "ops within a tx", "(tx, contract, slot) triples"),
        ("N(c,T)", "Per-tx account calls",
         "Number of times a single transaction calls a given contract (entry + CALL-family).",
         "tx_account_distribution", "calls within a tx", "(tx, contract) pairs"),
    ]

    agg_data = {}
    for short, _, _, key, _, _ in distributions:
        agg_data[short] = agg_distribution(results, key)

    n_blocks = len(results)
    block_min = min(r["block"] for r in results)
    block_max = max(r["block"] for r in results)
    total_txs = sum(r["total_txs"] for r in results)

    slot_totals: dict = defaultdict(int)
    for r in results:
        for s in r["top_shared_slots"]:
            slot_totals[(s["contract"], s["slot"])] += s["n_ops"]
    top_slots_window = sorted(slot_totals.items(), key=lambda x: x[1], reverse=True)[:20]

    acct_totals: dict = defaultdict(int)
    for r in results:
        for a in r["top_shared_accounts"]:
            acct_totals[a["account"]] += a["n_calls"]
    top_accts_window = sorted(acct_totals.items(), key=lambda x: x[1], reverse=True)[:20]

    sections_html = []
    for short, title, desc, key, xlabel, unit in distributions:
        d = agg_data[short]
        stats = distribution_stats(d)
        png = _chart_png(d, f"{short} — {title}", xlabel, f"count of {unit}")
        sections_html.append(f"""
        <section class="dist">
          <h2>{short} — {title}</h2>
          <p class="desc">{desc}</p>
          <div class="stats">
            <div><span class="label">Total</span><span class="val">{_fmt(stats['total'])}</span></div>
            <div><span class="label">Mean N</span><span class="val">{stats['mean']:.2f}</span></div>
            <div><span class="label">Median N</span><span class="val">{stats['p50']}</span></div>
            <div><span class="label">p95 N</span><span class="val">{stats['p95']}</span></div>
            <div><span class="label">p99 N</span><span class="val">{stats['p99']}</span></div>
            <div><span class="label">Max N</span><span class="val">{_fmt(stats['max'])}</span></div>
            <div><span class="label">N=1 share</span><span class="val">{stats['n1_pct']:.1%}</span></div>
            <div><span class="label">N≥2 share</span><span class="val">{stats['shared_pct']:.1%}</span></div>
          </div>
          <img alt="{short} chart" src="data:image/png;base64,{png}"/>
        </section>
        """)

    top_slots_rows = "".join(
        f"<tr><td class='addr'>{c}</td><td class='slot'>0x{s}</td><td class='num'>{_fmt(n)}</td></tr>"
        for (c, s), n in top_slots_window
    ) or "<tr><td colspan='3'>No shared slots</td></tr>"

    top_accts_rows = "".join(
        f"<tr><td class='addr'>{a}</td><td class='num'>{_fmt(n)}</td></tr>"
        for a, n in top_accts_window
    ) or "<tr><td colspan='2'>No shared accounts</td></tr>"

    per_block_rows = "".join(
        f"<tr><td class='num'>{r['block']}</td>"
        f"<td class='num'>{_fmt(r['total_txs'])}</td>"
        f"<td class='num'>{_fmt(r['total_unique_slots'])}</td>"
        f"<td class='num'>{_fmt(r['multi_access_slots'])}</td>"
        f"<td class='num'>{r['multi_access_rate']:.1%}</td>"
        f"<td class='num'>{_fmt(r['total_unique_accounts'])}</td>"
        f"<td class='num'>{_fmt(r['multi_call_accounts'])}</td>"
        f"<td class='num'>{r['multi_call_rate']:.1%}</td></tr>"
        for r in results
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>EVM Trace Analysis — blocks {block_min}–{block_max}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         max-width: 1100px; margin: 2rem auto; padding: 0 1.5rem; color: #222; }}
  h1 {{ border-bottom: 2px solid #1a3a5a; padding-bottom: .3em; }}
  h2 {{ color: #1a3a5a; margin-top: 2.2rem; }}
  .meta {{ color: #666; font-size: .95em; margin-bottom: 2rem; }}
  .meta span {{ margin-right: 1.2em; }}
  .desc {{ color: #555; font-style: italic; }}
  .dist img {{ max-width: 100%; border: 1px solid #ddd; border-radius: 4px; }}
  .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: .5rem; margin: 1rem 0; }}
  .stats div {{ background: #f3f5f8; border-radius: 4px; padding: .5rem .7rem; }}
  .stats .label {{ display: block; color: #666; font-size: .78em; text-transform: uppercase;
                   letter-spacing: .04em; }}
  .stats .val {{ display: block; font-weight: 600; font-size: 1.1em; color: #1a3a5a; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; font-size: .92em; }}
  th, td {{ border-bottom: 1px solid #e4e6eb; padding: .4rem .6rem; text-align: left; }}
  th {{ background: #f3f5f8; font-weight: 600; }}
  td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  td.addr, td.slot {{ font-family: ui-monospace, Menlo, Consolas, monospace;
                      font-size: .85em; }}
  details {{ margin-top: 1.5rem; }}
  summary {{ cursor: pointer; font-weight: 600; color: #1a3a5a; padding: .4rem 0; }}
  @media print {{ details[open] summary {{ page-break-after: avoid; }} }}
</style>
</head>
<body>
  <h1>Storage Slot & Account Access Report</h1>
  <div class="meta">
    <span><b>Blocks:</b> {block_min} – {block_max}</span>
    <span><b>Block count:</b> {n_blocks}</span>
    <span><b>Total txs:</b> {_fmt(total_txs)}</span>
  </div>

  {''.join(sections_html)}

  <h2>Top (contract, slot) pairs by ops — window total</h2>
  <table>
    <thead><tr><th>Contract</th><th>Slot</th><th>Σ ops (top-15 per block)</th></tr></thead>
    <tbody>{top_slots_rows}</tbody>
  </table>

  <h2>Top accounts by calls — window total</h2>
  <table>
    <thead><tr><th>Account</th><th>Σ calls (top-15 per block)</th></tr></thead>
    <tbody>{top_accts_rows}</tbody>
  </table>

  <details>
    <summary>Per-block breakdown ({n_blocks} blocks)</summary>
    <table>
      <thead><tr>
        <th>Block</th><th>Txs</th>
        <th>Uniq slots</th><th>N≥2 slots</th><th>N≥2 rate</th>
        <th>Uniq accts</th><th>N≥2 accts</th><th>N≥2 rate</th>
      </tr></thead>
      <tbody>{per_block_rows}</tbody>
    </table>
  </details>

  <p class="meta" style="margin-top:2rem;">
    To save as PDF, open this file in a browser and use File → Print → Save as PDF.
  </p>
</body>
</html>"""

    with open(output_path, "w") as f:
        f.write(html)
    print(f"\nHTML report written to {output_path}")
