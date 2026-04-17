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
            _distinct_expr = "address || '|' || slot" if 's' in _key else 'address'
            _table_name = 'storage_ops' if 's' in _key else 'calls'
            _group_by = 'block_num' if 'b' in _key else 'block_num, tx_idx'
            _extra_val = local_conn.execute(
                f"SELECT MAX(cnt) FROM (SELECT COUNT(DISTINCT {_distinct_expr})"
                f" AS cnt FROM {_table_name}"
                f" WHERE block_num BETWEEN ? AND ?"
                f" GROUP BY {_group_by})",
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
def _(mo):
    mo.md("""
    ## <a id="warm-rate" href="#warm-rate" class="anchor-link">Phase 1 — Warm rate</a>

    <p class="section-desc">
    A storage access is <b>warm</b> if the same <code>(address, slot)</code> was already touched
    earlier in the same block. <b>Warm rate</b> = warm accesses / total accesses per block.
    </p>
    """)
    return


@app.cell
def _(block_from, block_to, is_local, local_conn, mo, static_data):
    if not is_local:
        _warm_data = static_data.get("warm_analysis", {}).get("per_block_warm", []) if static_data else []
    else:
        _bmin_w, _bmax_w = block_from.value, block_to.value
        _warm_data_raw = local_conn.execute("""
            SELECT
                block_num,
                SUM(sload_count + sstore_count)            AS T,
                COUNT(*)                                   AS U_tx,
                COUNT(DISTINCT address || '|' || slot)     AS U_block
            FROM storage_ops
            WHERE block_num BETWEEN ? AND ?
            GROUP BY block_num
            ORDER BY block_num
        """, [_bmin_w, _bmax_w]).fetchall()
        _warm_data = []
        for _blk, _T, _U_tx, _U_block in _warm_data_raw:
            if _T == 0:
                continue
            _warm_data.append({
                "block": _blk, "T": _T, "U_tx": _U_tx, "U_block": _U_block,
                "within_warm": _T - _U_tx,
                "cross_warm": _U_tx - _U_block,
                "warm_rate": (_T - _U_block) / _T,
                "within_rate": (_T - _U_tx) / _T,
                "cross_rate": (_U_tx - _U_block) / _T,
            })

    if not _warm_data:
        mo.callout(mo.md("**No warm-rate data.** Run locally with results.db populated."), kind="warn")
    else:
        import plotly.graph_objects as _go2
        _rates = [d["warm_rate"] for d in _warm_data]
        _mean_wr = sum(_rates) / len(_rates)
        _min_wr = min(_rates)
        _max_wr = max(_rates)
        _sorted_rates = sorted(_rates)
        _p50_wr = _sorted_rates[len(_sorted_rates) // 2]

        def _sc2(label, value):
            return (
                f'<div style="flex: 1; min-width: 100px; background: #f8fafc; '
                f'border-radius: 6px; padding: 8px 12px; text-align: center;">'
                f'<div style="font-size: 0.7rem; font-weight: 600; text-transform: uppercase; '
                f'letter-spacing: 0.05em; color: #94a3b8; margin-bottom: 2px;">{label}</div>'
                f'<div style="font-size: 1rem; font-weight: 600; color: #1e293b; '
                f'font-variant-numeric: tabular-nums;">{value}</div>'
                f'</div>'
            )

        _stats_html = (
            f'<div style="display: flex; gap: 8px; flex-wrap: wrap;">'
            f'{_sc2("Blocks", str(len(_warm_data)))}'
            f'{_sc2("Mean warm rate", f"{_mean_wr:.3f}")}'
            f'{_sc2("Median warm rate", f"{_p50_wr:.3f}")}'
            f'{_sc2("Min", f"{_min_wr:.3f}")}'
            f'{_sc2("Max", f"{_max_wr:.3f}")}'
            f'</div>'
        )

        _fig1 = _go2.Figure()
        _fig1.add_trace(_go2.Histogram(
            x=_rates, nbinsx=30,
            marker_color="#3b82f6", opacity=0.85,
        ))
        _fig1.update_layout(
            xaxis_title="Warm rate (warm accesses / total accesses)",
            yaxis_title="Number of blocks",
            bargap=0.04, template="plotly_white", showlegend=False,
            font=dict(family="Inter, system-ui, sans-serif", size=12, color="#475569"),
            height=280, margin=dict(l=60, r=60, t=10, b=44),
            plot_bgcolor="white", paper_bgcolor="white",
        )

        mo.vstack([mo.md(_stats_html), _fig1], gap=0.6)
    return


@app.cell
def _(mo):
    mo.md('<hr style="border: none; border-top: 2px solid #e2e8f0; margin: 16px 0;">')
    return


@app.cell
def _(mo):
    mo.md("""
    ## <a id="warm-decomposition" href="#warm-decomposition" class="anchor-link">Phase 2 — Decomposition</a>

    <p class="section-desc">
    Warm accesses split into two components:<br>
    <b>Within-tx warm</b> — repeat access to a slot already touched earlier <i>in the same transaction</i> (already priced cheaply by EIP-2929).<br>
    <b>Cross-tx warm</b> — first access in a transaction to a slot already touched by an <i>earlier transaction</i> in the same block (the EIP-7863 opportunity).
    </p>
    """)
    return


@app.cell
def _(block_from, block_to, is_local, local_conn, mo, static_data):
    if not is_local:
        _wd2 = static_data.get("warm_analysis", {}).get("per_block_warm", []) if static_data else []
    else:
        _bmin_d, _bmax_d = block_from.value, block_to.value
        _rows_d = local_conn.execute("""
            SELECT
                block_num,
                SUM(sload_count + sstore_count)            AS T,
                COUNT(*)                                   AS U_tx,
                COUNT(DISTINCT address || '|' || slot)     AS U_block
            FROM storage_ops
            WHERE block_num BETWEEN ? AND ?
            GROUP BY block_num
            ORDER BY block_num
        """, [_bmin_d, _bmax_d]).fetchall()
        _wd2 = []
        for _blk2, _T2, _U_tx2, _U_block2 in _rows_d:
            if _T2 == 0:
                continue
            _wd2.append({
                "block": _blk2, "T": _T2,
                "within_rate": (_T2 - _U_tx2) / _T2,
                "cross_rate": (_U_tx2 - _U_block2) / _T2,
                "warm_rate": (_T2 - _U_block2) / _T2,
            })

    if not _wd2:
        mo.callout(mo.md("**No decomposition data.** Run locally with results.db populated."), kind="warn")
    else:
        import plotly.graph_objects as _go3
        _sorted_wd2 = sorted(_wd2, key=lambda d: d["warm_rate"])
        _blk_labels = [str(d["block"]) for d in _sorted_wd2]
        _within_vals = [d["within_rate"] for d in _sorted_wd2]
        _cross_vals = [d["cross_rate"] for d in _sorted_wd2]

        _mean_within = sum(_within_vals) / len(_within_vals)
        _mean_cross = sum(_cross_vals) / len(_cross_vals)
        _mean_total = _mean_within + _mean_cross

        def _sc3(label, value, color="#1e293b"):
            return (
                f'<div style="flex: 1; min-width: 100px; background: #f8fafc; '
                f'border-radius: 6px; padding: 8px 12px; text-align: center;">'
                f'<div style="font-size: 0.7rem; font-weight: 600; text-transform: uppercase; '
                f'letter-spacing: 0.05em; color: #94a3b8; margin-bottom: 2px;">{label}</div>'
                f'<div style="font-size: 1rem; font-weight: 600; color: {color}; '
                f'font-variant-numeric: tabular-nums;">{value}</div>'
                f'</div>'
            )

        _stats2 = mo.md(
            f'<div style="display: flex; gap: 8px; flex-wrap: wrap;">'
            f'{_sc3("Mean total warm", f"{_mean_total:.3f}")}'
            f'{_sc3("Mean within-tx", f"{_mean_within:.3f}", "#3b82f6")}'
            f'{_sc3("Mean cross-tx", f"{_mean_cross:.3f}", "#f59e0b")}'
            f'{_sc3("Cross / total warm", f"{_mean_cross / _mean_total:.1%}" if _mean_total else "—")}'
            f'</div>'
        )

        _fig2 = _go3.Figure()
        _fig2.add_trace(_go3.Bar(
            name="Within-tx warm (EIP-2929)",
            x=_blk_labels, y=_within_vals,
            marker_color="#3b82f6",
        ))
        _fig2.add_trace(_go3.Bar(
            name="Cross-tx warm (EIP-7863 opportunity)",
            x=_blk_labels, y=_cross_vals,
            marker_color="#f59e0b",
        ))
        _fig2.update_layout(
            barmode="stack",
            xaxis_title="Block (sorted by total warm rate ↑)",
            yaxis_title="Share of total accesses",
            xaxis=dict(showticklabels=False),
            template="plotly_white",
            font=dict(family="Inter, system-ui, sans-serif", size=12, color="#475569"),
            height=300, margin=dict(l=60, r=60, t=10, b=44),
            plot_bgcolor="white", paper_bgcolor="white",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )

        mo.vstack([_stats2, _fig2], gap=0.6)
    return


@app.cell
def _(mo):
    mo.md('<hr style="border: none; border-top: 2px solid #e2e8f0; margin: 16px 0;">')
    return


@app.cell
def _(mo):
    mo.md("""
    ## <a id="concentration" href="#concentration" class="anchor-link">Phase 3 — Concentration</a>

    <p class="section-desc">
    How concentrated is storage reuse? <b>Unique slot ratio</b> = unique (address, slot) pairs / total accesses per block —
    a low ratio means heavy reuse on fewer slots. The frequency distribution shows how many slot-block pairs
    are accessed exactly once, twice, etc. (pooled across all blocks).
    </p>
    """)
    return


@app.cell
def _(block_from, block_to, is_local, local_conn, mo, static_data):
    if not is_local:
        _conc_data = static_data.get("warm_analysis", {}).get("per_block_concentration", []) if static_data else []
        _freq_pool = static_data.get("warm_analysis", {}).get("access_frequency_pool", {}) if static_data else {}
        _warm_for_scatter = static_data.get("warm_analysis", {}).get("per_block_warm", []) if static_data else []
    else:
        _bmin_c, _bmax_c = block_from.value, block_to.value

        _totals_c = {
            row[0]: (row[1], row[2])
            for row in local_conn.execute("""
                SELECT block_num,
                       SUM(sload_count + sstore_count) AS T,
                       COUNT(DISTINCT address || '|' || slot) AS U_block
                FROM storage_ops
                WHERE block_num BETWEEN ? AND ?
                GROUP BY block_num
            """, [_bmin_c, _bmax_c]).fetchall()
        }

        from collections import defaultdict as _dd
        _slot_cnts = _dd(list)
        for _row_c in local_conn.execute("""
            SELECT block_num, SUM(sload_count + sstore_count) AS n
            FROM storage_ops
            WHERE block_num BETWEEN ? AND ?
            GROUP BY block_num, address, slot
            ORDER BY block_num, n DESC
        """, [_bmin_c, _bmax_c]).fetchall():
            _slot_cnts[_row_c[0]].append(_row_c[1])

        _conc_data = []
        for _bn_c, (_T_c, _U_c) in sorted(_totals_c.items()):
            if _T_c == 0:
                continue
            _cnts_c = _slot_cnts[_bn_c]
            _conc_data.append({
                "block": _bn_c, "T": _T_c, "U_block": _U_c,
                "unique_ratio": _U_c / _T_c,
                "top10_share": sum(_cnts_c[:10]) / _T_c,
                "top50_share": sum(_cnts_c[:50]) / _T_c,
            })

        _freq_rows = local_conn.execute("""
            SELECT SUM(sload_count + sstore_count) AS n
            FROM storage_ops
            WHERE block_num BETWEEN ? AND ?
            GROUP BY block_num, address, slot
        """, [_bmin_c, _bmax_c]).fetchall()
        _freq_pool = {"1": 0, "2": 0, "3-5": 0, "6-10": 0, "11+": 0}
        for (_fn,) in _freq_rows:
            if _fn == 1:
                _freq_pool["1"] += 1
            elif _fn == 2:
                _freq_pool["2"] += 1
            elif _fn <= 5:
                _freq_pool["3-5"] += 1
            elif _fn <= 10:
                _freq_pool["6-10"] += 1
            else:
                _freq_pool["11+"] += 1

        _warm_rows_c = local_conn.execute("""
            SELECT block_num,
                   SUM(sload_count + sstore_count) AS T,
                   COUNT(DISTINCT address || '|' || slot) AS U_block
            FROM storage_ops
            WHERE block_num BETWEEN ? AND ?
            GROUP BY block_num
        """, [_bmin_c, _bmax_c]).fetchall()
        _warm_for_scatter = [
            {"block": r[0], "warm_rate": (r[1] - r[2]) / r[1]}
            for r in _warm_rows_c if r[1] > 0
        ]

    if not _conc_data:
        mo.callout(mo.md("**No concentration data.** Run locally with results.db populated."), kind="warn")
    else:
        import plotly.graph_objects as _go4

        _ratios = [d["unique_ratio"] for d in _conc_data]
        _mean_ratio = sum(_ratios) / len(_ratios)
        _top10_mean = sum(d["top10_share"] for d in _conc_data) / len(_conc_data)
        _top50_mean = sum(d["top50_share"] for d in _conc_data) / len(_conc_data)

        def _sc4(label, value):
            return (
                f'<div style="flex: 1; min-width: 100px; background: #f8fafc; '
                f'border-radius: 6px; padding: 8px 12px; text-align: center;">'
                f'<div style="font-size: 0.7rem; font-weight: 600; text-transform: uppercase; '
                f'letter-spacing: 0.05em; color: #94a3b8; margin-bottom: 2px;">{label}</div>'
                f'<div style="font-size: 1rem; font-weight: 600; color: #1e293b; '
                f'font-variant-numeric: tabular-nums;">{value}</div>'
                f'</div>'
            )

        _stats3 = mo.md(
            f'<div style="display: flex; gap: 8px; flex-wrap: wrap;">'
            f'{_sc4("Mean unique ratio", f"{_mean_ratio:.3f}")}'
            f'{_sc4("Mean top-10 share", f"{_top10_mean:.1%}")}'
            f'{_sc4("Mean top-50 share", f"{_top50_mean:.1%}")}'
            f'</div>'
        )

        # Unique ratio histogram
        _fig_hist = _go4.Figure()
        _fig_hist.add_trace(_go4.Histogram(
            x=_ratios, nbinsx=30,
            marker_color="#8b5cf6", opacity=0.85,
        ))
        _fig_hist.update_layout(
            xaxis_title="Unique slots / total accesses",
            yaxis_title="Number of blocks",
            bargap=0.04, template="plotly_white", showlegend=False,
            font=dict(family="Inter, system-ui, sans-serif", size=12, color="#475569"),
            height=240, margin=dict(l=60, r=60, t=10, b=44),
            plot_bgcolor="white", paper_bgcolor="white",
        )

        # Unique ratio vs warm rate scatter
        _warm_map = {d["block"]: d["warm_rate"] for d in _warm_for_scatter}
        _scatter_x, _scatter_y, _scatter_lbl = [], [], []
        for _d3 in _conc_data:
            if _d3["block"] in _warm_map:
                _scatter_x.append(_d3["unique_ratio"])
                _scatter_y.append(_warm_map[_d3["block"]])
                _scatter_lbl.append(str(_d3["block"]))

        _fig_scat = _go4.Figure()
        _fig_scat.add_trace(_go4.Scatter(
            x=_scatter_x, y=_scatter_y, mode="markers",
            marker=dict(color="#8b5cf6", opacity=0.6, size=7),
            text=_scatter_lbl,
            hovertemplate="Block %{text}<br>Unique ratio: %{x:.3f}<br>Warm rate: %{y:.3f}<extra></extra>",
        ))
        _fig_scat.update_layout(
            xaxis_title="Unique slots / total accesses",
            yaxis_title="Warm rate",
            template="plotly_white",
            font=dict(family="Inter, system-ui, sans-serif", size=12, color="#475569"),
            height=240, margin=dict(l=60, r=60, t=10, b=44),
            plot_bgcolor="white", paper_bgcolor="white",
        )

        # Access frequency bar (log scale)
        _freq_keys = ["1", "2", "3-5", "6-10", "11+"]
        _freq_vals = [_freq_pool.get(k, 0) for k in _freq_keys]
        _fig_freq = _go4.Figure()
        _fig_freq.add_trace(_go4.Bar(
            x=_freq_keys, y=_freq_vals,
            marker_color="#10b981", opacity=0.85,
        ))
        _fig_freq.update_layout(
            xaxis_title="Accesses per (block, address, slot)",
            yaxis_title="Slot-block pairs (log scale)",
            yaxis_type="log",
            template="plotly_white", showlegend=False,
            font=dict(family="Inter, system-ui, sans-serif", size=12, color="#475569"),
            height=240, margin=dict(l=60, r=60, t=10, b=44),
            plot_bgcolor="white", paper_bgcolor="white",
        )

        mo.vstack([
            _stats3,
            mo.hstack([
                mo.vstack([
                    mo.md('<span class="section-label" style="background: #8b5cf618; color: #8b5cf6;">Unique slot ratio histogram</span>'),
                    _fig_hist,
                ]),
                mo.vstack([
                    mo.md('<span class="section-label" style="background: #8b5cf618; color: #8b5cf6;">Unique ratio vs warm rate</span>'),
                    _fig_scat,
                ]),
            ]),
            mo.vstack([
                mo.md('<span class="section-label" style="background: #10b98118; color: #10b981;">Access frequency distribution (pooled, log scale)</span>'),
                _fig_freq,
            ]),
        ], gap=0.6)
    return


@app.cell
def _(mo):
    mo.md('<hr style="border: none; border-top: 2px solid #e2e8f0; margin: 16px 0;">')
    return


@app.cell
def _(mo):
    mo.md("""
    ## <a id="contract-attribution" href="#contract-attribution" class="anchor-link">Phase 4 — Contract attribution</a>

    <p class="section-desc">
    Which contracts drive the most warm accesses? Per contract:
    <b>warm accesses</b> = total accesses − unique (address, slot) pairs, summed across all blocks.
    </p>
    """)
    return


@app.cell
def _(block_from, block_to, is_local, local_conn, mo, static_data):
    if not is_local:
        _ca_data = static_data.get("warm_analysis", {}).get("warm_by_contract", []) if static_data else []
    else:
        _bmin_ca, _bmax_ca = block_from.value, block_to.value
        _ca_rows = local_conn.execute("""
            SELECT
                address,
                SUM(total_access)                         AS total_accesses,
                SUM(unique_slots)                         AS cold_accesses,
                SUM(total_access - unique_slots)          AS warm_accesses,
                COUNT(DISTINCT block_num)                 AS blocks_present
            FROM (
                SELECT block_num, address,
                       SUM(sload_count + sstore_count)    AS total_access,
                       COUNT(DISTINCT slot)               AS unique_slots
                FROM storage_ops
                WHERE block_num BETWEEN ? AND ?
                GROUP BY block_num, address
            ) sub
            GROUP BY address
            ORDER BY warm_accesses DESC
        """, [_bmin_ca, _bmax_ca]).fetchall()
        _ca_data = [
            {
                "address": r[0],
                "total_accesses": r[1],
                "cold_accesses": r[2],
                "warm_accesses": r[3],
                "blocks_present": r[4],
                "short_addr": r[0][:6] + "…" + r[0][-4:],
            }
            for r in _ca_rows if r[3] and r[3] > 0
        ]

    if not _ca_data:
        mo.callout(mo.md("**No contract attribution data.** Run locally with results.db populated."), kind="warn")
    else:
        import plotly.graph_objects as _go5

        _top_n = min(20, len(_ca_data))
        _top = _ca_data[:_top_n]
        _total_warm_ca = sum(d["warm_accesses"] for d in _ca_data)

        def _sc5(label, value):
            return (
                f'<div style="flex: 1; min-width: 100px; background: #f8fafc; '
                f'border-radius: 6px; padding: 8px 12px; text-align: center;">'
                f'<div style="font-size: 0.7rem; font-weight: 600; text-transform: uppercase; '
                f'letter-spacing: 0.05em; color: #94a3b8; margin-bottom: 2px;">{label}</div>'
                f'<div style="font-size: 1rem; font-weight: 600; color: #1e293b; '
                f'font-variant-numeric: tabular-nums;">{value}</div>'
                f'</div>'
            )

        _top5_warm = sum(d["warm_accesses"] for d in _ca_data[:5])
        _top10_warm = sum(d["warm_accesses"] for d in _ca_data[:10])

        _stats4 = mo.md(
            f'<div style="display: flex; gap: 8px; flex-wrap: wrap;">'
            f'{_sc5("Total warm accesses", f"{_total_warm_ca:,}")}'
            f'{_sc5("Top-5 share", f"{_top5_warm / _total_warm_ca:.1%}" if _total_warm_ca else "—")}'
            f'{_sc5("Top-10 share", f"{_top10_warm / _total_warm_ca:.1%}" if _total_warm_ca else "—")}'
            f'{_sc5("Unique contracts", str(len(_ca_data)))}'
            f'</div>'
        )

        # Horizontal bar — top N contracts
        _fig_bar = _go5.Figure()
        _fig_bar.add_trace(_go5.Bar(
            x=[d["warm_accesses"] for d in _top],
            y=[d["short_addr"] for d in _top],
            orientation="h",
            marker_color="#3b82f6", opacity=0.85,
            hovertemplate="%{y}<br>Warm accesses: %{x:,}<extra></extra>",
        ))
        _fig_bar.update_layout(
            xaxis_title="Total warm accesses (across selected blocks)",
            yaxis=dict(autorange="reversed"),
            template="plotly_white", showlegend=False,
            font=dict(family="Inter, system-ui, sans-serif", size=12, color="#475569"),
            height=max(320, _top_n * 26),
            margin=dict(l=120, r=60, t=10, b=44),
            plot_bgcolor="white", paper_bgcolor="white",
        )

        # Treemap — top-5 / top-10 / rest
        _rest_warm = _total_warm_ca - _top10_warm
        _tm_labels = (
            ["All", "Top 5", "Top 6–10", "Rest"]
            + [d["short_addr"] for d in _ca_data[:5]]
            + [d["short_addr"] for d in _ca_data[5:10]]
            + ["Everything else"]
        )
        _tm_parents = (
            ["", "All", "All", "All"]
            + ["Top 5"] * 5
            + ["Top 6–10"] * min(5, len(_ca_data) - 5)
            + ["Rest"]
        )
        _tm_values = (
            [_total_warm_ca, _top5_warm, _top10_warm - _top5_warm, _rest_warm]
            + [d["warm_accesses"] for d in _ca_data[:5]]
            + [d["warm_accesses"] for d in _ca_data[5:10]]
            + [_rest_warm]
        )

        _fig_tree = _go5.Figure(_go5.Treemap(
            labels=_tm_labels,
            parents=_tm_parents,
            values=_tm_values,
            branchvalues="total",
            marker=dict(colorscale="Blues"),
            textinfo="label+percent parent",
        ))
        _fig_tree.update_layout(
            template="plotly_white",
            font=dict(family="Inter, system-ui, sans-serif", size=12),
            height=380, margin=dict(t=10, l=10, r=10, b=10),
        )

        mo.vstack([
            _stats4,
            mo.vstack([
                mo.md('<span class="section-label" style="background: #3b82f618; color: #3b82f6;">Top contracts by warm access contribution</span>'),
                _fig_bar,
            ]),
            mo.vstack([
                mo.md('<span class="section-label" style="background: #3b82f618; color: #3b82f6;">Warm access share — top 5 / top 10 / rest</span>'),
                _fig_tree,
            ]),
        ], gap=0.6)
    return


@app.cell
def _(mo):
    mo.md('<hr style="border: none; border-top: 2px solid #e2e8f0; margin: 16px 0;">')
    return


@app.cell
def _(is_local, local_conn, mo):
    if not is_local:
        _sql_content = mo.md("""
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
        sql_input = None
        run_button = None
    else:
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

        _sql_content = mo.vstack([
            mo.md("""
            ## <a id="sql-explorer" href="#sql-explorer" class="anchor-link">SQL explorer</a>

            <p class="section-desc">
            Write custom SQL queries against the raw trace data.
            Use this to answer questions the charts above don't cover —
            filter by address, find the heaviest transactions, compare read/write ratios, etc.
            </p>
            """),
            mo.hstack([
                _schema,
                mo.md(
                    '<div class="sql-col">'
                    '<span class="section-label" style="background: #3b82f618; color: #3b82f6; margin-bottom: 6px;">Custom query</span>'
                    f'{mo.as_html(sql_input).text}'
                    f'<div style="display:flex; justify-content:flex-start; margin-top: 6px;">{mo.as_html(run_button).text}</div>'
                    '</div>'
                ),
            ], widths=[1, 3], align="stretch"),
        ])
    _sql_content
    return local_conn, run_button, sql_input


@app.cell
def _(is_local, local_conn, mo, run_button, sql_input):
    if is_local:
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
