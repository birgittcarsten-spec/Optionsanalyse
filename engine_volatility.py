"""Volatility Engine - Berechnung und Bewertung von Volatilitätskennzahlen.

Berechnet historische Volatilität (HV), extrahiert implizite Volatilität (IV),
berechnet IV Rank und IV Percentile, und weist eine Volatilitätsbewertung zu.
"""

import logging
from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger("volatility_engine")


class VolatilityRating(str, Enum):
    """Bewertungsstufen für die Volatilität eines Underlyings."""

    LOW = "niedrig"
    MEDIUM = "mittel"
    HIGH = "hoch"
    VERY_HIGH = "sehr hoch"


class VolatilityEngine:
    """Berechnung von Volatilitätskennzahlen."""

    DEFAULT_THRESHOLDS = {"low": 25.0, "medium": 50.0, "high": 75.0}

    def __init__(self, thresholds: Optional[dict[str, float]] = None):
        self.thresholds = thresholds or self.DEFAULT_THRESHOLDS.copy()

    def calculate_historical_volatility(
        self, prices: pd.Series, window: int
    ) -> float:
        """Historische Volatilität über ein Zeitfenster berechnen."""
        if window <= 0:
            raise ValueError(f"Window muss positiv sein, erhalten: {window}")

        if len(prices) < window + 1:
            raise ValueError(
                f"Mindestens {window + 1} Datenpunkte benötigt, "
                f"erhalten: {len(prices)}"
            )

        recent_prices = prices.iloc[-(window + 1):]
        log_returns = np.log(recent_prices / recent_prices.shift(1)).dropna()

        hv = float(log_returns.std(ddof=1) * np.sqrt(252))
        return hv

    def extract_implied_volatility(self, option_chain: pd.DataFrame) -> float:
        """Implizite Volatilität aus Optionspreisen extrahieren (ATM-IV)."""
        if option_chain.empty:
            raise ValueError("Option Chain ist leer")

        if "iv" not in option_chain.columns or "strike" not in option_chain.columns:
            raise ValueError(
                "Option Chain muss 'iv' und 'strike' Spalten enthalten"
            )

        valid_chain = option_chain.dropna(subset=["iv"])
        valid_chain = valid_chain[valid_chain["iv"] > 0]

        if valid_chain.empty:
            raise ValueError("Keine gültigen IV-Werte in der Option Chain")

        spot = None
        for col in ["underlying_price", "spot"]:
            if col in valid_chain.columns:
                spot_values = valid_chain[col].dropna()
                if not spot_values.empty:
                    spot = float(spot_values.iloc[0])
                    break

        if spot is None:
            spot = float(
                (valid_chain["strike"].min() + valid_chain["strike"].max()) / 2.0
            )

        valid_chain = valid_chain.copy()
        valid_chain["_distance"] = (valid_chain["strike"] - spot).abs()
        atm_row = valid_chain.loc[valid_chain["_distance"].idxmin()]

        atm_iv = float(atm_row["iv"])
        return atm_iv

    def calculate_iv_rank(
        self, current_iv: float, iv_history_52w: pd.Series
    ) -> float:
        """IV Rank berechnen."""
        if iv_history_52w.empty:
            raise ValueError("IV-Historie darf nicht leer sein")

        iv_min = float(iv_history_52w.min())
        iv_max = float(iv_history_52w.max())

        if iv_max == iv_min:
            return 50.0

        iv_rank = (current_iv - iv_min) / (iv_max - iv_min) * 100.0

        return float(np.clip(iv_rank, 0.0, 100.0))

    def calculate_iv_percentile(
        self, current_iv: float, iv_history_252d: pd.Series
    ) -> float:
        """IV Percentile berechnen."""
        if iv_history_252d.empty:
            raise ValueError("IV-Historie darf nicht leer sein")

        total_days = len(iv_history_252d)
        days_below = int((iv_history_252d < current_iv).sum())

        iv_percentile = (days_below / total_days) * 100.0
        return float(iv_percentile)

    def rate_volatility(self, iv_rank: float) -> VolatilityRating:
        """Volatilitätsbewertung basierend auf IV Rank zuweisen."""
        low_threshold = self.thresholds["low"]
        medium_threshold = self.thresholds["medium"]
        high_threshold = self.thresholds["high"]

        if iv_rank < low_threshold:
            return VolatilityRating.LOW
        elif iv_rank < medium_threshold:
            return VolatilityRating.MEDIUM
        elif iv_rank < high_threshold:
            return VolatilityRating.HIGH
        else:
            return VolatilityRating.VERY_HIGH
