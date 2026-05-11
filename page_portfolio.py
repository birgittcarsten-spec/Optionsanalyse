"""Portfolio-Seite für das ThetaFlow AI Dashboard.

Offene Positionen anzeigen, P&L-Berechnung, Risikokennzahlen visualisieren.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import date, datetime, timedelta


def _generate_mock_positions() -> list[dict]:
    """Mock Portfolio-Positionen für Demo-Betrieb generieren."""
    np.random.seed(77)
    positions = [
        {"underlying": "AAPL", "strategy_type": "cash_secured_put", "entry_date": (date.today() - timedelta(days=15)).isoformat(), "strike": 170.00, "expiration": (date.today() + timedelta(days=20)).isoformat(), "premium_received": 2.85, "current_value": 1.20, "pnl": 165.00, "pnl_pct": 57.89, "status": "open"},
        {"underlying": "MSFT", "strategy_type": "covered_call", "entry_date": (date.today() - timedelta(days=10)).isoformat(), "strike": 430.00, "expiration": (date.today() + timedelta(days=25)).isoformat(), "premium_received": 4.50, "current_value": 3.10, "pnl": 140.00, "pnl_pct": 31.11, "status": "open"},
        {"underlying": "SPY", "strategy_type": "iron_condor", "entry_date": (date.today() - timedelta(days=22)).isoformat(), "strike": 500.00, "expiration": (date.today() + timedelta(days=8)).isoformat(), "premium_received": 3.20, "current_value": 0.80, "pnl": 240.00, "pnl_pct": 75.00, "status": "open"},
        {"underlying": "TSLA", "strategy_type": "cash_secured_put", "entry_date": (date.today() - timedelta(days=5)).isoformat(), "strike": 230.00, "expiration": (date.today() + timedelta(days=30)).isoformat(), "premium_received": 5.80, "current_value": 7.20, "pnl": -140.00, "pnl_pct": -24.14, "status": "open"},
        {"underlying": "NVDA", "strategy_type": "covered_call", "entry_date": (date.today() - timedelta(days=30)).isoformat(), "strike": 900.00, "expiration": (date.today() - timedelta(days=2)).isoformat(), "premium_received": 12.50, "current_value": 0.00, "pnl": 1250.00, "pnl_pct": 100.00, "status": "closed"},
        {"underlying": "QQQ", "strategy_type": "wheel", "entry_date": (date.today() - timedelta(days=40)).isoformat(), "strike": 420.00, "expiration": (date.today() - timedelta(days=5)).isoformat(), "premium_received": 3.90, "current_value": 0.00, "pnl": 390.00, "pnl_pct": 100.00, "status": "rolled"},
    ]
    return positions


def _generate_mock_risk_metrics() -> dict:
    return {"max_drawdown": -0.08, "var_95": -0.032, "cvar_95": -0.048, "margin_usage": 0.62, "portfolio_exposure": 125000.0}


def _generate_mock_equity_curve() -> pd.Series:
    np.random.seed(55)
    dates = pd.date_range(end=datetime.now(), periods=60, freq="B")
    initial = 100000
    returns = np.random.normal(0.001, 0.008, len(dates))
    values = initial * np.cumprod(1 + returns)
    return pd.Series(values, index=dates, name="portfolio_value")


def _generate_mock_risk_warnings(risk_metrics: dict) -> list[dict]:
    warnings = []
    if risk_metrics["margin_usage"] >= 0.80:
        warnings.append({"metric": "Margin Usage", "current_value": risk_metrics["margin_usage"], "threshold": 0.80, "message": f"Margin-Auslastung bei {risk_metrics['margin_usage']:.0%} - Schwellenwert 80% überschritten!", "severity": "high"})
    if abs(risk_metrics["var_95"]) >= 0.05:
        warnings.append({"metric": "VaR (95%)", "current_value": risk_metrics["var_95"], "threshold": 0.05, "message": f"Value at Risk bei {risk_metrics['var_95']:.1%} - Schwellenwert 5.0% erreicht.", "severity": "medium"})
    return warnings


def _render_portfolio_performance(equity_curve: pd.Series):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=equity_curve.index, y=equity_curve.values, mode="lines", name="Portfolio-Wert", line=dict(color="#6366f1", width=2), fill="tozeroy", fillcolor="rgba(99, 102, 241, 0.1)"))
    fig.update_layout(title="Portfolio-Performance (60 Tage)", xaxis_title="Datum", yaxis_title="Portfolio-Wert ($)", template="plotly_white", height=350, yaxis_tickformat="$,.0f")
    st.plotly_chart(fig, use_container_width=True)


def _render_pnl_chart(positions: list[dict]):
    open_positions = [p for p in positions if p["status"] == "open"]
    if not open_positions:
        return
    fig = go.Figure()
    symbols = [p["underlying"] for p in open_positions]
    pnls = [p["pnl"] for p in open_positions]
    colors = ["#22c55e" if pnl >= 0 else "#ef4444" for pnl in pnls]
    fig.add_trace(go.Bar(x=symbols, y=pnls, marker_color=colors, text=[f"${pnl:+.0f}" for pnl in pnls], textposition="auto", name="P&L"))
    fig.update_layout(title="P&L nach Position (offene Positionen)", xaxis_title="Underlying", yaxis_title="P&L ($)", template="plotly_white", height=300)
    st.plotly_chart(fig, use_container_width=True)


def _render_risk_gauge(risk_metrics: dict):
    col1, col2 = st.columns(2)
    with col1:
        fig = go.Figure(go.Indicator(mode="gauge+number+delta", value=risk_metrics["margin_usage"] * 100, title={"text": "Margin-Auslastung (%)"}, number={"suffix": "%"}, gauge={"axis": {"range": [0, 100]}, "bar": {"color": "#6366f1"}, "steps": [{"range": [0, 50], "color": "#d1fae5"}, {"range": [50, 80], "color": "#fef3c7"}, {"range": [80, 100], "color": "#fee2e2"}], "threshold": {"line": {"color": "red", "width": 4}, "thickness": 0.75, "value": 80}}))
        fig.update_layout(height=250, margin=dict(t=40, b=0))
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        fig = go.Figure(go.Indicator(mode="gauge+number", value=abs(risk_metrics["var_95"]) * 100, title={"text": "Value at Risk 95% (%)"}, number={"suffix": "%"}, gauge={"axis": {"range": [0, 10]}, "bar": {"color": "#f59e0b"}, "steps": [{"range": [0, 3], "color": "#d1fae5"}, {"range": [3, 5], "color": "#fef3c7"}, {"range": [5, 10], "color": "#fee2e2"}], "threshold": {"line": {"color": "red", "width": 4}, "thickness": 0.75, "value": 5}}))
        fig.update_layout(height=250, margin=dict(t=40, b=0))
        st.plotly_chart(fig, use_container_width=True)


def render_portfolio():
    """Portfolio-Seite rendern."""
    st.title("💼 Portfolio")
    st.caption("Offene Positionen, P&L und Risikokennzahlen")

    positions = _generate_mock_positions()
    risk_metrics = _generate_mock_risk_metrics()
    equity_curve = _generate_mock_equity_curve()
    warnings = _generate_mock_risk_warnings(risk_metrics)

    if warnings:
        for warning in warnings:
            if warning["severity"] == "high":
                st.error(f"⚠️ {warning['message']}")
            else:
                st.warning(f"⚡ {warning['message']}")

    open_positions = [p for p in positions if p["status"] == "open"]
    total_pnl = sum(p["pnl"] for p in open_positions)
    total_premium = sum(p["premium_received"] * 100 for p in open_positions)

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Offene Positionen", len(open_positions))
    with col2:
        st.metric("Gesamt P&L", f"${total_pnl:+,.0f}", delta=f"{total_pnl / total_premium * 100:.1f}%" if total_premium > 0 else "0%")
    with col3:
        st.metric("Max Drawdown", f"{risk_metrics['max_drawdown']:.1%}")
    with col4:
        st.metric("Margin-Auslastung", f"{risk_metrics['margin_usage']:.0%}")
    with col5:
        st.metric("Portfolio Exposure", f"${risk_metrics['portfolio_exposure']:,.0f}")

    st.markdown("---")

    tab1, tab2, tab3 = st.tabs(["📋 Positionen", "📈 Performance", "⚠️ Risiko"])

    with tab1:
        strategy_display = {"covered_call": "Covered Call", "cash_secured_put": "Cash Secured Put", "wheel": "Wheel", "iron_condor": "Iron Condor"}
        status_display = {"open": "🟢 Offen", "closed": "✅ Geschlossen", "rolled": "🔄 Gerollt"}
        table_data = []
        for p in positions:
            table_data.append({"Underlying": p["underlying"], "Strategie": strategy_display.get(p["strategy_type"], p["strategy_type"]), "Strike": f"${p['strike']:.2f}", "Eröffnung": p["entry_date"], "Verfall": p["expiration"], "Prämie": f"${p['premium_received']:.2f}", "Akt. Wert": f"${p['current_value']:.2f}", "P&L": f"${p['pnl']:+.0f}", "P&L %": f"{p['pnl_pct']:+.1f}%", "Status": status_display.get(p["status"], p["status"])})
        df = pd.DataFrame(table_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        _render_pnl_chart(positions)

    with tab2:
        _render_portfolio_performance(equity_curve)
        col1, col2, col3 = st.columns(3)
        with col1:
            total_return = (equity_curve.iloc[-1] / equity_curve.iloc[0] - 1) * 100
            st.metric("Gesamtrendite", f"{total_return:+.2f}%")
        with col2:
            daily_returns = equity_curve.pct_change().dropna()
            sharpe = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252)
            st.metric("Sharpe Ratio", f"{sharpe:.2f}")
        with col3:
            win_count = sum(1 for p in positions if p["pnl"] > 0)
            total_count = len(positions)
            st.metric("Win Rate", f"{win_count / total_count * 100:.0f}%")

    with tab3:
        _render_risk_gauge(risk_metrics)
        st.markdown("### Risikokennzahlen im Detail")
        risk_df = pd.DataFrame([
            {"Kennzahl": "Max Drawdown", "Wert": f"{risk_metrics['max_drawdown']:.2%}", "Schwellenwert": "N/A", "Status": "✅"},
            {"Kennzahl": "VaR (95%)", "Wert": f"{risk_metrics['var_95']:.2%}", "Schwellenwert": "5.0%", "Status": "✅" if abs(risk_metrics['var_95']) < 0.05 else "⚠️"},
            {"Kennzahl": "CVaR (95%)", "Wert": f"{risk_metrics['cvar_95']:.2%}", "Schwellenwert": "N/A", "Status": "✅"},
            {"Kennzahl": "Margin-Auslastung", "Wert": f"{risk_metrics['margin_usage']:.0%}", "Schwellenwert": "80%", "Status": "✅" if risk_metrics['margin_usage'] < 0.80 else "⚠️"},
            {"Kennzahl": "Portfolio Exposure", "Wert": f"${risk_metrics['portfolio_exposure']:,.0f}", "Schwellenwert": "N/A", "Status": "✅"},
        ])
        st.dataframe(risk_df, use_container_width=True, hide_index=True)
