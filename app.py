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
        --cyan-500: #06b6d4;
        --violet-500: #8b5cf6;
        --emerald-500: #10b981;
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

    p, li, td, th, label, span {
        font-size: 0.9rem;
    }

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

    /* SQL explorer — textarea fills space, leaves room for button */
    .sql-col { display: flex; flex-direction: column; height: 100%; }
    .sql-col > :nth-child(2) { flex: 1; overflow: hidden; }
    .sql-col .cm-editor { height: 100% !important; }
    .sql-col .cm-editor .cm-scroller { height: 100% !important; }

    /* Style run button */
    button[data-testid="marimo-plugin-ui-run-button"] {
        background: var(--blue-500) !important;
        color: white !important;
        border: none !important;
        border-radius: 6px !important;
        padding: 8px 24px !important;
        font-family: var(--font-sans) !important;
        font-weight: 500 !important;
        font-size: 0.85rem !important;
        letter-spacing: 0.02em;
        cursor: pointer;
        transition: background 0.15s ease;
    }
    button[data-testid="marimo-plugin-ui-run-button"]:hover {
        background: var(--blue-600) !important;
    }

    /* Clickable section anchors */
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

    .section-desc {
        color: var(--slate-500);
        font-size: 1rem;
        line-height: 1.6;
        margin: 4px 0 12px 0;
    }
    </style>

    <span id="top"></span>

    # Ethereum storage and account access analysis
    """)
    return


@app.cell
def _(mo, os, sqlite3):
    _db_path = "data/results.db"

    if not os.path.exists(_db_path):
        mo.stop(True, mo.callout(mo.md(
            "**No data found.** Run the CLI to populate `data/results.db`:\n\n"
            "```\npython -m eth_tracestat.cli --rpc <url> --start <block> --count 10 "
            "--results-db data/results.db\n```"
        ), kind="danger"))

    conn = sqlite3.connect(_db_path)

    _range = conn.execute("SELECT MIN(block_num), MAX(block_num) FROM blocks").fetchone()
    _n_blocks = conn.execute("SELECT COUNT(*) FROM blocks").fetchone()[0]
    _n_txs = conn.execute("SELECT SUM(n_txs) FROM blocks").fetchone()[0] or 0
    _n_storage = conn.execute("SELECT COUNT(*) FROM storage_ops").fetchone()[0]
    _n_calls = conn.execute("SELECT COUNT(*) FROM calls").fetchone()[0]

    block_min, block_max = _range[0], _range[1]

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

    mo.vstack([
        mo.md(
            '<p class="section-desc">'
            'Ethereum storage slot & account access patterns. '
            'Analysis loaded from <code>data/results.db</code> — '
            'update it by running the CLI with <code>--results-db data/results.db</code>.'
            '</p>'
        ),
        mo.md(
            f'<div style="display: flex; gap: 8px; flex-wrap: wrap;">'
            f'{_sc("Block range", f"{block_min:,} – {block_max:,}")}'
            f'{_sc("Blocks", f"{_n_blocks:,}")}'
            f'{_sc("Transactions", f"{_n_txs:,}")}'
            f'{_sc("Storage Reads/Writes", f"{_n_storage:,}")}'
            f'{_sc("Account Calls", f"{_n_calls:,}")}'
            f'</div>'
        ),
    ], gap=0.5)
    return block_max, block_min, conn


@app.cell
def _(block_max, block_min, conn, mo):
    _all_blocks = [r[0] for r in conn.execute(
        "SELECT block_num FROM blocks ORDER BY block_num"
    ).fetchall()]

    _options = {f"{b:,}": b for b in _all_blocks}

    block_from = mo.ui.dropdown(
        options=_options,
        value=f"{block_min:,}",
        label="From block",
    )
    block_to = mo.ui.dropdown(
        options=_options,
        value=f"{block_max:,}",
        label="To block",
    )

    mo.vstack([
        mo.md(
            '<p class="section-desc" style="margin-bottom: 4px;">'
            'Select the block range to analyze. All distributions, tables, and stats below will update accordingly.</p>'
        ),
        mo.hstack([block_from, block_to], justify="start", gap=0.75),
    ], gap=0.3)
    return block_from, block_to


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## <a id="distributions" href="#distributions" class="anchor-link">Access distributions</a>

    <p class="section-desc" style="margin-bottom: 0;">
    <b>N(x, y)</b> = number of accesses of type <b>x</b> per grouping <b>y</b>, where:
    <b>s</b> = storage slot, <b>a</b> = address, <b>B</b> = block, <b>T</b> = transaction.
    </p>
    """)
    return


