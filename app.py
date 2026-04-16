# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
#     "plotly",
#     "numpy",
# ]
# ///

import marimo

__generated_with = "0.23.1"
app = marimo.App(width="full")


@app.cell
def _(mo):
    mo.md("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

    :root {
        --font-sans: 'Inter', -apple-system, system-ui, sans-serif;
        --font-mono: 'JetBrains Mono', ui-monospace, monospace;
        --slate-50: #f8fafc;
        --slate-100: #f1f5f9;
        --slate-200: #e2e8f0;
        --slate-400: #94a3b8;
        --slate-500: #64748b;
        --slate-600: #475569;
        --slate-800: #1e293b;
        --slate-900: #0f172a;
        --blue-500: #3b82f6;
        --blue-600: #2563eb;
    }

    body, .marimo {
        font-family: var(--font-sans) !important;
        color: var(--slate-800);
    }

    h1, h2, h3, h4 {
        font-family: var(--font-sans) !important;
        font-weight: 600 !important;
        color: var(--slate-900) !important;
        letter-spacing: -0.025em;
    }

    h1 { font-size: 1.875rem !important; }
    h3 { font-size: 1.1rem !important; color: var(--slate-800) !important; }

    code, pre, .cm-editor {
        font-family: var(--font-mono) !important;
        font-size: 0.85rem !important;
    }

    p, li, td, th, label, span { font-size: 0.9rem; }

    table th {
        font-weight: 600 !important;
        font-size: 0.8rem !important;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        color: var(--slate-500) !important;
    }

    table td {
        font-family: var(--font-mono) !important;
        font-size: 0.82rem !important;
    }

    .section-label {
        display: inline-block;
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        padding: 2px 8px;
        border-radius: 4px;
        margin-bottom: 4px;
    }

    .sql-col { display: flex; flex-direction: column; height: 100%; }
    .sql-col > :nth-child(2) { flex: 1; overflow: hidden; }
    .sql-col .cm-editor { height: 100% !important; }
    .sql-col .cm-editor .cm-scroller { height: 100% !important; }

    button[data-testid="marimo-plugin-ui-run-button"] {
        background: var(--blue-500) !important;
        color: white !important;
        border: none !important;
        border-radius: 6px !important;
        padding: 8px 24px !important;
        font-family: var(--font-sans) !important;
        font-weight: 500 !important;
        font-size: 0.85rem !important;
        cursor: pointer;
        transition: background 0.15s ease;
    }
    button[data-testid="marimo-plugin-ui-run-button"]:hover {
        background: var(--blue-600) !important;
    }

    .section-desc {
        color: var(--slate-500);
        font-size: 1rem;
        line-height: 1.6;
        margin: 4px 0 12px 0;
    }

    a.anchor-link {
        color: inherit !important;
        text-decoration: none !important;
    }
    a.anchor-link:hover {
        text-decoration: underline !important;
        text-decoration-color: var(--slate-400) !important;
        text-underline-offset: 4px;
    }
    a.anchor-link:hover::after {
        content: " #";
        color: var(--slate-400);
        font-weight: 400;
        font-size: 0.8em;
    }
    </style>

    <span id="top"></span>

    # Ethereum storage and account access analysis
    """)
    return


@app.cell
def _(json, mo, os):
    # Detect mode: local (SQLite) or static (pre-computed data)
    _local_db = "data/results.db"

    # STATIC_DATA_PLACEHOLDER is replaced by the export script with the actual JSON.
    # When running locally, this stays as None and the app uses SQLite instead.
    _embedded = None  # STATIC_DATA_EMBED

    if os.path.exists(_local_db):
        import sqlite3 as _sql
        local_conn = _sql.connect(_local_db)
        static_data = None
        is_local = True
    elif _embedded is not None:
        local_conn = None
        static_data = _embedded
        is_local = False
    else:
        # Fallback: try loading docs/data.json (local dev)
        local_conn = None
        is_local = False
        try:
            with open("docs/data.json") as _f:
                static_data = json.loads(_f.read())
        except Exception as _e:
            mo.stop(True, mo.callout(mo.md(
                f"**Could not load data.** {_e}"
            ), kind="danger"))
            static_data = None

    return is_local, local_conn, static_data


@app.cell
def _(is_local, local_conn, mo, static_data):
    def _sc(label, value):
        return (
            f'<div style="flex: 1; min-width: 100px; background: #f8fafc; '
            f'border-radius: 6px; padding: 8px 12px; text-align: center;">'
            f'<div style="font-size: 0.7rem; font-weight: 600; text-transform: uppercase; '
            f'letter-spacing: 0.05em; color: #94a3b8; margin-bottom: 2px;">{label}</div>'
            f'<div style="font-size: 1rem; font-weight: 600; color: #1e293b; '
            f'font-variant-numeric: tabular-nums;">{value}</div>'
            f'</div>'
        )

    if is_local:
        _r = local_conn.execute("SELECT MIN(block_num), MAX(block_num) FROM blocks").fetchone()
        _m = {
            "block_min": _r[0], "block_max": _r[1],
            "n_blocks": local_conn.execute("SELECT COUNT(*) FROM blocks").fetchone()[0],
            "n_txs": local_conn.execute("SELECT SUM(n_txs) FROM blocks").fetchone()[0] or 0,
            "n_storage": local_conn.execute("SELECT COUNT(*) FROM storage_ops").fetchone()[0],
            "n_calls": local_conn.execute("SELECT COUNT(*) FROM calls").fetchone()[0],
        }
    else:
        _m = static_data["meta"]

    _mode_note = (
        "Full interactive mode — SQLite loaded locally."
        if is_local else
        "Static mode — viewing pre-computed data. "
        '<a href="https://github.com/mokita-j/eth-tracestat" style="color: var(--blue-500);">Run locally</a> '
        "for block range filtering and SQL explorer."
    )

    _bmin = _m["block_min"]
    _bmax = _m["block_max"]
    _nb = _m["n_blocks"]
    _nt = _m["n_txs"]
    _ns = _m["n_storage"]
    _nc = _m["n_calls"]

    mo.vstack([
        mo.md(f'<p class="section-desc">{_mode_note}</p>'),
        mo.md(
            f'<div style="display: flex; gap: 8px; flex-wrap: wrap;">'
            f'{_sc("Block range", f"{_bmin:,} – {_bmax:,}")}'
            f'{_sc("Blocks", f"{_nb:,}")}'
            f'{_sc("Transactions", f"{_nt:,}")}'
            f'{_sc("Storage Reads/Writes", f"{_ns:,}")}'
            f'{_sc("Account Calls", f"{_nc:,}")}'
            f'</div>'
        ),
    ], gap=0.5)
    return


@app.cell
def _(is_local, local_conn, mo):
    if is_local:
        _all_blocks = [r[0] for r in local_conn.execute(
            "SELECT block_num FROM blocks ORDER BY block_num"
        ).fetchall()]
        _options = {f"{b:,}": b for b in _all_blocks}
        block_from = mo.ui.dropdown(options=_options, value=f"{_all_blocks[0]:,}", label="From block")
        block_to = mo.ui.dropdown(options=_options, value=f"{_all_blocks[-1]:,}", label="To block")
        mo.vstack([
            mo.md(
                '<p class="section-desc" style="margin-bottom: 4px;">'
                'Select the block range to analyze. All distributions, tables, and stats below will update accordingly.</p>'
            ),
            mo.hstack([block_from, block_to], justify="start", gap=0.75),
        ], gap=0.3)
    else:
        block_from = None
        block_to = None
    return block_from, block_to


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## <a id="distributions" href="#distributions" class="anchor-link">Access distributions</a>

    <p class="section-desc" style="margin-bottom: 0;">
    <b>N(x, y)</b> = number of accesses of type <b>x</b> per grouping <b>y</b>, where:
    <b>s</b> = storage slot, <b>a</b> = account address, <b>B</b> = block, <b>T</b> = transaction.
    </p>
    """)
    return


