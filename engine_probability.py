"""Probability Engine - Statistische Wahrscheinlichkeitsberechnung für Optionsstrategien.

Berechnet Probability of Profit, Expected Value und Probability OTM
basierend auf log-normaler Verteilung des Underlyings.
"""

import logging
import math
from dataclasses import dataclass

from scipy.stats import norm

from util_validators import validate_option_params

logger = logging.getLogger("probability_engine")


@dataclass
class ProbabilityResult:
    """Ergebnis der Wahrscheinlichkeitsberechnung."""

    probability_of_profit: float
    expected_value: float
    probability_otm: float


class ProbabilityEngine:
    """Statistische Wahrscheinlichkeitsberechnung für Stillhalter-Strategien."""

    def __init__(self, risk_free_rate: float = 0.05):
        self.risk_free_rate = risk_free_rate

    def calculate_probability_of_profit(
        self,
        spot: float,
        strike: float,
        dte: int,
        iv: float,
        option_type: str,
        premium: float,
    ) -> float:
        """Wahrscheinlichkeit berechnen, dass der Trade profitabel ist."""
        if not self._validate_inputs(spot, strike, dte, iv, option_type, premium):
            return float("nan")

        t = dte / 365.0
        sigma = iv
        r = self.risk_free_rate
        option_type_lower = option_type.lower()

        if option_type_lower == "put":
            breakeven = strike - premium
            if breakeven <= 0:
                return 1.0
            d2 = self._calculate_d2(spot, breakeven, t, r, sigma)
            probability = norm.cdf(d2)
        else:
            breakeven = strike + premium
            d2 = self._calculate_d2(spot, breakeven, t, r, sigma)
            probability = norm.cdf(-d2)

        return round(probability, 2)

    def calculate_expected_value(
        self,
        probability_of_profit: float,
        premium: float,
        max_loss: float,
    ) -> float:
        """Expected Value berechnen."""
        if not self._validate_ev_inputs(probability_of_profit, premium, max_loss):
            return float("nan")

        ev = probability_of_profit * premium - (1.0 - probability_of_profit) * max_loss
        return round(ev, 2)

    def calculate_probability_otm(
        self,
        spot: float,
        strike: float,
        dte: int,
        iv: float,
        option_type: str,
    ) -> float:
        """Wahrscheinlichkeit berechnen, dass die Option OTM verfällt."""
        if not self._validate_inputs_basic(spot, strike, dte, iv, option_type):
            return float("nan")

        t = dte / 365.0
        sigma = iv
        r = self.risk_free_rate
        option_type_lower = option_type.lower()

        d2 = self._calculate_d2(spot, strike, t, r, sigma)

        if option_type_lower == "put":
            probability = norm.cdf(d2)
        else:
            probability = norm.cdf(-d2)

        return round(probability, 2)

    def _calculate_d2(
        self, spot: float, strike: float, t: float, r: float, sigma: float
    ) -> float:
        """d2-Parameter für die log-normale Verteilung berechnen."""
        return (math.log(spot / strike) + (r - sigma**2 / 2.0) * t) / (
            sigma * math.sqrt(t)
        )

    def _validate_inputs(
        self, spot, strike, dte, iv, option_type, premium
    ) -> bool:
        """Eingabeparameter für Probability of Profit validieren."""
        if not self._validate_inputs_basic(spot, strike, dte, iv, option_type):
            return False

        if premium is None:
            logger.warning("premium darf nicht None sein")
            return False
        if not isinstance(premium, (int, float)):
            logger.warning("premium muss eine Zahl sein, erhalten: %s", type(premium).__name__)
            return False
        if math.isnan(premium) or math.isinf(premium):
            logger.warning("premium darf nicht NaN oder Inf sein")
            return False
        if premium < 0:
            logger.warning("premium muss >= 0 sein, erhalten: %s", premium)
            return False

        return True

    def _validate_inputs_basic(self, spot, strike, dte, iv, option_type) -> bool:
        """Basis-Eingabeparameter validieren."""
        validation = validate_option_params(spot, strike, dte, iv, option_type)
        if not validation.is_valid:
            logger.warning(
                "Ungültige Optionsparameter: %s", "; ".join(validation.errors)
            )
            return False
        return True

    def _validate_ev_inputs(self, probability_of_profit, premium, max_loss) -> bool:
        """Eingabeparameter für Expected Value validieren."""
        if probability_of_profit is None:
            logger.warning("probability_of_profit darf nicht None sein")
            return False
        if not isinstance(probability_of_profit, (int, float)):
            logger.warning("probability_of_profit muss eine Zahl sein")
            return False
        if math.isnan(probability_of_profit) or math.isinf(probability_of_profit):
            logger.warning("probability_of_profit darf nicht NaN oder Inf sein")
            return False
        if probability_of_profit < 0.0 or probability_of_profit > 1.0:
            logger.warning("probability_of_profit muss zwischen 0.0 und 1.0 liegen")
            return False

        if premium is None:
            logger.warning("premium darf nicht None sein")
            return False
        if not isinstance(premium, (int, float)):
            logger.warning("premium muss eine Zahl sein")
            return False
        if math.isnan(premium) or math.isinf(premium):
            logger.warning("premium darf nicht NaN oder Inf sein")
            return False
        if premium < 0:
            logger.warning("premium muss >= 0 sein")
            return False

        if max_loss is None:
            logger.warning("max_loss darf nicht None sein")
            return False
        if not isinstance(max_loss, (int, float)):
            logger.warning("max_loss muss eine Zahl sein")
            return False
        if math.isnan(max_loss) or math.isinf(max_loss):
            logger.warning("max_loss darf nicht NaN oder Inf sein")
            return False
        if max_loss < 0:
            logger.warning("max_loss muss >= 0 sein")
            return False

        return True
