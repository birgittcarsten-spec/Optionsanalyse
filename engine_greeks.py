"""Greeks Engine - Berechnung der Options-Greeks mittels Black-Scholes-Modell.

Berechnet Delta, Gamma, Theta, Vega und Rho für Optionskontrakte
und erweitert Option Chain DataFrames um die berechneten Greeks-Spalten.
"""

import logging
import math
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
from scipy.stats import norm

from util_validators import validate_option_params

logger = logging.getLogger("greeks_engine")


@dataclass
class GreeksResult:
    """Ergebnis der Greeks-Berechnung für einen Kontrakt."""

    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float


class GreeksEngine:
    """Berechnung der Options-Greeks mittels Black-Scholes-Modell."""

    def __init__(self, risk_free_rate: float = 0.05):
        self.risk_free_rate = risk_free_rate

    def calculate_greeks(
        self,
        spot: float,
        strike: float,
        dte: int,
        iv: float,
        option_type: str,
        risk_free_rate: Optional[float] = None,
    ) -> GreeksResult:
        """Greeks für einen einzelnen Kontrakt berechnen (Black-Scholes)."""
        validation = validate_option_params(spot, strike, dte, iv, option_type)
        if not validation.is_valid:
            raise ValueError(
                f"Ungültige Optionsparameter: {'; '.join(validation.errors)}"
            )

        r = risk_free_rate if risk_free_rate is not None else self.risk_free_rate
        t = dte / 365.0
        sigma = iv
        option_type_lower = option_type.lower()

        d1 = self._d1(spot, strike, t, r, sigma)
        d2 = self._d2(d1, sigma, t)

        if option_type_lower == "call":
            delta = norm.cdf(d1)
        else:
            delta = norm.cdf(d1) - 1.0

        gamma = norm.pdf(d1) / (spot * sigma * math.sqrt(t))

        common_theta = -(spot * norm.pdf(d1) * sigma) / (2.0 * math.sqrt(t))
        if option_type_lower == "call":
            theta = common_theta - r * strike * math.exp(-r * t) * norm.cdf(d2)
        else:
            theta = common_theta + r * strike * math.exp(-r * t) * norm.cdf(-d2)
        theta = theta / 365.0

        vega = spot * norm.pdf(d1) * math.sqrt(t) / 100.0

        if option_type_lower == "call":
            rho = strike * t * math.exp(-r * t) * norm.cdf(d2) / 100.0
        else:
            rho = -strike * t * math.exp(-r * t) * norm.cdf(-d2) / 100.0

        return GreeksResult(
            delta=delta,
            gamma=gamma,
            theta=theta,
            vega=vega,
            rho=rho,
        )

    def enrich_option_chain(
        self, chain: pd.DataFrame, spot_prices: dict[str, float]
    ) -> pd.DataFrame:
        """Option Chain um Greeks-Spalten erweitern."""
        result = chain.copy()

        for col in ["delta", "gamma", "theta", "vega", "rho"]:
            result[col] = np.nan

        for idx, row in result.iterrows():
            underlying = row.get("underlying")
            strike = row.get("strike")
            dte = row.get("dte")
            iv = row.get("iv")
            option_type = row.get("option_type")

            spot = spot_prices.get(underlying) if underlying else None

            if not self._is_valid_row(spot, strike, dte, iv, option_type):
                logger.warning(
                    "Unvollständige Daten für Kontrakt bei Index %s - übersprungen",
                    idx,
                )
                continue

            try:
                greeks = self.calculate_greeks(
                    spot=float(spot),
                    strike=float(strike),
                    dte=int(dte),
                    iv=float(iv),
                    option_type=str(option_type),
                )
                result.at[idx, "delta"] = greeks.delta
                result.at[idx, "gamma"] = greeks.gamma
                result.at[idx, "theta"] = greeks.theta
                result.at[idx, "vega"] = greeks.vega
                result.at[idx, "rho"] = greeks.rho
            except (ValueError, ZeroDivisionError, OverflowError) as e:
                logger.warning(
                    "Fehler bei Greeks-Berechnung für Kontrakt bei Index %s: %s",
                    idx,
                    e,
                )
                continue

        return result

    @staticmethod
    def _d1(spot: float, strike: float, t: float, r: float, sigma: float) -> float:
        """d1-Parameter der Black-Scholes-Formel."""
        return (math.log(spot / strike) + (r + sigma**2 / 2.0) * t) / (
            sigma * math.sqrt(t)
        )

    @staticmethod
    def _d2(d1: float, sigma: float, t: float) -> float:
        """d2-Parameter der Black-Scholes-Formel."""
        return d1 - sigma * math.sqrt(t)

    @staticmethod
    def _is_valid_row(
        spot: object,
        strike: object,
        dte: object,
        iv: object,
        option_type: object,
    ) -> bool:
        """Prüft ob eine Zeile vollständige und gültige Daten enthält."""
        if any(v is None for v in [spot, strike, dte, iv, option_type]):
            return False

        try:
            if math.isnan(float(spot)) or math.isnan(float(strike)):
                return False
            if math.isnan(float(dte)) or math.isnan(float(iv)):
                return False
        except (TypeError, ValueError):
            return False

        try:
            if float(spot) <= 0 or float(strike) <= 0:
                return False
            if float(dte) <= 0 or float(iv) <= 0:
                return False
        except (TypeError, ValueError):
            return False

        if not isinstance(option_type, str):
            return False
        if option_type.lower() not in ("call", "put"):
            return False

        return True
