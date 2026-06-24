"""Plotly chart builders for the Decision Ledger dashboard.

Each function accepts a pandas DataFrame and returns a plotly Figure.
No Streamlit imports here — pure data-viz layer.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

_PALETTE = {
    "succeeded": "#22c55e",
    "failed": "#ef4444",
    "reversed": "#f97316",
    "superseded": "#a855f7",
    "active": "#3b82f6",
}

_CAT_COLORS = px.colors.qualitative.Bold


def accuracy_bar(df: pd.DataFrame) -> go.Figure:
    """Grouped bar: succeeded vs failed vs reversed per category."""
    fig = go.Figure()
    for col, color in [
        ("succeeded", _PALETTE["succeeded"]),
        ("failed", _PALETTE["failed"]),
        ("reversed", _PALETTE["reversed"]),
        ("superseded", _PALETTE["superseded"]),
    ]:
        if col in df.columns:
            fig.add_trace(
                go.Bar(
                    name=col.title(),
                    x=df["category"],
                    y=df[col],
                    marker_color=color,
                )
            )
    fig.update_layout(
        barmode="group",
        title="Decision Outcomes by Category",
        xaxis_title="Category",
        yaxis_title="Count",
        legend_title="Outcome",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(size=13),
    )
    return fig


def accuracy_rate_line(df: pd.DataFrame) -> go.Figure:
    """Horizontal bar chart of accuracy rate % by category."""
    df_sorted = df.sort_values("accuracy_rate_pct", ascending=True)
    fig = go.Figure(
        go.Bar(
            x=df_sorted["accuracy_rate_pct"],
            y=df_sorted["category"],
            orientation="h",
            marker_color=[_PALETTE["succeeded"]] * len(df_sorted),
            text=df_sorted["accuracy_rate_pct"].apply(lambda v: f"{v}%"),
            textposition="outside",
        )
    )
    fig.update_layout(
        title="Success Rate by Category (%)",
        xaxis_title="Accuracy %",
        yaxis_title="",
        xaxis_range=[0, 110],
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(size=13),
    )
    return fig


def status_donut(df: pd.DataFrame) -> go.Figure:
    """Donut chart of overall status distribution from summary row."""
    labels = ["Active", "Succeeded", "Failed", "Reversed", "Superseded"]
    cols = [
        "active_decisions",
        "succeeded_decisions",
        "failed_decisions",
        "reversed_decisions",
        "superseded_decisions",
    ]
    values = [df[c].iloc[0] for c in cols if c in df.columns]
    colors = [
        _PALETTE["active"],
        _PALETTE["succeeded"],
        _PALETTE["failed"],
        _PALETTE["reversed"],
        _PALETTE["superseded"],
    ]
    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.55,
            marker_colors=colors,
            textinfo="label+percent",
            textfont_size=13,
        )
    )
    fig.update_layout(
        title="Decision Portfolio Status",
        showlegend=True,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(size=13),
    )
    return fig


def compliance_heatmap(df: pd.DataFrame) -> go.Figure:
    """Bar chart of review compliance % by category with color gradient."""
    df_sorted = df.sort_values("compliance_rate_pct", ascending=False)
    colors = [
        "#22c55e" if v >= 80 else "#f97316" if v >= 50 else "#ef4444"
        for v in df_sorted["compliance_rate_pct"].fillna(0)
    ]
    fig = go.Figure(
        go.Bar(
            x=df_sorted["category"],
            y=df_sorted["compliance_rate_pct"].fillna(0),
            marker_color=colors,
            text=df_sorted["compliance_rate_pct"].apply(
                lambda v: f"{v:.1f}%" if pd.notna(v) else "N/A"
            ),
            textposition="outside",
        )
    )
    fig.update_layout(
        title="Review Compliance Rate by Category",
        xaxis_title="Category",
        yaxis_title="Compliance %",
        yaxis_range=[0, 115],
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(size=13),
    )
    fig.add_hline(y=80, line_dash="dot", line_color="green", annotation_text="80% target")
    return fig


def velocity_timeline(df: pd.DataFrame) -> go.Figure:
    """Multi-line chart of decisions made per month by category."""
    if df.empty:
        return go.Figure()

    df = df.copy()
    df["month_bucket"] = pd.to_datetime(df["month_bucket"])

    fig = px.line(
        df,
        x="month_bucket",
        y="total_decisions",
        color="category",
        markers=True,
        title="Decision Volume Over Time by Category",
        labels={"month_bucket": "Month", "total_decisions": "Decisions Made", "category": "Category"},
        color_discrete_sequence=_CAT_COLORS,
    )
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(size=13),
        xaxis=dict(tickformat="%b %Y"),
    )
    return fig


def horizon_box(df: pd.DataFrame) -> go.Figure:
    """Box: average decision horizon (days to review) by category."""
    if df.empty:
        return go.Figure()

    fig = px.bar(
        df.groupby("category")["avg_horizon_days"].mean().reset_index(),
        x="category",
        y="avg_horizon_days",
        title="Average Decision Horizon (Days to Review) by Category",
        labels={"avg_horizon_days": "Avg Days", "category": "Category"},
        color="category",
        color_discrete_sequence=_CAT_COLORS,
    )
    fig.update_layout(
        showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(size=13),
    )
    return fig


def reversal_waterfall(df: pd.DataFrame) -> go.Figure:
    """Stacked bar showing decision counts and adverse rates per category."""
    if df.empty:
        return go.Figure()

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(
        go.Bar(
            name="Total Decisions",
            x=df["category"],
            y=df["total_decisions"],
            marker_color="#94a3b8",
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            name="Adverse Rate %",
            x=df["category"],
            y=df["adverse_rate_pct"],
            mode="markers+lines",
            marker=dict(size=12, color=_PALETTE["failed"]),
            line=dict(color=_PALETTE["failed"], dash="dot"),
        ),
        secondary_y=True,
    )
    fig.update_layout(
        title="Decision Volume vs Adverse Rate by Category",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(size=13),
        legend=dict(x=0.01, y=0.99),
    )
    fig.update_yaxes(title_text="Total Decisions", secondary_y=False)
    fig.update_yaxes(title_text="Adverse Rate %", secondary_y=True)
    return fig