@app.cell
def _(block_from, block_to, conn, make_distribution, mo):
    _bmin = block_from.value
    _bmax = block_to.value
    _params = [_bmin, _bmax]

    # Max unique slots/addresses per block and per tx
    _max_slots_block = conn.execute(
        "SELECT MAX(cnt) FROM ("
        "  SELECT COUNT(DISTINCT address || '|' || slot) AS cnt"
        "  FROM storage_ops WHERE block_num BETWEEN ? AND ?"
        "  GROUP BY block_num)", _params
    ).fetchone()[0] or 0

    _max_addrs_block = conn.execute(
        "SELECT MAX(cnt) FROM ("
        "  SELECT COUNT(DISTINCT address) AS cnt"
        "  FROM calls WHERE block_num BETWEEN ? AND ?"
        "  GROUP BY block_num)", _params
    ).fetchone()[0] or 0

    _max_slots_tx = conn.execute(
        "SELECT MAX(cnt) FROM ("
        "  SELECT COUNT(DISTINCT address || '|' || slot) AS cnt"
        "  FROM storage_ops WHERE block_num BETWEEN ? AND ?"
        "  GROUP BY block_num, tx_idx)", _params
    ).fetchone()[0] or 0

    _max_addrs_tx = conn.execute(
        "SELECT MAX(cnt) FROM ("
        "  SELECT COUNT(DISTINCT address) AS cnt"
        "  FROM calls WHERE block_num BETWEEN ? AND ?"
        "  GROUP BY block_num, tx_idx)", _params
    ).fetchone()[0] or 0

    _defs = [
        (
            "SELECT op_count AS n, COUNT(*) AS cnt FROM ("
            "  SELECT SUM(sload_count + sstore_count) AS op_count"
            "  FROM storage_ops WHERE block_num BETWEEN ? AND ?"
            "  GROUP BY block_num, address, slot"
            ") GROUP BY n ORDER BY n",
            "N(s, B)", "Per-block slot accesses",
            "SLOAD+SSTORE ops per (address, slot) per block.",
            ("Max unique slots/block", f"{_max_slots_block:,}"),
        ),
        (
            "SELECT call_count AS n, COUNT(*) AS cnt FROM ("
            "  SELECT SUM(call_count) AS call_count"
            "  FROM calls WHERE block_num BETWEEN ? AND ?"
            "  GROUP BY block_num, address"
            ") GROUP BY n ORDER BY n",
            "N(a, B)", "Per-block account calls",
            "Calls per address per block. Precompiles excluded.",
            ("Max unique addresses/block", f"{_max_addrs_block:,}"),
        ),
        (
            "SELECT sload_count + sstore_count AS n, COUNT(*) AS cnt"
            " FROM storage_ops WHERE block_num BETWEEN ? AND ?"
            " GROUP BY n ORDER BY n",
            "N(s, T)", "Per-tx slot accesses",
            "SLOAD+SSTORE ops per (address, slot) within a single tx.",
            ("Max unique slots/tx", f"{_max_slots_tx:,}"),
        ),
        (
            "SELECT call_count AS n, COUNT(*) AS cnt"
            " FROM calls WHERE block_num BETWEEN ? AND ?"
            " GROUP BY n ORDER BY n",
            "N(a, T)", "Per-tx account calls",
            "Calls to an address within one tx. Precompiles excluded.",
            ("Max unique addresses/tx", f"{_max_addrs_tx:,}"),
        ),
    ]

    _sections = []
    for _i, (_sql, _code, _title, _desc, _extra) in enumerate(_defs):
        _rows = conn.execute(_sql, _params).fetchall()
        if _i > 0:
            _sections.append(mo.md('<hr style="border: none; border-top: 1px solid #e2e8f0; margin: 8px 0;">'))
        _sections.append(make_distribution(_rows, _code, _title, _desc, _extra))

    # Per-block breakdown
    _block_rows = conn.execute(
        "SELECT b.block_num, b.n_txs,"
        "  (SELECT COUNT(DISTINCT s.address || '|' || s.slot) FROM storage_ops s WHERE s.block_num = b.block_num) AS unique_slots,"
        "  (SELECT COUNT(DISTINCT c.address) FROM calls c WHERE c.block_num = b.block_num) AS unique_addrs"
        " FROM blocks b WHERE b.block_num BETWEEN ? AND ? ORDER BY b.block_num",
        _params,
    ).fetchall()
    _block_data = [
        {"block": r[0], "txs": r[1], "unique_slots": r[2], "unique_addresses": r[3]}
        for r in _block_rows
    ]

    _sections.append(
        mo.accordion({
            f"Per-block breakdown ({len(_block_data)} blocks)": mo.ui.table(
                _block_data,
                selection=None,
                pagination=False,
                show_column_summaries=False,
                show_data_types=False,
                show_download=False,
            ) if _block_data else mo.md("*No data*"),
        })
    )

    mo.vstack(_sections, gap=1)
    return


