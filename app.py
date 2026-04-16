import marimo

__generated_with = "0.13.0"
app = marimo.App(width="full")


@app.cell
def _(mo):
    mo.md(
        """
        # eth-tracestat

        Interactive explorer for Ethereum storage slot and account access patterns.

        Upload a `results.db` produced by the CLI, or use the bundled demo data.
        """
    )
    return


@app.cell
def _(mo, os):
    _default_path = "data/results.db"
    _has_default = os.path.exists(_default_path)

    file_upload = mo.ui.file(
        filetypes=[".db"],
        label="Upload results.db" if _has_default else "Upload results.db (no bundled data found)",
    )
    file_upload if not _has_default else mo.md(f"Using bundled `{_default_path}` — or upload your own:")
    return (file_upload,)


@app.cell
def _(file_upload, mo, os, sqlite3, tempfile):
    _default_path = "data/results.db"

    if file_upload.value:
        _tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        _tmp.write(file_upload.value[0].contents)
        _tmp.flush()
        _db_path = _tmp.name
    elif os.path.exists(_default_path):
        _db_path = _default_path
    else:
        mo.stop(True, mo.md("**No data.** Upload a `results.db` file above."))
        _db_path = ""

    conn = sqlite3.connect(_db_path)

    _range = conn.execute("SELECT MIN(block_num), MAX(block_num) FROM blocks").fetchone()
    _n_blocks = conn.execute("SELECT COUNT(*) FROM blocks").fetchone()[0]
    _n_txs = conn.execute("SELECT SUM(n_txs) FROM blocks").fetchone()[0] or 0
    _n_storage = conn.execute("SELECT COUNT(*) FROM storage_ops").fetchone()[0]
    _n_calls = conn.execute("SELECT COUNT(*) FROM calls").fetchone()[0]

    block_min, block_max = _range[0], _range[1]

    mo.md(
        f"**Loaded:** {_n_blocks:,} blocks ({block_min:,} – {block_max:,}), "
        f"{_n_txs:,} txs, {_n_storage:,} storage op rows, {_n_calls:,} call rows"
    )
    return block_max, block_min, conn


@app.cell
def _(block_max, block_min, mo):
    block_slider = mo.ui.range_slider(
        start=block_min, stop=block_max, step=1,
        value=[block_min, block_max],
        label="Block range",
        full_width=True,
    )
    dist_picker = mo.ui.dropdown(
        options={
            "N(s,B) — Per-block slot accesses": "sb",
            "N(c,B) — Per-block account calls": "cb",
            "N(s,T) — Per-tx slot accesses": "st",
            "N(c,T) — Per-tx account calls": "ct",
        },
        value="sb",
        label="Distribution",
    )
    contract_filter = mo.ui.text(
        label="Filter by contract", placeholder="0x...",
    )
    mo.hstack([dist_picker, contract_filter], justify="start", gap=1)
    block_slider
    return block_slider, contract_filter, dist_picker


@app.cell
def _(block_slider, conn, contract_filter, dist_picker, mo, plt):
    bmin, bmax = block_slider.value
    cf = contract_filter.value.strip().lower() if contract_filter.value else ""

    queries = {
        "sb": (
            "SELECT op_count AS n, COUNT(*) AS cnt FROM ("
            "  SELECT SUM(sload_count + sstore_count) AS op_count"
            "  FROM storage_ops WHERE block_num BETWEEN ? AND ?"
            + (" AND contract = ?" if cf else "") +
            "  GROUP BY block_num, contract, slot"
            ") GROUP BY n ORDER BY n",
            "N(s,B) — Per-block slot accesses",
            "ops per (contract, slot) in block",
        ),
        "cb": (
            "SELECT call_count AS n, COUNT(*) AS cnt FROM ("
            "  SELECT SUM(call_count) AS call_count"
            "  FROM calls WHERE block_num BETWEEN ? AND ?"
            + (" AND contract = ?" if cf else "") +
            "  GROUP BY block_num, contract"
            ") GROUP BY n ORDER BY n",
            "N(c,B) — Per-block account calls",
            "calls per account in block",
        ),
        "st": (
            "SELECT sload_count + sstore_count AS n, COUNT(*) AS cnt"
            " FROM storage_ops WHERE block_num BETWEEN ? AND ?"
            + (" AND contract = ?" if cf else "") +
            " GROUP BY n ORDER BY n",
            "N(s,T) — Per-tx slot accesses",
            "ops per (tx, contract, slot)",
        ),
        "ct": (
            "SELECT call_count AS n, COUNT(*) AS cnt"
            " FROM calls WHERE block_num BETWEEN ? AND ?"
            + (" AND contract = ?" if cf else "") +
            " GROUP BY n ORDER BY n",
            "N(c,T) — Per-tx account calls",
            "calls per (tx, contract)",
        ),
    }

    sql, title, xlabel = queries[dist_picker.value]
    params = [bmin, bmax] + ([cf] if cf else [])
    rows = conn.execute(sql, params).fetchall()

    if not rows:
        mo.stop(True, mo.md("*No data for this selection.*"))

    ns = [r[0] for r in rows]
    cnts = [r[1] for r in rows]
    total = sum(cnts)
    weighted = sum(n * c for n, c in rows)

    # Stats
    cum = 0
    p50 = p95 = p99 = ns[-1]
    for n, c in rows:
        cum += c
        if p50 == ns[-1] and cum / total >= 0.50:
            p50 = n
        if p95 == ns[-1] and cum / total >= 0.95:
            p95 = n
        if p99 == ns[-1] and cum / total >= 0.99:
            p99 = n

    n1_pct = next((c for n, c in rows if n == 1), 0) / total

    stats_md = (
        f"**Total:** {total:,} | **Mean:** {weighted/total:.2f} | "
        f"**Median:** {p50} | **p95:** {p95} | **p99:** {p99} | **Max:** {ns[-1]} | "
        f"**N=1:** {n1_pct:.1%} | **N≥2:** {1-n1_pct:.1%}"
    )

    # Chart
    fig, ax = plt.subplots(figsize=(14, 4.5))
    max_bins = 60
    if len(ns) > max_bins:
        xs = [str(n) for n in ns[:max_bins-1]] + [f"≥{ns[max_bins-1]}"]
        ys = cnts[:max_bins-1] + [sum(cnts[max_bins-1:])]
    else:
        xs = [str(n) for n in ns]
        ys = cnts

    ax.bar(xs, ys, color="#4a7cbf", edgecolor="#1a3a5a", linewidth=0.5)
    if max(ys) / max(1, min(y for y in ys if y > 0)) > 20:
        ax.set_yscale("log")
    if len(xs) > 25:
        ax.tick_params(axis="x", rotation=60, labelsize=8)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("count")
    ax.set_title(title)
    ax.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()

    mo.vstack([mo.md(stats_md), fig])
    return


