"""
agents/analytics_agent/charts.py
Plotly chart generators for all dashboards — Agent 5
"""

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from typing import Dict, List, Any


# ── Color Palette ─────────────────────────────────────────────────────────────

COLORS = {
    "primary":    "#6C63FF",
    "secondary":  "#FF6584",
    "accent":     "#43E97B",
    "warning":    "#F5A623",
    "bg_dark":    "#0F1117",
    "card_bg":    "#1C1F26",
    "text":       "#E8EAED",
}

SPORT_COLORS = {
    "cricket":    "#43E97B",
    "kabaddi":    "#FF6584",
    "volleyball": "#6C63FF",
}

BRANCH_COLORS = px.colors.qualitative.Set3


# ── Bar Charts ────────────────────────────────────────────────────────────────

def batting_runs_chart(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return _empty_chart("No batting data available")
    fig = px.bar(
        df.head(10), x="Player", y="Runs",
        color="Runs",
        color_continuous_scale=["#1C1F26", "#43E97B"],
        title="🏏 Top Batters — Runs Scored",
        text="Runs",
    )
    fig.update_traces(textposition="outside")
    return _apply_dark_theme(fig)


def bowling_wickets_chart(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return _empty_chart("No bowling data available")
    fig = px.bar(
        df.head(10), x="Player", y="Wickets",
        color="Wickets",
        color_continuous_scale=["#1C1F26", "#FF6584"],
        title="🎳 Top Bowlers — Wickets",
        text="Wickets",
    )
    fig.update_traces(textposition="outside")
    return _apply_dark_theme(fig)


def kabaddi_points_chart(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return _empty_chart("No kabaddi data available")
    fig = px.bar(
        df.head(10), x="Player",
        y=["Raid Pts", "Tackle Pts", "Bonus Pts"],
        title="🤼 Kabaddi — Points Breakdown",
        barmode="stack",
        color_discrete_sequence=[COLORS["primary"], COLORS["secondary"], COLORS["accent"]],
    )
    return _apply_dark_theme(fig)


def volleyball_stats_chart(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return _empty_chart("No volleyball data available")
    fig = px.bar(
        df.head(10), x="Player",
        y=["Aces", "Kills", "Blocks"],
        title="🏐 Volleyball — Player Contributions",
        barmode="stack",
        color_discrete_sequence=[COLORS["primary"], COLORS["accent"], COLORS["warning"]],
    )
    return _apply_dark_theme(fig)


# ── Leaderboard Chart ─────────────────────────────────────────────────────────

def leaderboard_chart(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return _empty_chart("No leaderboard data")
    fig = px.bar(
        df, x="Team", y="Pts",
        color="Pts",
        color_continuous_scale=["#1C1F26", "#6C63FF"],
        title="🏆 Tournament Leaderboard",
        text="Pts",
    )
    fig.update_traces(textposition="outside")
    return _apply_dark_theme(fig)


# ── Branch Standings Chart ─────────────────────────────────────────────────────

def branch_standings_chart(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return _empty_chart("No branch standings data")
    fig = go.Figure(data=[
        go.Bar(name="🥇 Gold",   x=df["Branch"], y=df["🥇 Gold"],   marker_color="#FFD700"),
        go.Bar(name="🥈 Silver", x=df["Branch"], y=df["🥈 Silver"], marker_color="#C0C0C0"),
        go.Bar(name="🥉 Bronze", x=df["Branch"], y=df["🥉 Bronze"], marker_color="#CD7F32"),
    ])
    fig.update_layout(barmode="stack", title="🏛️ Branch Medal Standings")
    return _apply_dark_theme(fig)


# ── Strike Rate Scatter ────────────────────────────────────────────────────────

def strike_rate_scatter(df: pd.DataFrame) -> go.Figure:
    if df.empty or "SR" not in df.columns:
        return _empty_chart("No data for strike rate chart")
    fig = px.scatter(
        df, x="Balls", y="Runs",
        size="SR", color="SR",
        hover_name="Player",
        color_continuous_scale="Viridis",
        title="📊 Runs vs Balls (Bubble = Strike Rate)",
    )
    return _apply_dark_theme(fig)


# ── Live Score Gauge ──────────────────────────────────────────────────────────

def run_rate_gauge(current_rr: float, required_rr: float) -> go.Figure:
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=current_rr,
        delta={"reference": required_rr, "increasing": {"color": "#43E97B"}, "decreasing": {"color": "#FF6584"}},
        title={"text": "Current Run Rate", "font": {"color": COLORS["text"]}},
        gauge={
            "axis":  {"range": [0, max(required_rr * 1.5, 12)], "tickcolor": COLORS["text"]},
            "bar":   {"color": COLORS["primary"]},
            "steps": [
                {"range": [0, required_rr * 0.8], "color": "#FF6584"},
                {"range": [required_rr * 0.8, required_rr], "color": COLORS["warning"]},
                {"range": [required_rr, required_rr * 1.5], "color": COLORS["accent"]},
            ],
            "threshold": {"line": {"color": "#FFD700", "width": 3}, "thickness": 0.8, "value": required_rr},
        },
    ))
    fig.update_layout(height=250, paper_bgcolor=COLORS["card_bg"], font_color=COLORS["text"])
    return fig


# ── MVP Radar ─────────────────────────────────────────────────────────────────

def player_radar(player_stats: Dict[str, float], player_name: str) -> go.Figure:
    categories = list(player_stats.keys())
    values     = list(player_stats.values())
    values    += values[:1]
    categories += categories[:1]

    fig = go.Figure(go.Scatterpolar(
        r=values, theta=categories, fill="toself",
        line_color=COLORS["primary"],
        fillcolor="rgba(108, 99, 255, 0.3)",
    ))
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, gridcolor="#2D3039")),
        title=f"🎯 {player_name} — Performance Radar",
        paper_bgcolor=COLORS["card_bg"],
        font_color=COLORS["text"],
    )
    return fig


# ── Helpers ───────────────────────────────────────────────────────────────────

def _apply_dark_theme(fig: go.Figure) -> go.Figure:
    fig.update_layout(
        paper_bgcolor=COLORS["card_bg"],
        plot_bgcolor=COLORS["bg_dark"],
        font_color=COLORS["text"],
        title_font_color=COLORS["text"],
        legend=dict(bgcolor=COLORS["card_bg"]),
        xaxis=dict(gridcolor="#2D3039", linecolor="#2D3039"),
        yaxis=dict(gridcolor="#2D3039", linecolor="#2D3039"),
        margin=dict(t=50, b=30, l=30, r=30),
    )
    return fig


def _empty_chart(message: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper", yref="paper",
        x=0.5, y=0.5, showarrow=False,
        font=dict(size=16, color=COLORS["text"]),
    )
    fig.update_layout(
        paper_bgcolor=COLORS["card_bg"],
        plot_bgcolor=COLORS["bg_dark"],
        height=300,
    )
    return fig
