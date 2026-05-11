"""Backtesting-Simulation für Stillhalter-Strategien.

Simuliert Strategien auf historischen Optionsketten mit Berücksichtigung
von Slippage und Transaktionsgebühren.
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Optional

from bt_metrics import calculate_metrics


@dataclass
class BacktestConfig:
    """Konfiguration für einen Backtest."""

    strategy_type: str
    start_date: str
    end_date: str
    initial_capital: float
    slippage_pct: float = 0.001
    commission_per_contract: float = 0.65
    enable_rolling: bool = True


@dataclass
class BacktestResult:
    """Ergebnis eines Backtests."""

    cagr: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    equity_curve: pd.Series
    trades: pd.DataFrame


class BacktestingEngine:
    """Backtesting-Simulation für Stillhalter-Strategien."""

    def __init__(self, config: BacktestConfig):
        self.config = config

    def run_backtest(
        self,
        historical_chains: pd.DataFrame,
        historical_prices: pd.DataFrame,
    ) -> BacktestResult:
        """Backtest durchführen."""
        capital = self.config.initial_capital
        trades_list: list[dict] = []
        equity_values: list[float] = []
        equity_dates: list = []

        start = pd.Timestamp(self.config.start_date)
        end = pd.Timestamp(self.config.end_date)

        historical_chains = historical_chains.copy()
        historical_prices = historical_prices.copy()

        if "date" in historical_chains.columns:
            historical_chains["date"] = pd.to_datetime(historical_chains["date"])
        if "date" in historical_prices.columns:
            historical_prices["date"] = pd.to_datetime(historical_prices["date"])

        chains_filtered = historical_chains[
            (historical_chains["date"] >= start) & (historical_chains["date"] <= end)
        ]
        prices_filtered = historical_prices[
            (historical_prices["date"] >= start) & (historical_prices["date"] <= end)
        ]

        trading_days = sorted(prices_filtered["date"].unique())
        active_position: Optional[dict] = None

        for day in trading_days:
            day_ts = pd.Timestamp(day)
            current_value = capital
            if active_position is not None:
                current_value = capital + self._position_value(active_position, day_ts, prices_filtered)

            equity_values.append(current_value)
            equity_dates.append(day_ts)

            if active_position is not None:
                expiration = pd.Timestamp(active_position["expiration"])
                if day_ts >= expiration:
                    trade_result = self._close_position(active_position, day_ts, prices_filtered)
                    capital += trade_result["pnl"]
                    trades_list.append(trade_result)
                    active_position = None
                elif self.config.enable_rolling and active_position.get("dte_remaining", 999) <= 5:
                    day_chains = chains_filtered[chains_filtered["date"] == day_ts]
                    if not day_chains.empty:
                        spot = self._get_spot_price(active_position["underlying"], day_ts, prices_filtered)
                        if self._is_itm(active_position, spot):
                            roll_result = self.simulate_rolling(active_position, day_chains)
                            if roll_result.get("rolled", False):
                                trade_result = self._close_position(active_position, day_ts, prices_filtered)
                                capital += trade_result["pnl"]
                                trades_list.append(trade_result)
                                active_position = roll_result["new_position"]
                                capital -= self._entry_cost(active_position)

            if active_position is None:
                day_chains = chains_filtered[chains_filtered["date"] == day_ts]
                if not day_chains.empty:
                    new_position = self._find_entry(day_chains, day_ts, prices_filtered)
                    if new_position is not None:
                        active_position = new_position
                        capital -= self._entry_cost(active_position)

            if active_position is not None:
                exp = pd.Timestamp(active_position["expiration"])
                active_position["dte_remaining"] = max(0, (exp - day_ts).days)

        equity_curve = pd.Series(
            data=equity_values,
            index=pd.DatetimeIndex(equity_dates),
            name="portfolio_value",
        )

        if trades_list:
            trades_df = pd.DataFrame(trades_list)
        else:
            trades_df = pd.DataFrame(columns=["entry_date", "exit_date", "underlying",
                                               "strike", "option_type", "premium",
                                               "exit_price", "pnl", "commission"])

        metrics = calculate_metrics(equity_curve, trades_df)

        return BacktestResult(
            cagr=metrics["cagr"],
            sharpe_ratio=metrics["sharpe_ratio"],
            max_drawdown=metrics["max_drawdown"],
            win_rate=metrics["win_rate"],
            profit_factor=metrics["profit_factor"],
            equity_curve=equity_curve,
            trades=trades_df,
        )

    def simulate_rolling(self, position: dict, next_chain: pd.DataFrame) -> dict:
        """Rolling-Strategie simulieren."""
        option_type = position.get("option_type", "put")
        underlying = position.get("underlying")

        candidates = next_chain[next_chain["option_type"] == option_type]
        if "underlying" in next_chain.columns and underlying:
            candidates = candidates[candidates["underlying"] == underlying]
        if "dte" in candidates.columns:
            candidates = candidates[candidates["dte"] > 10]

        if candidates.empty:
            return {"rolled": False, "new_position": None, "roll_credit": 0.0}

        current_strike = position.get("strike", 0)
        candidates = candidates.copy()
        candidates["strike_diff"] = abs(candidates["strike"] - current_strike)
        best_candidate = candidates.sort_values("strike_diff").iloc[0]

        new_premium = self._apply_slippage(float(best_candidate.get("bid", 0)), is_sell=True)
        commission = self.config.commission_per_contract * 2

        new_position = {
            "underlying": underlying,
            "strike": float(best_candidate["strike"]),
            "option_type": option_type,
            "expiration": best_candidate.get("expiration", position["expiration"]),
            "premium": new_premium,
            "entry_date": position.get("entry_date"),
            "dte_remaining": int(best_candidate.get("dte", 30)),
            "commission": commission,
        }

        roll_credit = new_premium - commission
        return {"rolled": True, "new_position": new_position, "roll_credit": roll_credit}

    def calculate_metrics(self, equity_curve: pd.Series, trades: pd.DataFrame) -> dict:
        """Performance-Metriken berechnen."""
        return calculate_metrics(equity_curve, trades)

    def _find_entry(self, day_chains, day, prices) -> Optional[dict]:
        """Einstiegspunkt für eine neue Position finden."""
        strategy = self.config.strategy_type
        if strategy in ("covered_call", "cash_secured_put", "wheel"):
            option_type = "call" if strategy == "covered_call" else "put"
        elif strategy == "iron_condor":
            option_type = "put"
        else:
            option_type = "put"

        candidates = day_chains[day_chains["option_type"] == option_type].copy()
        if "dte" in candidates.columns:
            candidates = candidates[(candidates["dte"] >= 20) & (candidates["dte"] <= 45)]
        if "delta" in candidates.columns:
            candidates = candidates[(candidates["delta"].abs() >= 0.10) & (candidates["delta"].abs() <= 0.30)]

        if candidates.empty:
            return None

        if "bid" in candidates.columns:
            best = candidates.sort_values("bid", ascending=False).iloc[0]
        else:
            best = candidates.iloc[0]

        premium = self._apply_slippage(float(best.get("bid", 0)), is_sell=True)
        underlying = best.get("underlying", "UNKNOWN")

        return {
            "underlying": underlying,
            "strike": float(best["strike"]),
            "option_type": option_type,
            "expiration": best.get("expiration"),
            "premium": premium,
            "entry_date": day,
            "dte_remaining": int(best.get("dte", 30)),
            "commission": self.config.commission_per_contract,
        }

    def _apply_slippage(self, price: float, is_sell: bool = True) -> float:
        """Slippage auf einen Preis anwenden."""
        if is_sell:
            return price * (1 - self.config.slippage_pct)
        else:
            return price * (1 + self.config.slippage_pct)

    def _entry_cost(self, position: dict) -> float:
        """Kosten für den Einstieg berechnen."""
        commission = position.get("commission", self.config.commission_per_contract)
        premium = position.get("premium", 0)
        return commission - premium * 100

    def _close_position(self, position, day, prices) -> dict:
        """Position schließen und Trade-Ergebnis berechnen."""
        underlying = position.get("underlying", "UNKNOWN")
        spot = self._get_spot_price(underlying, day, prices)
        strike = position.get("strike", 0)
        option_type = position.get("option_type", "put")
        premium = position.get("premium", 0)

        if option_type == "put":
            intrinsic = max(0, strike - spot)
        else:
            intrinsic = max(0, spot - strike)

        close_commission = self.config.commission_per_contract
        pnl = (premium - intrinsic) * 100 - close_commission - position.get("commission", 0)

        return {
            "entry_date": position.get("entry_date"),
            "exit_date": day,
            "underlying": underlying,
            "strike": strike,
            "option_type": option_type,
            "premium": premium,
            "exit_price": intrinsic,
            "pnl": pnl,
            "commission": close_commission + position.get("commission", 0),
        }

    def _position_value(self, position, day, prices) -> float:
        """Aktuellen Wert einer offenen Position berechnen."""
        underlying = position.get("underlying", "UNKNOWN")
        spot = self._get_spot_price(underlying, day, prices)
        strike = position.get("strike", 0)
        option_type = position.get("option_type", "put")
        premium = position.get("premium", 0)

        if option_type == "put":
            intrinsic = max(0, strike - spot)
        else:
            intrinsic = max(0, spot - strike)

        unrealized_pnl = (premium - intrinsic) * 100
        return unrealized_pnl

    def _get_spot_price(self, underlying, day, prices) -> float:
        """Spot-Preis abrufen."""
        day_prices = prices[(prices["date"] == day) & (prices["underlying"] == underlying)]
        if not day_prices.empty:
            return float(day_prices["close"].iloc[0])

        prior_prices = prices[(prices["date"] <= day) & (prices["underlying"] == underlying)].sort_values("date", ascending=False)
        if not prior_prices.empty:
            return float(prior_prices["close"].iloc[0])
        return 0.0

    def _is_itm(self, position, spot) -> bool:
        """Prüfen ob eine Position In-The-Money ist."""
        strike = position.get("strike", 0)
        option_type = position.get("option_type", "put")
        if option_type == "put":
            return spot < strike
        else:
            return spot > strike
