"""AI-Insights-Seite für das ThetaFlow AI Dashboard.

Nimmt die Top-Suggestions aus dem Scanner und bewertet sie mit dem
regelbasierten AI-Scoring. Zeigt Begründungen und Feature-Analyse.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import date, timedelta

from engine_ai_ranking import AIRankingEngine, RankedSuggestion, RULE_BASED_WEIGHTS
from model_trade import TradeSuggestion
from pipeline import load_live_quotes


def _get_scanner_suggestions() -> list[dict]:
    """Suggestions aus dem Scanner-Session-State holen."""
    return st.session_state.get("scanner_suggestions", [])


def _rank_suggestions_with_ai(suggestions: list[dict]) -> list[dict]:
    """Suggestions durch die AI Ranking Engine bewerten.

    Verwendet das regelbasierte Scoring (kein trainiertes Modell nötig).
    """
    if not suggestions:
        return []

    # AI Ranking Engine initialisieren (kein Modell = regelbasiertes Scoring)
    engine = AIRankingEngine(model_path="nonexistent_model.json")

    # TradeSuggestion-Objekte erstellen
    trade_suggestions = []
    for s in suggestions[:20]:  # Top 20 für AI-Analyse
        try:
            ts = TradeSuggestion(
                underlying=s["underlying"],
                strike=float(s["strike"]),
                expiration=date.fromisoformat(s["expiration"])
                if isinstance(s["expiration"], str)
                else s["expiration"],
                option_type=s["option_type"],
                strategy_type=s["strategy_type"],
                premium_bid=float(s["premium_bid"]),
                delta=float(s["delta"]),
                iv_rank=float(s["iv_rank"]),
                dte=int(s["dte"]),
                probability_of_profit=float(s["probability_of_profit"]),
                expected_value=float(s["expected_value"]),
                combined_score=float(s["combined_score"]),
            )
            trade_suggestions.append(ts)
        except (ValueError, KeyError, TypeError):
            continue

    if not trade_suggestions:
        return []

    # Marktkontext aus Live-Quotes ableiten
    underlyings = st.session_state.get("underlyings", [])
    quotes, _ = load_live_quotes(underlyings)

    market_context = {
        "market_regime": "neutral",
        "historical_volatility": {},
        "sector_performance": {},
        "vix": 18.0,
    }

    # AI Ranking durchführen
    ranked = engine.rank_suggestions(trade_suggestions, market_context)

    # Zurück in dict-Format konvertieren
    results = []
    for i, r in enumerate(ranked):
        s = r.suggestion
        results.append({
            "rank": i + 1,
            "underlying": s.underlying,
            "strategy_type": s.strategy_type,
            "strike": s.strike,
            "expiration": s.expiration.isoformat()
            if hasattr(s.expiration, "isoformat")
            else str(s.expiration),
            "option_type": s.option_type,
            "ai_score": round(r.ai_score, 1),
            "combined_score": s.combined_score,
            "premium_bid": s.premium_bid,
            "delta": s.delta,
            "iv_rank": s.iv_rank,
            "dte": s.dte,
            "probability_of_profit": s.probability_of_profit,
            "expected_value": s.expected_value,
            "reasoning": r.reasoning,
            "feature_contributions": {
                "IV Rank": RULE_BASED_WEIGHTS["iv_rank"],
                "Probability of Profit": RULE_BASED_WEIGHTS["probability_of_profit"],
                "Delta": RULE_BASED_WEIGHTS["delta_proximity"],
                "DTE": RULE_BASED_WEIGHTS["dte"],
                "Expected Value": RULE_BASED_WEIGHTS["expected_value"],
            },
        })

    return results


def _render_score_comparison(suggestions: list[dict]):
    """AI Score vs Combined Score Vergleich."""
    fig = go.Figure()
    symbols = [f"#{s['rank']} {s['underlying']}" for s in suggestions[:10]]
    ai_scores = [s["ai_score"] for s in suggestions[:10]]
    combined_scores = [s["combined_score"] for s in suggestions[:10]]

    fig.add_trace(go.Bar(
        x=symbols, y=ai_scores, name="AI Score",
        marker_color="#6366f1", text=[f"{s:.1f}" for s in ai_scores], textposition="auto",
    ))
    fig.add_trace(go.Bar(
        x=symbols, y=combined_scores, name="Combined Score",
        marker_color="#94a3b8", text=[f"{s:.1f}" for s in combined_scores], textposition="auto",
    ))
    fig.update_layout(
        title="AI Score vs Combined Score (Top 10)",
        xaxis_title="Empfehlung", yaxis_title="Score",
        yaxis_range=[0, 100], barmode="group", template="plotly_white", height=350,
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_feature_importance(suggestion: dict):
    """Feature Importance für eine Empfehlung."""
    contributions = suggestion.get("feature_contributions", {})
    if not contributions:
        return
    sorted_pairs = sorted(contributions.items(), key=lambda x: x[1], reverse=True)
    features = [p[0] for p in sorted_pairs]
    importances = [p[1] for p in sorted_pairs]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=importances, y=features, orientation="h",
        marker_color="#6366f1", text=[f"{imp:.0%}" for imp in importances], textposition="auto",
    ))
    fig.update_layout(
        title=f"Feature Importance - {suggestion['underlying']} (Rank #{suggestion['rank']})",
        xaxis_title="Beitrag zum Score", template="plotly_white", height=250,
        xaxis_tickformat=".0%", yaxis=dict(autorange="reversed"),
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_global_feature_importance(suggestions: list[dict]):
    """Durchschnittliche Feature Importance."""
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
    fig.add_trace(go.Bar(
        x=importances, y=features, orientation="h",
        marker_color=px.colors.sequential.Viridis[:len(features)],
        text=[f"{imp:.0%}" for imp in importances], textposition="auto",
    ))
    fig.update_layout(
        title="Feature-Gewichtung im AI-Ranking",
        xaxis_title="Gewicht", template="plotly_white", height=300,
        xaxis_tickformat=".0%", yaxis=dict(autorange="reversed"),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_ai_insights():
    """AI-Insights-Seite rendern."""
    st.title("🤖 AI Insights")
    st.caption("KI-gestützte Empfehlungen basierend auf Scanner-Ergebnissen")

    # Suggestions aus Scanner holen und mit AI ranken
    scanner_data = _get_scanner_suggestions()

    if not scanner_data:
        st.warning(
            "⚠️ Keine Scanner-Daten vorhanden. "
            "Bitte zuerst die **Scanner**-Seite öffnen, damit Daten geladen werden."
        )
        st.info("Tipp: Gehe zum Scanner-Tab, warte bis Daten geladen sind, dann komm hierher zurück.")
        return

    # AI Ranking durchführen
    suggestions = _rank_suggestions_with_ai(scanner_data)

    if not suggestions:
        st.warning("Keine Suggestions konnten bewertet werden.")
        return

    # Datenquelle anzeigen
    is_live = st.session_state.get("scanner_is_live", False)
    if is_live:
        st.success("🟢 **Live-Daten** — AI-Ranking basiert auf echten Marktdaten")
    else:
        st.info("ℹ️ **Demo-Modus** — AI-Ranking basiert auf simulierten Daten")

    # KPI-Karten
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

    # Top-Empfehlungen
    st.markdown("### 🏆 Top-Empfehlungen")
    strategy_display = {
        "covered_call": "Covered Call", "cash_secured_put": "Cash Secured Put",
        "wheel": "Wheel", "iron_condor": "Iron Condor",
    }

    for suggestion in suggestions[:10]:  # Top 10 anzeigen
        with st.expander(
            f"**#{suggestion['rank']} {suggestion['underlying']}** - "
            f"{strategy_display.get(suggestion['strategy_type'], suggestion['strategy_type'])} | "
            f"AI Score: {suggestion['ai_score']:.1f} | "
            f"Strike ${suggestion['strike']:.2f}",
            expanded=(suggestion["rank"] <= 3),
        ):
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
                fig = go.Figure(go.Indicator(
                    mode="gauge+number", value=suggestion["ai_score"],
                    gauge={"axis": {"range": [0, 100]}, "bar": {"color": "#6366f1"},
                           "steps": [{"range": [0, 33], "color": "#fee2e2"},
                                     {"range": [33, 66], "color": "#fef3c7"},
                                     {"range": [66, 100], "color": "#d1fae5"}]},
                ))
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
    Das AI-Ranking bewertet jeden Trade-Vorschlag aus dem Scanner mit einem
    gewichteten Score (0–100). Die Gewichtung:

    - **IV Rank (25%)** — Höherer IV Rank = bessere Prämienumgebung
    - **Probability of Profit (25%)** — Höhere Gewinnwahrscheinlichkeit = besser
    - **Delta-Nähe zu 0.20 (20%)** — Idealer Bereich für Stillhalter
    - **DTE-Nähe zu 32 Tagen (15%)** — Optimaler Theta-Decay
    - **Expected Value (15%)** — Positiver Erwartungswert bevorzugt

    Sobald ein trainiertes ML-Modell verfügbar ist, werden zusätzlich
    Sektor-Performance und Marktregime berücksichtigt.
    """)
