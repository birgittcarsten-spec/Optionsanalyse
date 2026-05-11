"""Backtesting-Seite für das ThetaFlow AI Dashboard.

Strategie und Zeitraum auswählen, Backtest starten.
Ergebnisanzeige: CAGR, Sharpe Ratio, Max Drawdown, Win Rate, Profit Factor.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import date, timedelta


def _run_mock_backtest(strategy, start_date, end_date, initial_capital, slippage, commission) -> dict:
    """Mock-Backtest durchführen."""
    seed = hash((strategy, str(start_date), str(end_date), initial_capital)) % 2**31
    np.random.seed(seed)

    trading_days = pd.bdate_range(start=start_date, end=end_date)
    num_days = len(trading_days)
    if num_days < 10:
        return None

    strategy_params = {
        "covered_call": {"mean_return": 0.0004, "volatility": 0.006, "win_bias": 0.70},
        "cash_secured_put": {"mean_return": 0.0005, "volatility": 0.007, "win_bias": 0.72},
        "wheel": {"mean_return": 0.0005, "volatility": 0.008, "win_bias": 0.68},
        "iron_condor": {"mean_return": 0.0003, "volatility": 0.005, "win_bias": 0.75},
    }
    params = strategy_params.get(strategy, strategy_params["covered_call"])
    adjusted_mean = params["mean_return"] - slippage * 0.1 - commission * 0.0001

    daily_returns = np.random.normal(adjusted_mean, params["volatility"], num_days)
    equity_values = initial_capital * np.cumprod(1 + daily_returns)
    equity_curve = pd.Series(equity_values, index=trading_days, name="portfolio_value")

    num_trades = num_days // 25
    trades = []
    for i in range(max(1, num_trades)):
        is_win = np.random.random() < params["win_bias"]
        pnl = np.random.uniform(50, 500) if is_win else -np.random.uniform(100, 800)
        trade_date = start_date + timedelta(days=int(i * 25 + np.random.randint(0, 10)))
        trades.append({"entry_date": trade_date, "exit_date": trade_date + timedelta(days=np.random.randint(15, 40)), "underlying": np.random.choice(["AAPL", "MSFT", "SPY", "QQQ", "TSLA"]), "strike": round(np.random.uniform(100, 500), 2), "option_type": "put" if strategy != "covered_call" else "call", "premium": round(np.random.uniform(1.0, 8.0), 2), "pnl": pnl, "commission": commission * 2})

    trades_df = pd.DataFrame(trades)
    final_value = equity_curve.iloc[-1]
    years = num_days / 252.0
    cagr = (final_value / initial_capital) ** (1 / years) - 1 if years > 0 else 0
    returns = equity_curve.pct_change().dropna()
    sharpe = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() > 0 else 0
    cummax = equity_curve.cummax()
    drawdown = (equity_curve - cummax) / cummax
    max_drawdown = drawdown.min()
    winning_trades = sum(1 for t in trades if t["pnl"] > 0)
    win_rate = (winning_trades / len(trades) * 100) if trades else 0
    gross_profit = sum(t["pnl"] for t in trades if t["pnl"] > 0)
    gross_loss = abs(sum(t["pnl"] for t in trades if t["pnl"] < 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    return {"cagr": cagr, "sharpe_ratio": sharpe, "max_drawdown": max_drawdown, "win_rate": win_rate, "profit_factor": profit_factor, "equity_curve": equity_curve, "trades": trades_df, "total_trades": len(trades), "final_value": final_value}


def _render_equity_curve(result: dict):
    equity_curve = result["equity_curve"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=equity_curve.index, y=equity_curve.values, mode="lines", name="Portfolio-Wert", line=dict(color="#6366f1", width=2), fill="tozeroy", fillcolor="rgba(99, 102, 241, 0.08)"))
    cummax = equity_curve.cummax()
    fig.add_trace(go.Scatter(x=equity_curve.index, y=cummax.values, mode="lines", name="High Water Mark", line=dict(color="#94a3b8", width=1, dash="dot")))
    fig.update_layout(title="Equity Curve", xaxis_title="Datum", yaxis_title="Portfolio-Wert ($)", template="plotly_white", height=400, yaxis_tickformat="$,.0f", legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01))
    st.plotly_chart(fig, use_container_width=True)


def _render_drawdown_chart(result: dict):
    equity_curve = result["equity_curve"]
    cummax = equity_curve.cummax()
    drawdown = (equity_curve - cummax) / cummax
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=drawdown.index, y=drawdown.values * 100, mode="lines", name="Drawdown", line=dict(color="#ef4444", width=1.5), fill="tozeroy", fillcolor="rgba(239, 68, 68, 0.15)"))
    fig.update_layout(title="Drawdown", xaxis_title="Datum", yaxis_title="Drawdown (%)", template="plotly_white", height=250, yaxis_tickformat=".1f")
    st.plotly_chart(fig, use_container_width=True)


def render_backtesting():
    """Backtesting-Seite rendern."""
    st.title("📊 Backtesting")
    st.caption("Strategien auf historischen Daten testen und bewerten")

    st.markdown("### Backtest-Konfiguration")
    col1, col2, col3 = st.columns(3)
    with col1:
        strategy = st.selectbox("Strategie", options=["covered_call", "cash_secured_put", "wheel", "iron_condor"], format_func=lambda x: {"covered_call": "Covered Call", "cash_secured_put": "Cash Secured Put", "wheel": "Wheel Strategy", "iron_condor": "Iron Condor"}.get(x, x))
    with col2:
        start_date = st.date_input("Startdatum", value=date.today() - timedelta(days=365))
    with col3:
        end_date = st.date_input("Enddatum", value=date.today())

    col4, col5, col6 = st.columns(3)
    with col4:
        initial_capital = st.number_input("Anfangskapital ($)", min_value=1000, max_value=10000000, value=100000, step=10000)
    with col5:
        slippage = st.number_input("Slippage (%)", min_value=0.0, max_value=1.0, value=0.1, step=0.01, format="%.2f")
    with col6:
        commission = st.number_input("Kommission ($/Kontrakt)", min_value=0.0, max_value=10.0, value=0.65, step=0.05, format="%.2f")

    run_button = st.button("🚀 Backtest starten", type="primary", use_container_width=True)

    if run_button or st.session_state.get("backtest_result") is not None:
        if run_button:
            with st.spinner("Backtest wird durchgeführt..."):
                result = _run_mock_backtest(strategy=strategy, start_date=start_date, end_date=end_date, initial_capital=initial_capital, slippage=slippage / 100, commission=commission)
                st.session_state.backtest_result = result

        result = st.session_state.get("backtest_result")
        if result is None:
            st.error("Backtest konnte nicht durchgeführt werden. Bitte wählen Sie einen längeren Zeitraum.")
            return

        st.markdown("---")
        st.markdown("### Ergebnisse")

        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("CAGR", f"{result['cagr']:.2%}", delta="positiv" if result["cagr"] > 0 else "negativ")
        with col2:
            st.metric("Sharpe Ratio", f"{result['sharpe_ratio']:.2f}", delta="gut" if result["sharpe_ratio"] > 1 else None)
        with col3:
            st.metric("Max Drawdown", f"{result['max_drawdown']:.2%}")
        with col4:
            st.metric("Win Rate", f"{result['win_rate']:.1f}%")
        with col5:
            pf_display = f"{result['profit_factor']:.2f}" if result["profit_factor"] != float("inf") else "∞"
            st.metric("Profit Factor", pf_display)

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.metric("Trades gesamt", result["total_trades"])
        with col_b:
            st.metric("Endkapital", f"${result['final_value']:,.0f}")
        with col_c:
            profit = result["final_value"] - initial_capital
            st.metric("Gewinn/Verlust", f"${profit:+,.0f}")

        st.markdown("---")
        _render_equity_curve(result)
        _render_drawdown_chart(result)

        st.markdown("### Trade-Historie")
        if not result["trades"].empty:
            display_trades = result["trades"].copy()
            display_trades["entry_date"] = pd.to_datetime(display_trades["entry_date"]).dt.strftime("%Y-%m-%d")
            display_trades["exit_date"] = pd.to_datetime(display_trades["exit_date"]).dt.strftime("%Y-%m-%d")
            display_trades["pnl"] = display_trades["pnl"].apply(lambda x: f"${x:+,.0f}")
            display_trades["premium"] = display_trades["premium"].apply(lambda x: f"${x:.2f}")
            display_trades["strike"] = display_trades["strike"].apply(lambda x: f"${x:.2f}")
            display_trades["commission"] = display_trades["commission"].apply(lambda x: f"${x:.2f}")
            display_trades.columns = ["Eröffnung", "Schließung", "Underlying", "Strike", "Typ", "Prämie", "P&L", "Kommission"]
            st.dataframe(display_trades, use_container_width=True, hide_index=True)
        else:
            st.info("Keine Trades im gewählten Zeitraum.")
