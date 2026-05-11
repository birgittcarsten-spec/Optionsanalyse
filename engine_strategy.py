"""Strategy Engine - Identifikation und Filterung von Handelsvorschlägen.

Filtert Optionsketten basierend auf konfigurierbaren Strategieparametern
und berechnet einen kombinierten Score aus Prämie, Wahrscheinlichkeit und Risiko.
"""

import logging
from dataclasses import dataclass
from datetime import date
from typing import Optional

import pandas as pd

from model_trade import TradeSuggestion

logger = logging.getLogger("strategy_engine")


@dataclass
class StrategyFilter:
    """Filterkriterien für eine Strategie."""

    min_iv_rank: float
    max_iv_rank: float
    min_delta: float
    max_delta: float
    min_dte: int
    max_dte: int
    exclude_earnings_within_days: Optional[int] = None


class StrategyEngine:
    """Strategieerkennung, Filterung und Scoring."""

    def __init__(self, config: dict):
        self.config = config
        self.filters = self._load_filters(config)
        self.scoring_weights = self._load_scoring_weights(config)

    def scan_covered_calls(
        self,
        enriched_chain: pd.DataFrame,
        volatility_data: dict,
    ) -> list[TradeSuggestion]:
        """Covered Call Vorschläge generieren."""
        strategy_filter = self.filters.get("covered_call")
        if strategy_filter is None:
            logger.warning("Keine Filter für covered_call konfiguriert")
            return []

        weights = self.scoring_weights.get(
            "covered_call", {"premium": 0.4, "probability": 0.35, "risk": 0.25}
        )

        calls = enriched_chain[enriched_chain["option_type"] == "call"].copy()
        if calls.empty:
            return []

        filtered = self._apply_filter(calls, strategy_filter, volatility_data)
        return self._build_suggestions(
            filtered, volatility_data, "covered_call", "call", weights
        )

    def scan_cash_secured_puts(
        self,
        enriched_chain: pd.DataFrame,
        volatility_data: dict,
        earnings: dict[str, list[date]],
    ) -> list[TradeSuggestion]:
        """Cash Secured Put Vorschläge generieren."""
        strategy_filter = self.filters.get("cash_secured_put")
        if strategy_filter is None:
            logger.warning("Keine Filter für cash_secured_put konfiguriert")
            return []

        weights = self.scoring_weights.get(
            "cash_secured_put", {"premium": 0.35, "probability": 0.40, "risk": 0.25}
        )

        puts = enriched_chain[enriched_chain["option_type"] == "put"].copy()
        if puts.empty:
            return []

        filtered = self._apply_filter(
            puts, strategy_filter, volatility_data, earnings
        )
        return self._build_suggestions(
            filtered, volatility_data, "cash_secured_put", "put", weights
        )

    def scan_wheel_strategy(
        self,
        enriched_chain: pd.DataFrame,
        volatility_data: dict,
    ) -> list[TradeSuggestion]:
        """Wheel Strategy Vorschläge generieren."""
        strategy_filter = self.filters.get("wheel")
        if strategy_filter is None:
            logger.warning("Keine Filter für wheel konfiguriert")
            return []

        weights = self.scoring_weights.get(
            "wheel", {"premium": 0.35, "probability": 0.35, "risk": 0.30}
        )

        puts = enriched_chain[enriched_chain["option_type"] == "put"].copy()
        if puts.empty:
            return []

        filtered = self._apply_filter(puts, strategy_filter, volatility_data)
        return self._build_suggestions(
            filtered, volatility_data, "wheel", "put", weights
        )

    def scan_iron_condors(
        self,
        enriched_chain: pd.DataFrame,
        volatility_data: dict,
    ) -> list[TradeSuggestion]:
        """Iron Condor Vorschläge generieren."""
        strategy_filter = self.filters.get("iron_condor")
        if strategy_filter is None:
            logger.warning("Keine Filter für iron_condor konfiguriert")
            return []

        weights = self.scoring_weights.get(
            "iron_condor", {"premium": 0.30, "probability": 0.45, "risk": 0.25}
        )

        filtered = self._apply_filter(
            enriched_chain, strategy_filter, volatility_data
        )
        return self._build_suggestions(
            filtered, volatility_data, "iron_condor", None, weights
        )

    def calculate_combined_score(
        self,
        premium: float,
        probability: float,
        risk: float,
        weights: Optional[dict[str, float]] = None,
    ) -> float:
        """Kombinierten Score berechnen."""
        if weights is None:
            weights = {"premium": 0.4, "probability": 0.35, "risk": 0.25}

        premium = max(0.0, min(1.0, premium))
        probability = max(0.0, min(1.0, probability))
        risk = max(0.0, min(1.0, risk))

        score = (
            weights["premium"] * premium
            + weights["probability"] * probability
            + weights["risk"] * risk
        ) * 100.0

        return round(max(0.0, min(100.0, score)), 2)

    def _apply_filter(
        self,
        chain: pd.DataFrame,
        strategy_filter: StrategyFilter,
        volatility_data: dict,
        earnings: Optional[dict[str, list[date]]] = None,
    ) -> pd.DataFrame:
        """Filterkriterien auf Option Chain anwenden."""
        if chain.empty:
            return chain

        filtered = chain.copy()

        filtered = filtered[
            (filtered["dte"] >= strategy_filter.min_dte)
            & (filtered["dte"] <= strategy_filter.max_dte)
        ]

        filtered = filtered[
            (filtered["delta"].abs() >= strategy_filter.min_delta)
            & (filtered["delta"].abs() <= strategy_filter.max_delta)
        ]

        if volatility_data:
            valid_underlyings = [
                symbol
                for symbol, data in volatility_data.items()
                if data.get("iv_rank", 0) >= strategy_filter.min_iv_rank
                and data.get("iv_rank", 0) <= strategy_filter.max_iv_rank
            ]
            filtered = filtered[filtered["underlying"].isin(valid_underlyings)]

        if (
            strategy_filter.exclude_earnings_within_days is not None
            and earnings is not None
        ):
            filtered = self._exclude_earnings(
                filtered, earnings, strategy_filter.exclude_earnings_within_days
            )

        return filtered

    def _exclude_earnings(
        self,
        chain: pd.DataFrame,
        earnings: dict[str, list[date]],
        exclude_days: int,
    ) -> pd.DataFrame:
        """Optionen nahe Earnings ausschließen."""
        if chain.empty:
            return chain

        today = date.today()
        exclude_symbols = set()

        for symbol, dates in earnings.items():
            for earnings_date in dates:
                if isinstance(earnings_date, date):
                    days_until = (earnings_date - today).days
                    if 0 <= days_until <= exclude_days:
                        exclude_symbols.add(symbol)
                        break

        if exclude_symbols:
            chain = chain[~chain["underlying"].isin(exclude_symbols)]

        return chain

    def _build_suggestions(
        self,
        filtered: pd.DataFrame,
        volatility_data: dict,
        strategy_type: str,
        option_type: Optional[str],
        weights: dict[str, float],
    ) -> list[TradeSuggestion]:
        """TradeSuggestion-Objekte aus gefiltertem DataFrame erstellen."""
        if filtered.empty:
            return []

        suggestions = []
        max_bid = filtered["bid"].max() if filtered["bid"].max() > 0 else 1.0

        for _, row in filtered.iterrows():
            underlying = row["underlying"]
            iv_rank = volatility_data.get(underlying, {}).get("iv_rank", 0.0)

            premium_score = row["bid"] / max_bid if max_bid > 0 else 0.0

            abs_delta = abs(row["delta"])
            probability_score = 1.0 - abs_delta

            dte_score = 1.0 - abs(row["dte"] - 30) / 30.0
            dte_score = max(0.0, min(1.0, dte_score))
            risk_score = dte_score

            combined_score = self.calculate_combined_score(
                premium_score, probability_score, risk_score, weights
            )

            probability_of_profit = round(1.0 - abs_delta, 2)

            premium_bid = row["bid"]
            max_loss = row["strike"] * 0.1
            expected_value = round(
                probability_of_profit * premium_bid
                - (1.0 - probability_of_profit) * max_loss,
                2,
            )

            expiration = row["expiration"]
            if isinstance(expiration, str):
                expiration = date.fromisoformat(expiration)

            actual_option_type = option_type if option_type else row["option_type"]

            suggestion = TradeSuggestion(
                underlying=underlying,
                strike=float(row["strike"]),
                expiration=expiration,
                option_type=actual_option_type,
                strategy_type=strategy_type,
                premium_bid=float(row["bid"]),
                delta=float(row["delta"]),
                iv_rank=float(iv_rank),
                dte=int(row["dte"]),
                probability_of_profit=probability_of_profit,
                expected_value=expected_value,
                combined_score=combined_score,
            )
            suggestions.append(suggestion)

        suggestions.sort(key=lambda s: s.combined_score, reverse=True)
        return suggestions

    def _load_filters(self, config: dict) -> dict[str, StrategyFilter]:
        """Strategiefilter aus Konfiguration laden."""
        filters = {}
        strategies = config.get("strategies", {})

        for strategy_name, strategy_config in strategies.items():
            filter_config = strategy_config.get("filters", strategy_config)
            try:
                strategy_filter = StrategyFilter(
                    min_iv_rank=float(filter_config.get("min_iv_rank", 0)),
                    max_iv_rank=float(filter_config.get("max_iv_rank", 100)),
                    min_delta=float(filter_config.get("min_delta", 0.10)),
                    max_delta=float(filter_config.get("max_delta", 0.30)),
                    min_dte=int(filter_config.get("min_dte", 20)),
                    max_dte=int(filter_config.get("max_dte", 45)),
                    exclude_earnings_within_days=(
                        int(filter_config["exclude_earnings_days"])
                        if filter_config.get("exclude_earnings_days") is not None
                        else None
                    ),
                )
                filters[strategy_name] = strategy_filter
            except (ValueError, TypeError) as e:
                logger.error(
                    "Fehler beim Laden der Filter für %s: %s", strategy_name, e
                )

        return filters

    def _load_scoring_weights(self, config: dict) -> dict[str, dict[str, float]]:
        """Scoring-Gewichtungen aus Konfiguration laden."""
        weights = {}
        strategies = config.get("strategies", {})

        for strategy_name, strategy_config in strategies.items():
            scoring = strategy_config.get("scoring", {})
            weights[strategy_name] = {
                "premium": float(scoring.get("premium_weight", 0.4)),
                "probability": float(scoring.get("probability_weight", 0.35)),
                "risk": float(scoring.get("risk_weight", 0.25)),
            }

        return weights
