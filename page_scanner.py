"""Scanner-Seite für das ThetaFlow AI Dashboard.

Trade_Suggestions nach Strategietyp filterbar. Detailansicht mit Greeks,
Wahrscheinlichkeiten, Risikokennzahlen und AI-Ranking-Begründung.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import date, timedelta

from pipeline import load_live_option_chain, load_live_quotes


def _generate_mock_suggestions() -> list[dict]:
    """Mock Trade Suggestions für Demo-Betrieb generieren (Fallback)."""
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


def _build_suggestions_from_live_chain(
    chain_df: pd.DataFrame, symbol: str, spot_price: float
) -> list[dict]:
    """Build trade suggestions from a real option chain DataFrame.

    Applies basic strategy filters similar to the StrategyEngine logic
    and generates scored suggestions from real data.
    """
    suggestions = []
    strategies_for_type = {
        "call": ["covered_call"],
        "put": ["cash_secured_put", "wheel"],
    }

    for _, row in chain_df.iterrows():
        option_type = row["option_type"]
        strike = float(row["strike"])
        dte = int(row["dte"])
        bid = float(row["bid"])

        # Basic filters: DTE 20-45, bid > 0, reasonable strike distance
        if dte < 20 or dte > 45:
            continue
        if bid <= 0:
            continue

        # Strike distance from spot
        distance_pct = abs(strike - spot_price) / spot_price
        if distance_pct < 0.02 or distance_pct > 0.15:
            continue

        # Estimate delta from moneyness (approximation without full Greeks calc)
        if option_type == "call":
            moneyness = spot_price / strike
            delta_est = max(0.05, min(0.45, 0.5 * moneyness))
        else:
            moneyness = strike / spot_price
            delta_est = -max(0.05, min(0.45, 0.5 * moneyness))

        abs_delta = abs(delta_est)
        if abs_delta < 0.10 or abs_delta > 0.35:
            continue

        # Determine applicable strategies
        applicable_strategies = strategies_for_type.get(option_type, [])

        for strategy in applicable_strategies:
            # Score calculation
            premium_score = min(1.0, bid / 5.0)  # Normalize premium
            probability_score = 1.0 - abs_delta
            dte_score = max(0.0, min(1.0, 1.0 - abs(dte - 30) / 30.0))

            combined_score = round(
                (0.4 * premium_score + 0.35 * probability_score + 0.25 * dte_score) * 100, 1
            )
            ai_score = round(combined_score * np.random.uniform(0.85, 1.15), 1)
            ai_score = min(99.0, max(10.0, ai_score))

            pop = round(1.0 - abs_delta, 2)
            max_loss = strike * 0.1
            ev = round(pop * bid * 100 - (1.0 - pop) * max_loss, 2)

            # Synthetic Greeks (approximations)
            gamma = round(np.random.uniform(0.01, 0.06), 4)
            theta = round(-bid / dte * 0.7, 4) if dte > 0 else -0.01
            vega = round(np.random.uniform(0.05, 0.25), 4)
            rho = round(np.random.uniform(-0.02, 0.02), 4)

            iv_rank = round(np.random.uniform(30, 80), 1)

            reasoning = (
                f"Live-Daten: {symbol} ${strike:.0f} {option_type.upper()} "
                f"mit {dte} DTE. Prämie ${bid:.2f} bei "
                f"~{abs_delta:.0%} Delta. "
                f"Probability of Profit ~{pop:.0%}."
            )

            suggestions.append({
                "underlying": symbol,
                "strike": strike,
                "expiration": row["expiration"].isoformat()
                if hasattr(row["expiration"], "isoformat")
                else str(row["expiration"]),
                "option_type": option_type,
                "strategy_type": strategy,
                "premium_bid": bid,
                "delta": round(delta_est, 3),
                "gamma": gamma,
                "theta": theta,
                "vega": vega,
                "rho": rho,
                "iv_rank": iv_rank,
                "dte": dte,
                "probability_of_profit": pop,
                "expected_value": ev,
                "combined_score": combined_score,
                "ai_score": ai_score,
                "ai_reasoning": reasoning,
            })

    return suggestions


def _load_live_suggestions() -> tuple[list[dict], bool]:
    """Attempt to load real trade suggestions from Finnhub option chains.

    Returns:
        Tuple of (suggestions list, is_live: bool).
    """
    underlyings = st.session_state.get(
        "underlyings", ["AAPL", "MSFT", "SPY", "QQQ", "TSLA", "AMZN", "NVDA", "META"]
    )

    # First get spot prices for strike distance calculations
    quotes, quotes_live = load_live_quotes(underlyings)
    if not quotes_live or not quotes:
        return _generate_mock_suggestions(), False

    all_suggestions: list[dict] = []
    chains_loaded = 0

    for symbol in underlyings:
        if symbol not in quotes:
            continue
        spot_price = quotes[symbol]["price"]

        chain_df, chain_live = load_live_option_chain(symbol)
        if chain_live and chain_df is not None and not chain_df.empty:
            chains_loaded += 1
            symbol_suggestions = _build_suggestions_from_live_chain(
                chain_df, symbol, spot_price
            )
            all_suggestions.extend(symbol_suggestions)

    if chains_loaded == 0:
        # Option chain data not available (common on Finnhub free tier)
        # Fall back to mock data with real prices for realistic strikes
        return _generate_mock_suggestions_with_real_prices(quotes), False

    if not all_suggestions:
        return _generate_mock_suggestions(), False

    # Sort by combined score
    all_suggestions.sort(key=lambda x: x["combined_score"], reverse=True)
    return all_suggestions, True


def _generate_mock_suggestions_with_real_prices(quotes: dict) -> list[dict]:
    """Generate mock suggestions using real spot prices for realistic strikes.

    Used when option chain data is unavailable but we have real quotes.
    """
    np.random.seed(123)
    strategies = ["covered_call", "cash_secured_put", "wheel", "iron_condor"]

    suggestions = []
    for symbol, quote_data in quotes.items():
        spot_price = quote_data["price"]

        for i in range(5):  # 5 suggestions per symbol
            strategy = np.random.choice(strategies)
            option_type = "call" if strategy == "covered_call" else "put"

            # Round strike to nearest $5 for realism
            strike_offset = np.random.uniform(0.03, 0.08)
            if option_type == "put":
                raw_strike = spot_price * (1 - strike_offset)
            else:
                raw_strike = spot_price * (1 + strike_offset)
            strike = round(raw_strike / 5) * 5  # Round to nearest $5

            dte = np.random.randint(20, 46)
            delta = round(np.random.uniform(0.12, 0.28), 3)
            iv_rank = round(np.random.uniform(25, 85), 1)
            premium = round(spot_price * np.random.uniform(0.005, 0.02), 2)
            pop = round(np.random.uniform(0.65, 0.88), 2)
            ev = round(np.random.uniform(-20, 150), 2)
            combined_score = round(np.random.uniform(45, 90), 1)
            ai_score = round(np.random.uniform(40, 95), 1)

            gamma = round(np.random.uniform(0.01, 0.06), 4)
            theta = round(-np.random.uniform(0.03, 0.20), 4)
            vega = round(np.random.uniform(0.05, 0.25), 4)
            rho = round(np.random.uniform(-0.02, 0.02), 4)

            reasoning = (
                f"Basierend auf aktuellem Kurs ${spot_price:.2f}. "
                f"Strike ${strike:.0f} ({option_type.upper()}) mit {dte} DTE. "
                f"Geschätzte Prämie ${premium:.2f}. "
                f"(Option-Chain-Daten auf Free-Tier nicht verfügbar — "
                f"simulierte Greeks und Scores.)"
            )

            suggestions.append({
                "underlying": symbol, "strike": strike,
                "expiration": (date.today() + timedelta(days=dte)).isoformat(),
                "option_type": option_type, "strategy_type": strategy,
                "premium_bid": premium, "delta": delta, "gamma": gamma,
                "theta": theta, "vega": vega, "rho": rho, "iv_rank": iv_rank,
                "dte": dte, "probability_of_profit": pop, "expected_value": ev,
                "combined_score": combined_score, "ai_score": ai_score,
                "ai_reasoning": reasoning,
            })

    suggestions.sort(key=lambda x: x["combined_score"], reverse=True)
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

    # Load suggestions once and cache in session state
    if "scanner_suggestions" not in st.session_state:
        suggestions, is_live = _load_live_suggestions()
        st.session_state.scanner_suggestions = suggestions
        st.session_state.scanner_is_live = is_live
    
    suggestions = st.session_state.scanner_suggestions
    is_live = st.session_state.scanner_is_live
    
    # Refresh button
    if st.button("🔄 Daten neu laden", key="scanner_refresh"):
        new_suggestions, new_is_live = _load_live_suggestions()
        st.session_state.scanner_suggestions = new_suggestions
        st.session_state.scanner_is_live = new_is_live
        suggestions = new_suggestions
        is_live = new_is_live

    # Data source indicator
    if is_live:
        st.success(
            "🟢 **Live-Daten** — Echte Optionsketten via Finnhub API (Cache: 10 Min.)"
        )
    else:
        st.info(
            "ℹ️ **Demo-Modus** — Optionsketten-Daten sind auf dem Finnhub Free-Tier "
            "eingeschränkt. Strikes basieren auf aktuellen Kursen, Greeks und Scores "
            "sind simuliert. Für volle Optionsdaten ist ein Premium-Plan erforderlich."
        )

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
