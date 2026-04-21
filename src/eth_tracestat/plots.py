"""Plotly figure builders for warm-rate analysis (Phases 1-4)."""

import plotly.graph_objects as go
import plotly.express as px

WARM_RATE_REFERENCE = 0.642

# Colour palette consistent with the existing app style
C_WITHIN = "#3b82f6"   # blue
C_CROSS = "#f59e0b"    # amber
C_COLD = "#e2e8f0"     # slate-200


# ---------------------------------------------------------------------------
# Phase 1
# ---------------------------------------------------------------------------

def fig_warm_hist(df_warm: list[dict]) -> go.Figure:
    """Histogram of warm rate across blocks (Phase 1)."""
    rates = [d["warm_rate"] for d in df_warm]
    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=rates,
        nbinsx=30,
        marker_color=C_WITHIN,
        opacity=0.85,
        name="warm rate",
    ))
    fig.update_layout(
        title="Phase 1 — Warm Rate Distribution Across Blocks",
        xaxis_title="Warm rate (warm accesses / total accesses)",
        yaxis_title="Number of blocks",
        bargap=0.04,
        template="plotly_white",
        showlegend=False,
    )
    return fig


# ---------------------------------------------------------------------------
# Phase 2
# ---------------------------------------------------------------------------

def fig_warm_stacked_bar(df_warm: list[dict]) -> go.Figure:
    """Stacked bar: within-tx vs cross-tx warm rate per block, sorted by total warm rate."""
    sorted_data = sorted(df_warm, key=lambda d: d["warm_rate"])
    blocks = [str(d["block"]) for d in sorted_data]
    within = [d["within_rate"] for d in sorted_data]
    cross = [d["cross_rate"] for d in sorted_data]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Within-tx warm (EIP-2929)",
        x=blocks,
        y=within,
        marker_color=C_WITHIN,
    ))
    fig.add_trace(go.Bar(
        name="Cross-tx warm (EIP-7863 opportunity)",
        x=blocks,
        y=cross,
        marker_color=C_CROSS,
    ))
    fig.update_layout(
        barmode="stack",
        title="Phase 2 — Warm Rate Decomposition per Block (sorted by total warm rate)",
        xaxis_title="Block (sorted by warm rate)",
        yaxis_title="Share of total accesses",
        xaxis=dict(showticklabels=False),
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


# ---------------------------------------------------------------------------
# Phase 3
# ---------------------------------------------------------------------------

def fig_unique_ratio_hist(df_conc: list[dict]) -> go.Figure:
    """Histogram of unique-slot ratio across blocks (Phase 3)."""
    ratios = [d["unique_ratio"] for d in df_conc]
    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=ratios,
        nbinsx=30,
        marker_color="#8b5cf6",
        opacity=0.85,
    ))
    fig.update_layout(
        title="Phase 3 — Unique Slot Ratio Distribution",
        xaxis_title="Unique slots / total accesses",
        yaxis_title="Number of blocks",
        bargap=0.04,
        template="plotly_white",
        showlegend=False,
    )
    return fig


def fig_unique_vs_warm_scatter(df_warm: list[dict], df_conc: list[dict]) -> go.Figure:
    """Scatter: unique-slot ratio vs warm rate (Phase 3)."""
    warm_by_block = {d["block"]: d["warm_rate"] for d in df_warm}
    xs, ys, labels = [], [], []
    for d in df_conc:
        b = d["block"]
        if b in warm_by_block:
            xs.append(d["unique_ratio"])
            ys.append(warm_by_block[b])
            labels.append(str(b))

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=xs,
        y=ys,
        mode="markers",
        marker=dict(color="#8b5cf6", opacity=0.6, size=7),
        text=labels,
        hovertemplate="Block %{text}<br>Unique ratio: %{x:.3f}<br>Warm rate: %{y:.3f}<extra></extra>",
    ))
    fig.update_layout(
        title="Phase 3 — Unique Slot Ratio vs Warm Rate",
        xaxis_title="Unique slots / total accesses",
        yaxis_title="Warm rate",
        template="plotly_white",
    )
    return fig


def fig_frequency_loglog(pool: dict[str, int]) -> go.Figure:
    """Log-scale bar chart of slot access frequency buckets, pooled (Phase 3)."""
    ordered_keys = ["1", "2", "3-5", "6-10", "11+"]
    counts = [pool.get(k, 0) for k in ordered_keys]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=ordered_keys,
        y=counts,
        marker_color="#10b981",
        opacity=0.85,
    ))
    fig.update_layout(
        title="Phase 3 — Access Frequency Distribution (pooled across blocks)",
        xaxis_title="Accesses per (block, address, slot)",
        yaxis_title="Number of slot-block pairs (log scale)",
        yaxis_type="log",
        template="plotly_white",
        showlegend=False,
    )
    return fig


# ---------------------------------------------------------------------------
# Phase 4
# ---------------------------------------------------------------------------

def fig_top_contracts_bar(df_contracts: list[dict], n: int = 20) -> go.Figure:
    """Horizontal bar: top-N contracts by warm access contribution (Phase 4)."""
    top = df_contracts[:n]
    labels = [d["short_addr"] for d in top]
    values = [d["warm_accesses"] for d in top]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=values,
        y=labels,
        orientation="h",
        marker_color=C_WITHIN,
        opacity=0.85,
    ))
    fig.update_layout(
        title=f"Phase 4 — Top {n} Contracts by Warm Access Contribution",
        xaxis_title="Total warm accesses (across all blocks)",
        yaxis=dict(autorange="reversed"),
        template="plotly_white",
        showlegend=False,
        height=max(400, n * 28),
    )
    return fig


def fig_contract_treemap(df_contracts: list[dict]) -> go.Figure:
    """Treemap: top-5 / top-10 / rest share of total warm accesses (Phase 4)."""
    total = sum(d["warm_accesses"] for d in df_contracts)
    if total == 0:
        return go.Figure()

    top5 = sum(d["warm_accesses"] for d in df_contracts[:5])
    top10 = sum(d["warm_accesses"] for d in df_contracts[5:10])
    rest = total - top5 - top10

    labels = (
        [d["short_addr"] for d in df_contracts[:5]]
        + [d["short_addr"] for d in df_contracts[5:10]]
        + ["Everything else"]
    )
    parents = ["Top 5"] * 5 + ["Top 6–10"] * 5 + ["Rest"]
    values = (
        [d["warm_accesses"] for d in df_contracts[:5]]
        + [d["warm_accesses"] for d in df_contracts[5:10]]
        + [rest]
    )

    # Add group nodes
    labels = ["All", "Top 5", "Top 6–10", "Rest"] + labels
    parents = ["", "All", "All", "All"] + parents
    values = [total, top5, top10, rest] + values

    fig = go.Figure(go.Treemap(
        labels=labels,
        parents=parents,
        values=values,
        branchvalues="total",
        marker=dict(colorscale="Blues"),
        textinfo="label+percent parent",
    ))
    fig.update_layout(
        title="Phase 4 — Warm Access Share: Top 5 / Top 10 / Rest",
        template="plotly_white",
        margin=dict(t=50, l=10, r=10, b=10),
    )
    return fig
