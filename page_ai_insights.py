"""AI-Insights-Seite für das ThetaFlow AI Dashboard.

Top-Empfehlungen der AI_Ranking_Engine mit Begründungen anzeigen.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import date, timedelta


def _generate_mock_ranked_suggestions() -> list[dict]:
    """Mock AI-gerankte Suggestions generieren."""
    np.random.seed(456)
    suggestions = [
        {"rank": 1, "underlying": "NVDA", "strategy_type": "cash_secured_put", "strike": 820.00, "expiration": (date.today() + timedelta(days=32)).isoformat(), "option_type": "put", "ai_score": 92.4, "combined_score": 88.1, "premium_bid": 14.50, "delta": 0.18, "iv_rank": 72.3, "dte": 32, "probability_of_profit": 0.82, "expected_value": 185.40, "reasoning": "NVDA zeigt einen IV Rank von 72.3, was auf überbewertete Volatilität hindeutet – ideal für Prämienverkauf. Das Delta von 0.18 bietet ein konservatives Risikoprofil mit 82% Gewinnwahrscheinlichkeit. DTE von 32 Tagen liegt im optimalen Theta-Decay-Bereich.", "feature_contributions": {"IV Rank": 0.28, "Probability of Profit": 0.22, "Expected Value": 0.18, "Delta": 0.12, "DTE": 0.08, "Sektor-Performance": 0.07, "Marktregime": 0.05}},
        {"rank": 2, "underlying": "AAPL", "strategy_type": "covered_call", "strike": 185.00, "expiration": (date.today() + timedelta(days=25)).isoformat(), "option_type": "call", "ai_score": 87.8, "combined_score": 84.5, "premium_bid": 3.20, "delta": 0.25, "iv_rank": 58.1, "dte": 25, "probability_of_profit": 0.78, "expected_value": 142.30, "reasoning": "AAPL bietet ein ausgewogenes Risiko-Rendite-Profil für Covered Calls. IV Rank bei 58.1 signalisiert moderate Überbewertung der Volatilität. Delta von 0.25 balanciert Prämieneinnahme und Zuweisungsrisiko.", "feature_contributions": {"IV Rank": 0.24, "Probability of Profit": 0.20, "Expected Value": 0.16, "Delta": 0.14, "DTE": 0.10, "Sektor-Performance": 0.09, "Marktregime": 0.07}},
        {"rank": 3, "underlying": "SPY", "strategy_type": "iron_condor", "strike": 500.00, "expiration": (date.today() + timedelta(days=38)).isoformat(), "option_type": "put", "ai_score": 84.2, "combined_score": 81.9, "premium_bid": 4.80, "delta": 0.12, "iv_rank": 45.6, "dte": 38, "probability_of_profit": 0.85, "expected_value": 168.50, "reasoning": "SPY Iron Condor profitiert vom aktuellen Range-Bound-Marktregime. Niedriges Delta (0.12) bietet hohe Gewinnwahrscheinlichkeit von 85%.", "feature_contributions": {"IV Rank": 0.18, "Probability of Profit": 0.26, "Expected Value": 0.20, "Delta": 0.10, "DTE": 0.09, "Sektor-Performance": 0.05, "Marktregime": 0.12}},
        {"rank": 4, "underlying": "MSFT", "strategy_type": "cash_secured_put", "strike": 400.00, "expiration": (date.today() + timedelta(days=28)).isoformat(), "option_type": "put", "ai_score": 79.5, "combined_score": 76.8, "premium_bid": 5.40, "delta": 0.20, "iv_rank": 52.8, "dte": 28, "probability_of_profit": 0.80, "expected_value": 128.60, "reasoning": "MSFT Cash Secured Put bei Strike $400 bietet solide Prämie bei akzeptablem Risiko. IV Rank von 52.8 über dem Schwellenwert für Prämienverkauf.", "feature_contributions": {"IV Rank": 0.22, "Probability of Profit": 0.21, "Expected Value": 0.17, "Delta": 0.13, "DTE": 0.11, "Sektor-Performance": 0.10, "Marktregime": 0.06}},
        {"rank": 5, "underlying": "TSLA", "strategy_type": "wheel", "strike": 235.00, "expiration": (date.today() + timedelta(days=22)).isoformat(), "option_type": "put", "ai_score": 74.1, "combined_score": 72.3, "premium_bid": 6.80, "delta": 0.22, "iv_rank": 68.9, "dte": 22, "probability_of_profit": 0.74, "expected_value": 95.20, "reasoning": "TSLA Wheel Strategy nutzt die hohe IV (Rank 68.9) für überdurchschnittliche Prämien. Höheres Risiko durch volatile Kursbewegungen.", "feature_contributions": {"IV Rank": 0.30, "Probability of Profit": 0.15, "Expected Value": 0.14, "Delta": 0.12, "DTE": 0.08, "Sektor-Performance": 0.06, "Marktregime": 0.15}},
    ]
    return suggestions


def _render_score_comparison(suggestions: list[dict]):
    fig = go.Figure()
    symbols = [f"#{s['rank']} {s['underlying']}" for s in suggestions]
    ai_scores = [s["ai_score"] for s in suggestions]
    combined_scores = [s["combined_score"] for s in suggestions]
    fig.add_trace(go.Bar(x=symbols, y=ai_scores, name="AI Score", marker_color="#6366f1", text=[f"{s:.1f}" for s in ai_scores], textposition="auto"))
    fig.add_trace(go.Bar(x=symbols, y=combined_scores, name="Combined Score", marker_color="#94a3b8", text=[f"{s:.1f}" for s in combined_scores], textposition="auto"))
    fig.update_layout(title="AI Score vs Combined Score", xaxis_title="Empfehlung", yaxis_title="Score", yaxis_range=[0, 100], barmode="group", template="plotly_white", height=350)
    st.plotly_chart(fig, use_container_width=True)


def _render_feature_importance(suggestion: dict):
    contributions = suggestion.get("feature_contributions", {})
    if not contributions:
        return
    sorted_pairs = sorted(contributions.items(), key=lambda x: x[1], reverse=True)
    features = [p[0] for p in sorted_pairs]
    importances = [p[1] for p in sorted_pairs]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=importances, y=features, orientation="h", marker_color="#6366f1", text=[f"{imp:.0%}" for imp in importances], textposition="auto"))
    fig.update_layout(title=f"Feature Importance - {suggestion['underlying']} (Rank #{suggestion['rank']})", xaxis_title="Beitrag zum Score", template="plotly_white", height=300, xaxis_tickformat=".0%", yaxis=dict(autorange="reversed"))
    st.plotly_chart(fig, use_container_width=True)


def _render_global_feature_importance(suggestions: list[dict]):
    all_features: dict[str, list[float]] = {}
    for s in suggestions:
        for feature, importance in s.get("feature_contributions", {}).items():
            if feature not in all_features:
                all_features[feature] = []
            all_features[feature].append(importance)
    avg_importance = {f: np.mean(vals) for f, vals in all_features.items()}
    sorted_features = sorted(avg_importance.items(), key=lambda x: x[1], reverse=True)
    features = [f[0] for f in sorted_features]
    importances = [f[1] for f in sorted_features]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=importances, y=features, orientation="h", marker_color=px.colors.sequential.Viridis[:len(features)], text=[f"{imp:.0%}" for imp in importances], textposition="auto"))
    fig.update_layout(title="Durchschnittliche Feature Importance (alle Empfehlungen)", xaxis_title="Durchschnittlicher Beitrag", template="plotly_white", height=350, xaxis_tickformat=".0%", yaxis=dict(autorange="reversed"))
    st.plotly_chart(fig, use_container_width=True)


def render_ai_insights():
    """AI-Insights-Seite rendern."""
    st.title("🤖 AI Insights")
    st.caption("KI-gestützte Empfehlungen mit Begründungen und Feature-Analyse")

    suggestions = _generate_mock_ranked_suggestions()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Top Empfehlungen", len(suggestions))
    with col2:
        avg_score = np.mean([s["ai_score"] for s in suggestions])
        st.metric("Ø AI Score", f"{avg_score:.1f}")
    with col3:
        avg_pop = np.mean([s["probability_of_profit"] for s in suggestions])
        st.metric("Ø Gewinnwahrscheinlichkeit", f"{avg_pop:.0%}")
    with col4:
        total_ev = sum(s["expected_value"] for s in suggestions)
        st.metric("Σ Expected Value", f"${total_ev:,.0f}")

    st.markdown("---")
    _render_score_comparison(suggestions)
    st.markdown("---")

    st.markdown("### 🏆 Top-Empfehlungen")
    strategy_display = {"covered_call": "Covered Call", "cash_secured_put": "Cash Secured Put", "wheel": "Wheel", "iron_condor": "Iron Condor"}

    for suggestion in suggestions:
        with st.expander(f"**#{suggestion['rank']} {suggestion['underlying']}** - {strategy_display.get(suggestion['strategy_type'], suggestion['strategy_type'])} | AI Score: {suggestion['ai_score']:.1f} | Strike ${suggestion['strike']:.2f}", expanded=(suggestion["rank"] <= 2)):
            col1, col2, col3 = st.columns([1, 1, 1])
            with col1:
                st.markdown("**Kennzahlen**")
                st.write(f"- **Strike:** ${suggestion['strike']:.2f}")
                st.write(f"- **Typ:** {suggestion['option_type'].upper()}")
                st.write(f"- **Verfall:** {suggestion['expiration']}")
                st.write(f"- **DTE:** {suggestion['dte']} Tage")
                st.write(f"- **Prämie:** ${suggestion['premium_bid']:.2f}")
            with col2:
                st.markdown("**Bewertung**")
                st.write(f"- **AI Score:** {suggestion['ai_score']:.1f} / 100")
                st.write(f"- **Combined Score:** {suggestion['combined_score']:.1f}")
                st.write(f"- **Delta:** {suggestion['delta']:.3f}")
                st.write(f"- **IV Rank:** {suggestion['iv_rank']:.1f}")
                st.write(f"- **PoP:** {suggestion['probability_of_profit']:.0%}")
            with col3:
                st.markdown("**Rendite**")
                st.write(f"- **Expected Value:** ${suggestion['expected_value']:.2f}")
                fig = go.Figure(go.Indicator(mode="gauge+number", value=suggestion["ai_score"], gauge={"axis": {"range": [0, 100]}, "bar": {"color": "#6366f1"}, "steps": [{"range": [0, 33], "color": "#fee2e2"}, {"range": [33, 66], "color": "#fef3c7"}, {"range": [66, 100], "color": "#d1fae5"}]}))
                fig.update_layout(height=150, margin=dict(t=20, b=0, l=20, r=20))
                st.plotly_chart(fig, use_container_width=True)
            st.markdown("**🧠 AI-Begründung:**")
            st.info(suggestion["reasoning"])
            _render_feature_importance(suggestion)

    st.markdown("---")
    st.markdown("### 📊 Feature Importance Analyse")
    _render_global_feature_importance(suggestions)

    st.markdown("### ℹ️ Über das AI-Ranking")
    st.markdown("""
    Das AI-Ranking-System bewertet Trade Suggestions anhand eines trainierten
    Machine-Learning-Modells (XGBoost). Die Features umfassen:

    - **IV Rank**: Implizite Volatilität im Verhältnis zum 52-Wochen-Bereich
    - **Probability of Profit**: Statistische Gewinnwahrscheinlichkeit
    - **Expected Value**: Erwarteter Gewinn/Verlust
    - **Delta**: Sensitivität gegenüber Kursänderungen
    - **DTE**: Restlaufzeit (optimaler Theta-Decay)
    - **Sektor-Performance**: Relative Stärke des Sektors
    - **Marktregime**: Aktuelle Marktphase (Trend/Range/Volatil)
    """)