@app.cell
def _(block_from, block_to, go, is_local, local_conn, mo, np, static_data):
    # --- Helper to build a distribution section ---
    CHART_COLOR = "#3b82f6"

    def _stat_card(label, value):
        return (
            f'<div style="flex: 1; min-width: 80px; background: #f8fafc; '
            f'border-radius: 6px; padding: 8px 12px; text-align: center;">'
            f'<div style="font-size: 0.7rem; font-weight: 600; text-transform: uppercase; '
            f'letter-spacing: 0.05em; color: #94a3b8; margin-bottom: 2px;">{label}</div>'
            f'<div style="font-size: 1rem; font-weight: 600; color: #1e293b; '
            f'font-variant-numeric: tabular-nums;">{value}</div>'
            f'</div>'
        )

    def _make_section(rows, code, title, desc, extra_stat=None):
        if not rows:
            return mo.callout(mo.md(f"**{code}** — no data."), kind="warn")

        ns = np.array([r[0] for r in rows])
        cnts = np.array([r[1] for r in rows])
        total = int(cnts.sum())
        weighted = int((ns * cnts).sum())
        cdf = np.cumsum(cnts) / total
        p50 = int(ns[np.searchsorted(cdf, 0.50)])
        n1_cnt = int(cnts[ns == 1].sum()) if 1 in ns else 0
        n1_pct = n1_cnt / total

        cards = [("Total", f"{total:,}"), ("Mean", f"{weighted/total:.2f}"),
                 ("Median", str(p50)), ("Max N", f"{int(ns[-1]):,}"),
                 ("N=1", f"{n1_pct:.1%}"), ("N>=2", f"{1 - n1_pct:.1%}")]
        if extra_stat:
            cards.append(extra_stat)

        stats = mo.md(
            f'<div style="display: flex; gap: 8px; padding: 0 56px; flex-wrap: wrap;">'
            f'{"".join(_stat_card(l, v) for l, v in cards)}</div>'
        )

        max_bins = 50
        if len(ns) > max_bins:
            cap = int(ns[max_bins - 1])
            d_cnts = list(cnts[:max_bins - 1]) + [int(cnts[max_bins - 1:].sum())]
            labels = [str(int(n)) for n in ns[:max_bins - 1]] + [f"\u2265{cap}"]
        else:
            d_cnts = list(cnts)
            labels = [str(int(n)) for n in ns]

        pcts = [f"{c / total:.1%}" for c in d_cnts]
        use_log = max(d_cnts) / max(1, min(c for c in d_cnts if c > 0)) > 20

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=labels, y=d_cnts, marker_color=CHART_COLOR,
            marker_line_width=0, marker_opacity=0.85, customdata=pcts,
            hovertemplate="<b>N = %{x}</b><br>Count: %{y:,}<br>Share: %{customdata}<extra></extra>",
        ))
        fig.update_layout(
            font=dict(family="Inter, system-ui, sans-serif", size=12, color="#475569"),
            height=250, margin=dict(l=60, r=60, t=6, b=44),
            xaxis=dict(title=dict(text="N", font=dict(size=11, color="#94a3b8")),
                       tickangle=-45 if len(labels) > 25 else 0,
                       tickfont=dict(size=10, family="JetBrains Mono, monospace"),
                       showline=True, linewidth=1, linecolor="#e2e8f0", zeroline=False),
            yaxis=dict(title=dict(text="Frequency", font=dict(size=11, color="#94a3b8")),
                       type="log" if use_log else "linear", tickfont=dict(size=10),
                       showline=False, gridcolor="#f1f5f9", zeroline=False),
            plot_bgcolor="white", paper_bgcolor="white", bargap=0.2,
            hoverlabel=dict(bgcolor="white", bordercolor="#e2e8f0",
                            font=dict(size=12, family="Inter, sans-serif", color="#0f172a")),
        )
        fig.update_xaxes(gridcolor="rgba(0,0,0,0)")

        _anchor = code.lower().replace("(", "").replace(")", "").replace(", ", "-").replace(" ", "")
        header = mo.md(
            f'### <a id="{_anchor}" href="#{_anchor}" class="anchor-link">{code} — {title}</a>\n'
            f'<p class="section-desc">{desc}</p>'
        )
        return mo.vstack([header, stats, fig], gap=0.4)

    # --- Build all 4 distributions ---
    _defs = [
        ("ns_b",
         "SELECT op_count AS n, COUNT(*) AS cnt FROM ("
         "  SELECT SUM(sload_count + sstore_count) AS op_count"
         "  FROM storage_ops WHERE block_num BETWEEN ? AND ?"
         "  GROUP BY block_num, address, slot) GROUP BY n ORDER BY n",
         "N(s, B)", "Per-block slot accesses",
         "SLOAD+SSTORE ops per (address, slot) per block. Measures block-level storage warming potential.",
         "max_slots_block", "Max unique slots/block"),
        ("na_b",
         "SELECT call_count AS n, COUNT(*) AS cnt FROM ("
         "  SELECT SUM(call_count) AS call_count FROM calls WHERE block_num BETWEEN ? AND ?"
         "  GROUP BY block_num, address) GROUP BY n ORDER BY n",
         "N(a, B)", "Per-block account calls",
         "Calls per address per block. Precompiles excluded.",
         "max_addrs_block", "Max unique addresses/block"),
        ("ns_t",
         "SELECT sload_count + sstore_count AS n, COUNT(*) AS cnt"
         " FROM storage_ops WHERE block_num BETWEEN ? AND ? GROUP BY n ORDER BY n",
         "N(s, T)", "Per-tx slot accesses",
         "SLOAD+SSTORE ops per (address, slot) within a single tx.",
         "max_slots_tx", "Max unique slots/tx"),
        ("na_t",
         "SELECT call_count AS n, COUNT(*) AS cnt"
         " FROM calls WHERE block_num BETWEEN ? AND ? GROUP BY n ORDER BY n",
         "N(a, T)", "Per-tx account calls",
         "Calls to a single address within one tx.",
         "max_addrs_tx", "Max unique addresses/tx"),
    ]

    _sections = []
    for _i, (_key, _sql, _code, _title, _desc, _extra_key, _extra_label) in enumerate(_defs):
        if _i > 0:
            _sections.append(mo.md('<hr style="border: none; border-top: 1px solid #e2e8f0; margin: 8px 0;">'))

        if is_local:
            _bmin = block_from.value
            _bmax = block_to.value
            _rows = local_conn.execute(_sql, [_bmin, _bmax]).fetchall()
            _extra_val = local_conn.execute(
                f"SELECT MAX(cnt) FROM (SELECT COUNT(DISTINCT "
                f"{'address || chr(124) || slot' if 's' in _key else 'address'}"
                f") AS cnt FROM {'storage_ops' if 's' in _key else 'calls'}"
                f" WHERE block_num BETWEEN ? AND ?"
                f" GROUP BY {'block_num' if 'b' in _key else 'block_num, tx_idx'})",
                [_bmin, _bmax],
            ).fetchone()[0] or 0
        else:
            _rows = static_data["distributions"][_key]
            _extra_val = static_data["extra_stats"][_extra_key]

        _sections.append(_make_section(
            _rows, _code, _title, _desc,
            (_extra_label, f"{_extra_val:,}"),
        ))

    # Per-block breakdown
    if is_local:
        _block_rows = local_conn.execute(
            "SELECT b.block_num, b.n_txs,"
            "  (SELECT COUNT(DISTINCT s.address || '|' || s.slot) FROM storage_ops s WHERE s.block_num = b.block_num),"
            "  (SELECT COUNT(DISTINCT c.address) FROM calls c WHERE c.block_num = b.block_num)"
            " FROM blocks b WHERE b.block_num BETWEEN ? AND ? ORDER BY b.block_num",
            [block_from.value, block_to.value],
        ).fetchall()
        _block_data = [{"block": r[0], "txs": r[1], "unique_slots": r[2], "unique_addresses": r[3]}
                       for r in _block_rows]
    else:
        _block_data = static_data["per_block"]

    _sections.append(
        mo.accordion({
            f"Per-block breakdown ({len(_block_data)} blocks)": mo.ui.table(
                _block_data, selection=None, pagination=False,
                show_column_summaries=False, show_data_types=False, show_download=False,
            ) if _block_data else mo.md("*No data*"),
        })
    )

    mo.vstack(_sections, gap=1)
    return


