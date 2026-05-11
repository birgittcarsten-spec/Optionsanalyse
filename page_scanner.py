"""Scanner-Seite für das ThetaFlow AI Dashboard.

Trade_Suggestions nach Strategietyp filterbar. Detailansicht mit Greeks,
Wahrscheinlichkeiten, Risikokennzahlen und AI-Ranking-Begründung.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import date, timedelta


def _generate_mock_suggestions() -> list[dict]:
    """Mock Trade Suggestions für Demo-Betrieb generieren."""
    np.random.seed(123)
    underlyings = ["AAPL", "MSFT", "SPY", "QQQ", "TSLA", "AMZN", "NVDA", "META"]
    strategies = ["covered_call", "cash_secured_put", "wheel", "iron_condor"]

    suggestions = []
    for i in range(40):
        underlying = np.random.choice(underlyings)
        strategy = np.random.choice(strategies)
        option_type = "call" if strategy == "covered_call" else "put"

        base_price = {
            "AAPL": 178.50, "MSFT": 415.20, "SPY": 512.30, "QQQ": 438.10,
            "TSLA": 248.90, "AMZN": 185.60, "NVDA": 875.40, "META": 505.80,
        }.get(underlying, 100.0)

        strike_offset = np.random.uniform(0.02, 0.10)
        if option_type == "put":
            strike = round(base_price * (1 - strike_offset), 2)
        else:
            strike = round(base_price * (1 + strike_offset), 2)

        dte = np.random.randint(20, 46)
        delta = round(np.random.uniform(0.10, 0.30), 3)
        iv_rank = round(np.random.uniform(25, 85), 1)
        premium = round(np.random.uniform(0.50, 8.00), 2)
        pop = round(np.random.uniform(0.60, 0.90), 2)
        ev = round(np.random.uniform(-50, 200), 2)
        combined_score = round(np.random.uniform(40, 95), 1)
        ai_score = round(np.random.uniform(35, 98), 1)

        gamma = round(np.random.uniform(0.01, 0.08), 4)
        theta = round(-np.random.uniform(0.02, 0.25), 4)
        vega = round(np.random.uniform(0.05, 0.30), 4)
        rho = round(np.random.uniform(-0.03, 0.03), 4)

        reasons = [
            f"Hoher IV Rank ({iv_rank:.0f}) deutet auf überbewertete Volatilität hin.",
            f"Delta von {delta:.2f} bietet gutes Risiko-Rendite-Verhältnis.",
            f"DTE von {dte} Tagen im optimalen Theta-Decay-Bereich.",
            f"Probability of Profit bei {pop:.0%} - statistisch vorteilhaft.",
            f"Expected Value von ${ev:.2f} positiv.",
        ]
        reasoning = " ".join(np.random.choice(reasons, size=3, replace=False))

        suggestions.append({
            "underlying": underlying, "strike": strike,
            "expiration": (date.today() + timedelta(days=dte)).isoformat(),
            "option_type": option_type, "strategy_type": strategy,
            "premium_bid": premium, "delta": delta, "gamma": gamma,
            "theta": theta, "vega": vega, "rho": rho, "iv_rank": iv_rank,
            "dte": dte, "probability_of_profit": pop, "expected_value": ev,
            "combined_score": combined_score, "ai_score": ai_score,
            "ai_reasoning": reasoning,
        })

    return suggestions


def _render_detail_view(suggestion: dict):
    """Detailansicht für einen ausgewählten Trade Suggestion."""
    st.markdown("---")
    st.markdown(f"### 📋 Detail: {suggestion['underlying']} "
                f"{suggestion['strike']} {suggestion['option_type'].upper()} "
                f"({suggestion['expiration']})")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**Greeks**")
        st.metric("Delta", f"{suggestion['delta']:.3f}")
        st.metric("Gamma", f"{suggestion['gamma']:.4f}")
        st.metric("Theta", f"{suggestion['theta']:.4f}")
        st.metric("Vega", f"{suggestion['vega']:.4f}")
        st.metric("Rho", f"{suggestion['rho']:.4f}")

    with col2:
        st.markdown("**Wahrscheinlichkeiten & Rendite**")
        st.metric("Probability of Profit", f"{suggestion['probability_of_profit']:.0%}")
        st.metric("Expected Value", f"${suggestion['expected_value']:.2f}")
        st.metric("Prämie (Bid)", f"${suggestion['premium_bid']:.2f}")
        st.metric("IV Rank", f"{suggestion['iv_rank']:.1f}")
        st.metric("DTE", f"{suggestion['dte']} Tage")

    with col3:
        st.markdown("**Scores & Ranking**")
        st.metric("AI Score", f"{suggestion['ai_score']:.1f} / 100")
        st.metric("Combined Score", f"{suggestion['combined_score']:.1f}")

        fig = go.Figure(go.Indicator(
            mode="gauge+number", value=suggestion["ai_score"],
            title={"text": "AI Score"},
            gauge={"axis": {"range": [0, 100]}, "bar": {"color": "#6366f1"},
                   "steps": [{"range": [0, 33], "color": "#fee2e2"},
                             {"range": [33, 66], "color": "#fef3c7"},
                             {"range": [66, 100], "color": "#d1fae5"}]},
        ))
        fig.update_layout(height=200, margin=dict(t=40, b=0, l=20, r=20))
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("**🤖 AI-Begründung:**")
    st.info(suggestion["ai_reasoning"])


def render_scanner():
    """Scanner-Seite rendern."""
    st.title("🔍 Strategie-Scanner")
    st.caption("Trade Suggestions nach Strategietyp filtern und bewerten")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        strategy_filter = st.selectbox(
            "Strategie",
            options=["Alle", "Covered Call", "Cash Secured Put", "Wheel", "Iron Condor"],
        )
    with col2:
        sort_by = st.selectbox(
            "Sortieren nach",
            options=["AI Score", "Combined Score", "IV Rank", "Probability of Profit"],
        )
    with col3:
        min_ai_score = st.slider("Min. AI Score", 0, 100, 50)
    with col4:
        min_pop = st.slider("Min. PoP (%)", 0, 100, 60)

    suggestions = _generate_mock_suggestions()

    strategy_map = {
        "Covered Call": "covered_call", "Cash Secured Put": "cash_secured_put",
        "Wheel": "wheel", "Iron Condor": "iron_condor",
    }

    if strategy_filter != "Alle":
        strategy_key = strategy_map.get(strategy_filter, "")
        suggestions = [s for s in suggestions if s["strategy_type"] == strategy_key]

    suggestions = [s for s in suggestions if s["ai_score"] >= min_ai_score]
    suggestions = [s for s in suggestions if s["probability_of_profit"] * 100 >= min_pop]

    sort_map = {
        "AI Score": "ai_score", "Combined Score": "combined_score",
        "IV Rank": "iv_rank", "Probability of Profit": "probability_of_profit",
    }
    sort_key = sort_map.get(sort_by, "ai_score")
    suggestions.sort(key=lambda x: x[sort_key], reverse=True)

    st.markdown(f"**{len(suggestions)} Vorschläge** gefunden")

    if not suggestions:
        st.warning("Keine Trade Suggestions für die gewählten Filter gefunden.")
        return

    strategy_display = {
        "covered_call": "Covered Call", "cash_secured_put": "Cash Secured Put",
        "wheel": "Wheel", "iron_condor": "Iron Condor",
    }

    table_data = []
    for s in suggestions:
        table_data.append({
            "Underlying": s["underlying"],
            "Strategie": strategy_display.get(s["strategy_type"], s["strategy_type"]),
            "Strike": f"${s['strike']:.2f}", "Typ": s["option_type"].upper(),
            "DTE": s["dte"], "Prämie": f"${s['premium_bid']:.2f}",
            "Delta": f"{s['delta']:.3f}", "IV Rank": f"{s['iv_rank']:.1f}",
            "PoP": f"{s['probability_of_profit']:.0%}",
            "EV": f"${s['expected_value']:.2f}",
            "AI Score": f"{s['ai_score']:.1f}", "Combined": f"{s['combined_score']:.1f}",
        })

    df = pd.DataFrame(table_data)
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("### Detailansicht")

    selected_idx = st.selectbox(
        "Trade auswählen für Details:",
        options=range(len(suggestions)),
        format_func=lambda i: (
            f"{suggestions[i]['underlying']} | "
            f"{strategy_display.get(suggestions[i]['strategy_type'], '')} | "
            f"Strike ${suggestions[i]['strike']:.2f} | "
            f"AI Score {suggestions[i]['ai_score']:.1f}"
        ),
    )

    if selected_idx is not None:
        _render_detail_view(suggestions[selected_idx])