@app.cell
def _(go, mo, np):
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

    def make_distribution(rows, code, title, desc, extra_stat=None):
        if not rows:
            return mo.callout(mo.md(f"**{code}** — no data for this selection."), kind="warn")

        ns = np.array([r[0] for r in rows])
        cnts = np.array([r[1] for r in rows])
        total = int(cnts.sum())
        weighted = int((ns * cnts).sum())
        cdf = np.cumsum(cnts) / total

        p50 = int(ns[np.searchsorted(cdf, 0.50)])
        n1_cnt = int(cnts[ns == 1].sum()) if 1 in ns else 0
        n1_pct = n1_cnt / total

        cards = [
            ("Total", f"{total:,}"),
            ("Mean", f"{weighted/total:.2f}"),
            ("Median", str(p50)),
            ("Max N", f"{int(ns[-1]):,}"),
            ("N=1", f"{n1_pct:.1%}"),
            ("N>=2", f"{1-n1_pct:.1%}"),
        ]
        if extra_stat:
            cards.append(extra_stat)

        stats = mo.md(
            f'<div style="display: flex; gap: 8px; padding: 0 56px; flex-wrap: wrap;">'
            f'{"".join(_stat_card(l, v) for l, v in cards)}'
            f'</div>'
        )

        max_bins = 50
        if len(ns) > max_bins:
            cap = int(ns[max_bins - 1])
            display_cnts = list(cnts[:max_bins - 1]) + [int(cnts[max_bins - 1:].sum())]
            labels = [str(int(n)) for n in ns[:max_bins - 1]] + [f"\u2265{cap}"]
        else:
            display_cnts = list(cnts)
            labels = [str(int(n)) for n in ns]

        pcts = [f"{c / total:.1%}" for c in display_cnts]
        use_log = max(display_cnts) / max(1, min(c for c in display_cnts if c > 0)) > 20

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=labels,
            y=display_cnts,
            marker_color=CHART_COLOR,
            marker_line_width=0,
            marker_opacity=0.85,
            customdata=pcts,
            hovertemplate=(
                "<b>N = %{x}</b><br>"
                "Count: %{y:,}<br>"
                "Share: %{customdata}"
                "<extra></extra>"
            ),
        ))

        fig.update_layout(
            font=dict(family="Inter, system-ui, sans-serif", size=12, color="#475569"),
            height=250,
            margin=dict(l=60, r=60, t=6, b=44),
            xaxis=dict(
                title=dict(text="N", font=dict(size=11, color="#94a3b8")),
                tickangle=-45 if len(labels) > 25 else 0,
                tickfont=dict(size=10, family="JetBrains Mono, monospace"),
                showline=True,
                linewidth=1,
                linecolor="#e2e8f0",
                zeroline=False,
            ),
            yaxis=dict(
                title=dict(text="Frequency", font=dict(size=11, color="#94a3b8")),
                type="log" if use_log else "linear",
                tickfont=dict(size=10),
                showline=False,
                gridcolor="#f1f5f9",
                zeroline=False,
            ),
            plot_bgcolor="white",
            paper_bgcolor="white",
            bargap=0.2,
            hoverlabel=dict(
                bgcolor="white",
                bordercolor="#e2e8f0",
                font=dict(size=12, family="Inter, sans-serif", color="#0f172a"),
            ),
        )
        fig.update_xaxes(gridcolor="rgba(0,0,0,0)")

        _anchor = code.lower().replace("(", "").replace(")", "").replace(", ", "-").replace(" ", "")
        header = mo.md(
            f'### <a id="{_anchor}" href="#{_anchor}" class="anchor-link">{code} — {title}</a>\n'
            f'<p class="section-desc">{desc}</p>'
        )

        return mo.vstack([header, stats, fig], gap=0.4)

    return (make_distribution,)


