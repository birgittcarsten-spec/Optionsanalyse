"""Risk Analyzer - Berechnung von Risikokennzahlen für Portfolio und Trades.

Berechnet Max Drawdown, Value at Risk (VaR), Conditional VaR (CVaR),
Margin Usage und Portfolio Exposure.
"""

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from model_trade import TradeSuggestion

logger = logging.getLogger("risk_analyzer")


@dataclass
class RiskMetrics:
    """Risikokennzahlen für ein Portfolio."""

    max_drawdown: float
    var_95: float
    cvar_95: float
    margin_usage: float
    portfolio_exposure: float


@dataclass
class RiskWarning:
    """Risikowarnung bei Schwellenwertüberschreitung."""

    metric: str
    current_value: float
    threshold: float
    message: str


class RiskAnalyzer:
    """Portfolio-Risikoanalyse."""

    def __init__(self, config: dict):
        self.margin_threshold = config.get("margin_threshold", 0.80)
        self.var_threshold = config.get("var_threshold", 0.05)
        self.total_margin = config.get("total_margin", 100_000.0)

    def calculate_risk_metrics(
        self, portfolio: pd.DataFrame, market_data: pd.DataFrame
    ) -> RiskMetrics:
        """Risikokennzahlen für das Gesamtportfolio berechnen."""
        returns = self._extract_returns(market_data)
        max_drawdown = self._calculate_max_drawdown(market_data)
        var_95 = self.calculate_var(returns, confidence=0.95)
        cvar_95 = self.calculate_cvar(returns, confidence=0.95)
        margin_usage = self._calculate_margin_usage(portfolio)
        portfolio_exposure = self._calculate_portfolio_exposure(portfolio)

        return RiskMetrics(
            max_drawdown=max_drawdown,
            var_95=var_95,
            cvar_95=cvar_95,
            margin_usage=margin_usage,
            portfolio_exposure=portfolio_exposure,
        )

    def simulate_trade_impact(
        self,
        current_metrics: RiskMetrics,
        new_trade: TradeSuggestion,
        portfolio: pd.DataFrame,
    ) -> RiskMetrics:
        """Auswirkung eines neuen Trades auf das Portfolio-Risiko simulieren."""
        trade_exposure = new_trade.strike * 100
        new_exposure = current_metrics.portfolio_exposure + trade_exposure

        margin_for_trade = self._estimate_margin_requirement(new_trade)
        current_margin_used = current_metrics.margin_usage * self.total_margin
        new_margin_used = current_margin_used + margin_for_trade
        new_margin_usage = min(new_margin_used / self.total_margin, 1.0)

        if current_metrics.portfolio_exposure > 0:
            exposure_ratio = new_exposure / current_metrics.portfolio_exposure
        else:
            exposure_ratio = 1.0

        new_var = current_metrics.var_95 * exposure_ratio
        new_cvar = current_metrics.cvar_95 * exposure_ratio
        new_max_drawdown = current_metrics.max_drawdown

        return RiskMetrics(
            max_drawdown=new_max_drawdown,
            var_95=new_var,
            cvar_95=new_cvar,
            margin_usage=new_margin_usage,
            portfolio_exposure=new_exposure,
        )

    def check_thresholds(self, metrics: RiskMetrics) -> list[RiskWarning]:
        """Schwellenwerte prüfen und Warnungen generieren."""
        warnings: list[RiskWarning] = []

        if metrics.margin_usage > self.margin_threshold:
            warnings.append(
                RiskWarning(
                    metric="margin_usage",
                    current_value=metrics.margin_usage,
                    threshold=self.margin_threshold,
                    message=(
                        f"Margin-Auslastung ({metrics.margin_usage:.1%}) "
                        f"überschreitet Schwellenwert ({self.margin_threshold:.1%})"
                    ),
                )
            )

        if metrics.var_95 > self.var_threshold:
            warnings.append(
                RiskWarning(
                    metric="var_95",
                    current_value=metrics.var_95,
                    threshold=self.var_threshold,
                    message=(
                        f"Value at Risk ({metrics.var_95:.4f}) "
                        f"überschreitet Schwellenwert ({self.var_threshold:.4f})"
                    ),
                )
            )

        return warnings

    def calculate_var(
        self, returns: pd.Series, confidence: float = 0.95
    ) -> float:
        """Value at Risk berechnen (historische Methode)."""
        if returns.empty or len(returns) < 2:
            return 0.0

        clean_returns = returns.dropna()
        if clean_returns.empty:
            return 0.0

        alpha = 1 - confidence
        var = -float(np.percentile(clean_returns, alpha * 100))

        return max(var, 0.0)

    def calculate_cvar(
        self, returns: pd.Series, confidence: float = 0.95
    ) -> float:
        """Conditional Value at Risk berechnen (Expected Shortfall)."""
        if returns.empty or len(returns) < 2:
            return 0.0

        clean_returns = returns.dropna()
        if clean_returns.empty:
            return 0.0

        alpha = 1 - confidence
        var_threshold = float(np.percentile(clean_returns, alpha * 100))

        tail_returns = clean_returns[clean_returns <= var_threshold]

        if tail_returns.empty:
            return max(-var_threshold, 0.0)

        cvar = -float(tail_returns.mean())
        return max(cvar, 0.0)

    def _extract_returns(self, market_data: pd.DataFrame) -> pd.Series:
        """Returns aus Marktdaten extrahieren."""
        if "returns" in market_data.columns:
            return market_data["returns"].dropna()

        if "close" in market_data.columns:
            prices = market_data["close"].dropna()
            if len(prices) < 2:
                return pd.Series(dtype=float)
            returns = prices.pct_change().dropna()
            return returns

        return pd.Series(dtype=float)

    def _calculate_max_drawdown(self, market_data: pd.DataFrame) -> float:
        """Maximalen Drawdown aus Marktdaten berechnen."""
        if "portfolio_value" in market_data.columns:
            values = market_data["portfolio_value"].dropna()
        elif "close" in market_data.columns:
            values = market_data["close"].dropna()
        else:
            return 0.0

        if len(values) < 2:
            return 0.0

        cumulative_max = values.cummax()
        drawdown = (cumulative_max - values) / cumulative_max
        max_dd = float(drawdown.max())

        return max(max_dd, 0.0)

    def _calculate_margin_usage(self, portfolio: pd.DataFrame) -> float:
        """Margin-Auslastung berechnen."""
        if portfolio.empty:
            return 0.0

        open_positions = portfolio[portfolio["status"] == "open"]
        if open_positions.empty:
            return 0.0

        margin_used = (open_positions["strike"] * 100 * 0.20).sum()
        usage = margin_used / self.total_margin
        return min(float(usage), 1.0)

    def _calculate_portfolio_exposure(self, portfolio: pd.DataFrame) -> float:
        """Portfolio Exposure berechnen."""
        if portfolio.empty:
            return 0.0

        open_positions = portfolio[portfolio["status"] == "open"]
        if open_positions.empty:
            return 0.0

        exposure = (open_positions["strike"] * 100).sum()
        return float(exposure)

    def _estimate_margin_requirement(self, trade: TradeSuggestion) -> float:
        """Geschätzten Margin-Bedarf für einen Trade berechnen."""
        notional = trade.strike * 100
        margin = notional * 0.20 - trade.premium_bid * 100
        return max(margin, 0.0)
