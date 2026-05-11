"""Marktübersicht-Seite für das ThetaFlow AI Dashboard.

Zeigt aktuelle Kurse, IV_Rank und Volatilitätsbewertung für alle
konfigurierten Underlyings. Plotly-Charts für Volatilitätsverläufe.
Greek-KPI-Tooltips mit fachlicher Definition und Interpretation.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta

from util_kpi import get_all_kpi_definitions, get_kpi_definition


def _generate_mock_market_data() -> pd.DataFrame:
    """Mock-Marktdaten für Demo-Betrieb generieren."""
    underlyings = st.session_state.get(
        "underlyings", ["AAPL", "MSFT", "SPY", "QQQ", "TSLA", "AMZN", "NVDA", "META"]
    )

    np.random.seed(42)
    data = []
    for symbol in underlyings:
        base_price = {
            "AAPL": 178.50, "MSFT": 415.20, "SPY": 512.30, "QQQ": 438.10,
            "TSLA": 248.90, "AMZN": 185.60, "NVDA": 875.40, "META": 505.80,
        }.get(symbol, 100.0)

        iv_rank = np.random.uniform(15, 85)
        iv_percentile = np.random.uniform(20, 90)
        hv_20 = np.random.uniform(0.15, 0.55)
        hv_30 = np.random.uniform(0.14, 0.50)
        hv_60 = np.random.uniform(0.13, 0.45)
        iv_current = np.random.uniform(0.18, 0.60)

        if iv_rank < 25:
            rating = "niedrig"
        elif iv_rank < 50:
            rating = "mittel"
        elif iv_rank < 75:
            rating = "hoch"
        else:
            rating = "sehr hoch"

        change_pct = np.random.uniform(-3.0, 3.0)

        data.append({
            "Symbol": symbol,
            "Kurs": base_price * (1 + change_pct / 100),
            "Änderung %": change_pct,
            "IV Rank": iv_rank,
            "IV Percentile": iv_percentile,
            "IV Aktuell": iv_current,
            "HV 20": hv_20,
            "HV 30": hv_30,
            "HV 60": hv_60,
            "Bewertung": rating,
        })

    return pd.DataFrame(data)


def _generate_mock_iv_history(symbol: str) -> pd.DataFrame:
    """Mock IV-Verlauf für ein Underlying generieren."""
    np.random.seed(hash(symbol) % 2**31)
    dates = pd.date_range(end=datetime.now(), periods=90, freq="B")
    base_iv = np.random.uniform(0.20, 0.40)
    iv_values = base_iv + np.cumsum(np.random.normal(0, 0.005, len(dates)))
    iv_values = np.clip(iv_values, 0.10, 0.80)

    return pd.DataFrame({"Datum": dates, "IV": iv_values, "Symbol": symbol})


def _render_volatility_chart(market_data: pd.DataFrame):
    """Plotly-Chart für Volatilitätsvergleich rendern."""
    fig = go.Figure()

    symbols = market_data["Symbol"].tolist()
    iv_ranks = market_data["IV Rank"].tolist()

    colors = []
    for rank in iv_ranks:
        if rank >= 75:
            colors.append("#ff4444")
        elif rank >= 50:
            colors.append("#ffaa00")
        elif rank >= 25:
            colors.append("#44bb44")
        else:
            colors.append("#4488ff")

    fig.add_trace(go.Bar(
        x=symbols, y=iv_ranks, marker_color=colors,
        text=[f"{r:.1f}" for r in iv_ranks], textposition="auto", name="IV Rank",
    ))

    fig.update_layout(
        title="IV Rank Übersicht", xaxis_title="Underlying",
        yaxis_title="IV Rank", yaxis_range=[0, 100],
        template="plotly_white", height=400,
    )

    fig.add_hline(y=25, line_dash="dash", line_color="gray", annotation_text="Niedrig/Mittel")
    fig.add_hline(y=50, line_dash="dash", line_color="gray", annotation_text="Mittel/Hoch")
    fig.add_hline(y=75, line_dash="dash", line_color="gray", annotation_text="Hoch/Sehr Hoch")

    st.plotly_chart(fig, use_container_width=True)


def _render_iv_trend_chart(selected_symbol: str):
    """Plotly-Chart für IV-Verlauf eines Underlyings rendern."""
    iv_history = _generate_mock_iv_history(selected_symbol)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=iv_history["Datum"], y=iv_history["IV"], mode="lines",
        name=f"{selected_symbol} IV", line=dict(color="#6366f1", width=2),
        fill="tozeroy", fillcolor="rgba(99, 102, 241, 0.1)",
    ))

    fig.update_layout(
        title=f"Implizite Volatilität - {selected_symbol} (90 Tage)",
        xaxis_title="Datum", yaxis_title="Implizite Volatilität",
        template="plotly_white", height=350,
    )

    st.plotly_chart(fig, use_container_width=True)


def _render_greek_kpi_info():
    """Greek-KPI-Definitionen als Info-Dialog anzeigen."""
    st.markdown("### 📖 Greek-KPI Definitionen")
    st.caption("Klicken Sie auf einen Greek für Definition und Interpretation.")

    all_kpis = get_all_kpi_definitions()

    for greek_name, kpi in all_kpis.items():
        with st.expander(f"**{kpi['name']}** ({kpi['unit']})"):
            st.markdown("**Definition:**")
            st.markdown(kpi["definition"])
            st.markdown("**Interpretation für Stillhalter:**")
            st.markdown(kpi["interpretation"])
            favorable = kpi.get("favorable_range", {})
            if favorable:
                st.info(
                    f"Günstiger Bereich: {favorable.get('min', 'N/A')} "
                    f"bis {favorable.get('max', 'N/A')}"
                )


def render_market_overview():
    """Marktübersicht-Seite rendern."""
    st.title("🏠 Marktübersicht")
    st.caption("Aktuelle Kurse, Volatilität und Bewertung aller konfigurierten Underlyings")

    market_data = _generate_mock_market_data()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        high_iv_count = len(market_data[market_data["IV Rank"] >= 50])
        st.metric("Hohe IV Rank (≥50)", high_iv_count)
    with col2:
        avg_iv_rank = market_data["IV Rank"].mean()
        st.metric("Ø IV Rank", f"{avg_iv_rank:.1f}")
    with col3:
        best_symbol = market_data.loc[market_data["IV Rank"].idxmax(), "Symbol"]
        st.metric("Höchster IV Rank", best_symbol)
    with col4:
        st.metric("Underlyings", len(market_data))

    st.markdown("---")

    st.markdown("### Marktdaten")

    display_df = market_data.copy()
    display_df["Kurs"] = display_df["Kurs"].apply(lambda x: f"${x:.2f}")
    display_df["Änderung %"] = display_df["Änderung %"].apply(
        lambda x: f"{'🟢' if x >= 0 else '🔴'} {x:+.2f}%"
    )
    display_df["IV Rank"] = display_df["IV Rank"].apply(lambda x: f"{x:.1f}")
    display_df["IV Percentile"] = display_df["IV Percentile"].apply(lambda x: f"{x:.1f}")
    display_df["IV Aktuell"] = display_df["IV Aktuell"].apply(lambda x: f"{x:.1%}")
    display_df["HV 20"] = display_df["HV 20"].apply(lambda x: f"{x:.1%}")
    display_df["HV 30"] = display_df["HV 30"].apply(lambda x: f"{x:.1%}")
    display_df["HV 60"] = display_df["HV 60"].apply(lambda x: f"{x:.1%}")

    rating_emoji = {
        "niedrig": "🔵 niedrig", "mittel": "🟢 mittel",
        "hoch": "🟠 hoch", "sehr hoch": "🔴 sehr hoch",
    }
    display_df["Bewertung"] = display_df["Bewertung"].map(rating_emoji)

    st.dataframe(display_df, use_container_width=True, hide_index=True)

    st.markdown("---")

    col_left, col_right = st.columns([2, 1])

    with col_left:
        _render_volatility_chart(market_data)
        selected = st.selectbox("IV-Verlauf anzeigen für:", options=market_data["Symbol"].tolist())
        if selected:
            _render_iv_trend_chart(selected)

    with col_right:
        _render_greek_kpi_info()