@app.cell
def _(mo):
    mo.md('<hr style="border: none; border-top: 2px solid #e2e8f0; margin: 16px 0;">')
    return


@app.cell
def _(block_from, block_to, is_local, local_conn, mo, static_data):
    mo.md("""
    ## <a id="top-slots-accounts" href="#top-slots-accounts" class="anchor-link">Top slots & accounts</a>

    <p class="section-desc">Ranked by total ops/calls across the selected block range.</p>
    """)

    if is_local:
        _bmin, _bmax = block_from.value, block_to.value
        _params = [_bmin, _bmax]
        _slots = local_conn.execute(
            "SELECT address, slot, SUM(sload_count), SUM(sstore_count), "
            "SUM(sload_count + sstore_count) AS total "
            "FROM storage_ops WHERE block_num BETWEEN ? AND ? "
            "GROUP BY address, slot ORDER BY total DESC LIMIT 30", _params,
        ).fetchall()
        _accts = local_conn.execute(
            "SELECT address, SUM(call_count) AS total, COUNT(DISTINCT block_num) "
            "FROM calls WHERE block_num BETWEEN ? AND ? "
            "GROUP BY address ORDER BY total DESC LIMIT 30", _params,
        ).fetchall()
        _slot_data = [{"address": r[0], "slot": f"0x{r[1][:16]}...", "SLOADs": r[2], "SSTOREs": r[3], "total": r[4]}
                      for r in _slots]
        _acct_data = [{"address": r[0], "total_calls": r[1], "blocks_present": r[2]}
                      for r in _accts]
    else:
        _slot_data = [{"address": s["address"], "slot": f"0x{s['slot'][:16]}...",
                       "SLOADs": s["sloads"], "SSTOREs": s["sstores"], "total": s["total"]}
                      for s in static_data["top_slots"]]
        _acct_data = static_data["top_accounts"]

    mo.hstack([
        mo.vstack([
            mo.md('<span class="section-label" style="background: #3b82f618; color: #3b82f6;">STORAGE SLOTS</span>'),
            mo.ui.table(_slot_data, selection=None, pagination=False,
                        show_column_summaries=False, show_data_types=False, show_download=False)
            if _slot_data else mo.md("*No data*"),
        ]),
        mo.vstack([
            mo.md('<span class="section-label" style="background: #3b82f618; color: #3b82f6;">ACCOUNTS</span>'),
            mo.ui.table(_acct_data, selection=None, pagination=False,
                        show_column_summaries=False, show_data_types=False, show_download=False)
            if _acct_data else mo.md("*No data*"),
        ]),
    ], widths=[3, 2])
    return