@app.cell
def _(mo):
    mo.md("## Top slots and accounts")
    return


@app.cell
def _(block_slider, conn, contract_filter, mo):
    bmin, bmax = block_slider.value
    cf = contract_filter.value.strip().lower() if contract_filter.value else ""

    _where = "WHERE block_num BETWEEN ? AND ?" + (" AND contract = ?" if cf else "")
    _params = [bmin, bmax] + ([cf] if cf else [])

    _slots = conn.execute(
        f"SELECT contract, slot, SUM(sload_count) AS reads, SUM(sstore_count) AS writes, "
        f"SUM(sload_count + sstore_count) AS total "
        f"FROM storage_ops {_where} "
        f"GROUP BY contract, slot ORDER BY total DESC LIMIT 30",
        _params,
    ).fetchall()

    _accts = conn.execute(
        f"SELECT contract, SUM(call_count) AS total, COUNT(DISTINCT block_num) AS blocks "
        f"FROM calls {_where} "
        f"GROUP BY contract ORDER BY total DESC LIMIT 30",
        _params,
    ).fetchall()

    _slot_data = [
        {"contract": r[0], "slot": f"0x{r[1][:16]}…", "SLOADs": r[2], "SSTOREs": r[3], "total": r[4]}
        for r in _slots
    ]
    _acct_data = [
        {"contract": r[0], "total_calls": r[1], "blocks_present": r[2]}
        for r in _accts
    ]

    mo.hstack([
        mo.vstack([
            mo.md("### Top (contract, slot) pairs"),
            mo.ui.table(_slot_data, selection=None) if _slot_data else mo.md("*No data*"),
        ]),
        mo.vstack([
            mo.md("### Top accounts"),
            mo.ui.table(_acct_data, selection=None) if _acct_data else mo.md("*No data*"),
        ]),
    ], widths=[3, 2])
    return


@app.cell
def _(mo):
    mo.md("## SQL explorer")
    return


@app.cell
def _(mo):
    sql_input = mo.ui.text_area(
        label="Custom SQL (tables: blocks, storage_ops, calls)",
        value="SELECT contract, SUM(sload_count + sstore_count) AS total_ops,\n"
              "       SUM(sload_count) AS reads, SUM(sstore_count) AS writes\n"
              "FROM storage_ops\n"
              "GROUP BY contract\n"
              "ORDER BY total_ops DESC\n"
              "LIMIT 20",
        rows=8,
        full_width=True,
    )
    sql_input
    return (sql_input,)


@app.cell
def _(conn, mo, sql_input):
    _query = sql_input.value.strip()
    if not _query:
        mo.stop(True)

    try:
        _rows = conn.execute(_query).fetchall()
        _cols = [desc[0] for desc in conn.execute(_query).description]
        _data = [dict(zip(_cols, row)) for row in _rows]
        mo.ui.table(_data, selection=None) if _data else mo.md("*Query returned no rows.*")
    except Exception as e:
        mo.md(f"**Error:** `{e}`")
    return


@app.cell
def _():
    import marimo as mo
    import matplotlib.pyplot as plt
    import os
    import sqlite3
    import tempfile
    return mo, os, plt, sqlite3, tempfile


if __name__ == "__main__":
    app.run()
