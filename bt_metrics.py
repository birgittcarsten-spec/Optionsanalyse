"""Performance-Metriken für Backtesting-Ergebnisse.

Berechnet CAGR, Sharpe Ratio, Max Drawdown, Win Rate und Profit Factor.
"""

import numpy as np
import pandas as pd


def calculate_metrics(equity_curve: pd.Series, trades: pd.DataFrame) -> dict:
    """Performance-Metriken aus Equity Curve und Trades berechnen."""
    cagr = _calculate_cagr(equity_curve)
    sharpe_ratio = _calculate_sharpe_ratio(equity_curve)
    max_drawdown = _calculate_max_drawdown(equity_curve)
    win_rate = _calculate_win_rate(trades)
    profit_factor = _calculate_profit_factor(trades)

    return {
        "cagr": cagr,
        "sharpe_ratio": sharpe_ratio,
        "max_drawdown": max_drawdown,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
    }


def _calculate_cagr(equity_curve: pd.Series) -> float:
    """CAGR berechnen."""
    if len(equity_curve) < 2:
        return 0.0

    initial_value = equity_curve.iloc[0]
    final_value = equity_curve.iloc[-1]

    if initial_value <= 0:
        return 0.0

    num_days = len(equity_curve) - 1
    years = num_days / 252.0

    if years <= 0:
        return 0.0

    ratio = final_value / initial_value
    if ratio <= 0:
        return -1.0

    cagr = ratio ** (1.0 / years) - 1.0
    return float(cagr)


def _calculate_sharpe_ratio(equity_curve: pd.Series) -> float:
    """Sharpe Ratio berechnen."""
    if len(equity_curve) < 3:
        return 0.0

    returns = equity_curve.pct_change().dropna()

    if len(returns) == 0:
        return 0.0

    std_returns = returns.std()
    if std_returns == 0 or np.isnan(std_returns):
        return 0.0

    mean_returns = returns.mean()
    sharpe = (mean_returns / std_returns) * np.sqrt(252)
    return float(sharpe)


def _calculate_max_drawdown(equity_curve: pd.Series) -> float:
    """Max Drawdown berechnen."""
    if len(equity_curve) < 2:
        return 0.0

    cumulative_max = equity_curve.cummax()
    drawdown = (equity_curve - cumulative_max) / cumulative_max
    max_dd = drawdown.min()
    return float(max_dd) if not np.isnan(max_dd) else 0.0


def _calculate_win_rate(trades: pd.DataFrame) -> float:
    """Win Rate berechnen."""
    if trades.empty or "pnl" not in trades.columns:
        return 0.0

    total_trades = len(trades)
    if total_trades == 0:
        return 0.0

    winning_trades = (trades["pnl"] > 0).sum()
    return float(winning_trades / total_trades * 100.0)


def _calculate_profit_factor(trades: pd.DataFrame) -> float:
    """Profit Factor berechnen."""
    if trades.empty or "pnl" not in trades.columns:
        return 0.0

    gross_profit = trades.loc[trades["pnl"] > 0, "pnl"].sum()
    gross_loss = abs(trades.loc[trades["pnl"] < 0, "pnl"].sum())

    if gross_loss == 0:
        return float("inf") if gross_profit > 0 else 0.0

    return float(gross_profit / gross_loss)