@app.cell
def _(mo):
    mo.md('<hr style="border: none; border-top: 2px solid #e2e8f0; margin: 16px 0;">')
    return


@app.cell
def _(is_local, local_conn, mo):
    if not is_local:
        mo.md("""
        ## <a id="sql-explorer" href="#sql-explorer" class="anchor-link">SQL explorer</a>

        <p class="section-desc">
        The SQL explorer is available when running locally with <code>marimo run app.py</code>.
        It requires direct access to the SQLite database for arbitrary queries.
        </p>

        <p class="section-desc">
        Clone the repo and run locally:
        </p>

        ```
        pip install eth-tracestat marimo plotly numpy
        gunzip results.db.gz -c > data/results.db
        marimo run app.py
        ```
        """)
        return

    mo.md("""
    ## <a id="sql-explorer" href="#sql-explorer" class="anchor-link">SQL explorer</a>

    <p class="section-desc">
    Write custom SQL queries against the raw trace data.
    Use this to answer questions the charts above don't cover —
    filter by address, find the heaviest transactions, compare read/write ratios, etc.
    </p>
    """)

    sql_input = mo.ui.text_area(
        value="SELECT address,\n"
              "       SUM(sload_count + sstore_count) AS total_ops,\n"
              "       SUM(sload_count) AS reads,\n"
              "       SUM(sstore_count) AS writes\n"
              "FROM storage_ops\n"
              "GROUP BY address\n"
              "ORDER BY total_ops DESC\n"
              "LIMIT 20",
        rows=20,
        full_width=True,
    )
    run_button = mo.ui.run_button(label="Run query")

    _schema_data = [
        {"table": "blocks", "column": "block_num", "type": "INT (PK)"},
        {"table": "", "column": "n_txs", "type": "INT"},
        {"table": "storage_ops", "column": "block_num", "type": "INT"},
        {"table": "", "column": "tx_idx", "type": "INT"},
        {"table": "", "column": "address", "type": "TEXT"},
        {"table": "", "column": "slot", "type": "TEXT"},
        {"table": "", "column": "sload_count", "type": "INT"},
        {"table": "", "column": "sstore_count", "type": "INT"},
        {"table": "calls", "column": "block_num", "type": "INT"},
        {"table": "", "column": "tx_idx", "type": "INT"},
        {"table": "", "column": "address", "type": "TEXT"},
        {"table": "", "column": "call_count", "type": "INT"},
    ]
    _schema = mo.vstack([
        mo.md('<span class="section-label" style="background: #3b82f618; color: #3b82f6;">Database schema</span>'),
        mo.ui.table(_schema_data, selection=None, pagination=False,
                    show_column_summaries=False, show_data_types=False, show_download=False),
    ], gap=0.3)

    mo.hstack([
        _schema,
        mo.md(
            '<div class="sql-col">'
            '<span class="section-label" style="background: #3b82f618; color: #3b82f6; margin-bottom: 6px;">Custom query</span>'
            f'{mo.as_html(sql_input).text}'
            f'<div style="display:flex; justify-content:flex-start; margin-top: 6px;">{mo.as_html(run_button).text}</div>'
            '</div>'
        ),
    ], widths=[1, 3], align="stretch")
    return local_conn, run_button, sql_input


@app.cell
def _(is_local, local_conn, mo, run_button, sql_input):
    if not is_local:
        return

    mo.stop(not run_button.value)

    _query = sql_input.value.strip()
    if not _query:
        mo.stop(True, mo.md("*Enter a query above.*"))

    try:
        _cur = local_conn.execute(_query)
        _cols = [desc[0] for desc in _cur.description]
        _rows = _cur.fetchall()
        _data = [dict(zip(_cols, row)) for row in _rows]
        sql_result = mo.ui.table(_data, selection=None) if _data else mo.md("*Query returned no rows.*")
    except Exception as e:
        sql_result = mo.callout(mo.md(f"`{e}`"), kind="danger")

    sql_result
    return


@app.cell
def _():
    import json
    import marimo as mo
    import numpy as np
    import os
    import plotly.graph_objects as go

    return go, json, mo, np, os


if __name__ == "__main__":
    app.run()