@app.cell
def _(mo):
    mo.md("""
    <hr style="border: none; border-top: 2px solid #e2e8f0; margin: 16px 0;">
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## <a id="top-slots-accounts" href="#top-slots-accounts" class="anchor-link">Top slots & accounts</a>

    <p class="section-desc">Ranked by total ops/calls across the selected block range.</p>
    """)
    return


@app.cell
def _(block_from, block_to, conn, mo):
    _bmin = block_from.value
    _bmax = block_to.value

    _where = "WHERE block_num BETWEEN ? AND ?"
    _params = [_bmin, _bmax]

    _slots = conn.execute(
        f"SELECT address, slot, SUM(sload_count) AS reads, SUM(sstore_count) AS writes, "
        f"SUM(sload_count + sstore_count) AS total "
        f"FROM storage_ops {_where} "
        f"GROUP BY address, slot ORDER BY total DESC LIMIT 30",
        _params,
    ).fetchall()

    _accts = conn.execute(
        f"SELECT address, SUM(call_count) AS total, COUNT(DISTINCT block_num) AS blocks "
        f"FROM calls {_where} "
        f"GROUP BY address ORDER BY total DESC LIMIT 30",
        _params,
    ).fetchall()

    _slot_data = [
        {"address": r[0], "slot": f"0x{r[1][:16]}...", "SLOADs": r[2], "SSTOREs": r[3], "total": r[4]}
        for r in _slots
    ]
    _acct_data = [
        {"address": r[0], "total_calls": r[1], "blocks_present": r[2]}
        for r in _accts
    ]

    mo.hstack([
        mo.vstack([
            mo.md('<span class="section-label" style="background: #3b82f618; color: #3b82f6;">STORAGE SLOTS</span>'),
            mo.ui.table(_slot_data, selection=None) if _slot_data else mo.md("*No data*"),
        ]),
        mo.vstack([
            mo.md('<span class="section-label" style="background: #06b6d418; color: #06b6d4;">ACCOUNTS</span>'),
            mo.ui.table(_acct_data, selection=None) if _acct_data else mo.md("*No data*"),
        ]),
    ], widths=[3, 2])
    return


@app.cell
def _(mo):
    mo.md("""
    <hr style="border: none; border-top: 2px solid #e2e8f0; margin: 16px 0;">
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## <a id="sql-explorer" href="#sql-explorer" class="anchor-link">SQL explorer</a>

    <p class="section-desc">
    Write custom SQL queries against the raw trace data.
    Use this to answer questions the charts above don't cover —
    filter by address, find the heaviest transactions, compare read/write ratios, etc.
    </p>
    """)
    return


@app.cell
def _(mo):
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
        mo.ui.table(
            _schema_data,
            selection=None,
            pagination=False,
            show_column_summaries=False,
            show_data_types=False,
            show_download=False,
        ),
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
    return run_button, sql_input


@app.cell
def _(conn, mo, run_button, sql_input):
    mo.stop(not run_button.value)

    _query = sql_input.value.strip()
    if not _query:
        mo.stop(True, mo.md("*Enter a query above.*"))

    try:
        _cur = conn.execute(_query)
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
    import marimo as mo
    import numpy as np
    import os
    import plotly.graph_objects as go
    import sqlite3

    return go, mo, np, os, sqlite3


if __name__ == "__main__":
    app.run()
