"""KI-gestützte Bewertung und Priorisierung von Handelsvorschlägen.

Verwendet ein XGBoost-Modell (falls vorhanden) oder ein regelbasiertes
Fallback-Scoring, um Trade Suggestions zu bewerten und zu priorisieren.
"""

import logging
import os
from dataclasses import dataclass

import numpy as np

from model_trade import TradeSuggestion

logger = logging.getLogger(__name__)


@dataclass
class RankedSuggestion:
    """Bewerteter Handelsvorschlag mit AI-Score."""

    suggestion: TradeSuggestion
    ai_score: float
    reasoning: str


MARKET_REGIME_MAP: dict[str, float] = {
    "bullish": 1.0,
    "neutral": 0.5,
    "bearish": 0.0,
    "high_volatility": 0.75,
}

FEATURE_NAMES: list[str] = [
    "iv_rank",
    "delta",
    "dte",
    "probability_of_profit",
    "expected_value",
    "historical_volatility",
    "sector_performance",
    "market_regime",
]

RULE_BASED_WEIGHTS: dict[str, float] = {
    "iv_rank": 0.25,
    "delta_proximity": 0.20,
    "dte": 0.15,
    "probability_of_profit": 0.25,
    "expected_value": 0.15,
}


class AIRankingEngine:
    """KI-gestütztes Ranking von Trade Suggestions."""

    def __init__(self, model_path: str):
        self.model_path = model_path
        self.model = self._load_model(model_path)
        self._use_model = self.model is not None

    def rank_suggestions(
        self, suggestions: list[TradeSuggestion], market_context: dict
    ) -> list[RankedSuggestion]:
        """Trade Suggestions bewerten und sortieren."""
        if not suggestions:
            return []

        ranked: list[RankedSuggestion] = []

        for suggestion in suggestions:
            features = self._extract_features(suggestion, market_context)

            if self._use_model:
                raw_score = float(self.model.predict(features.reshape(1, -1))[0])
                ai_score = float(np.clip(raw_score, 0.0, 100.0))
                importances = dict(
                    zip(FEATURE_NAMES, self.model.feature_importances_)
                )
            else:
                ai_score = self._rule_based_score(suggestion, features)
                importances = {
                    "iv_rank": RULE_BASED_WEIGHTS["iv_rank"],
                    "delta": RULE_BASED_WEIGHTS["delta_proximity"],
                    "dte": RULE_BASED_WEIGHTS["dte"],
                    "probability_of_profit": RULE_BASED_WEIGHTS["probability_of_profit"],
                    "expected_value": RULE_BASED_WEIGHTS["expected_value"],
                    "historical_volatility": 0.0,
                    "sector_performance": 0.0,
                    "market_regime": 0.0,
                }

            reasoning = self._generate_reasoning(suggestion, ai_score, importances)

            ranked.append(
                RankedSuggestion(
                    suggestion=suggestion,
                    ai_score=ai_score,
                    reasoning=reasoning,
                )
            )

        ranked.sort(key=lambda r: r.ai_score, reverse=True)
        return ranked

    def _extract_features(
        self, suggestion: TradeSuggestion, market_context: dict
    ) -> np.ndarray:
        """Feature-Vektor für das ML-Modell extrahieren."""
        hv_data = market_context.get("historical_volatility", {})
        hv = hv_data.get(suggestion.underlying, 0.0)

        sector_perf = market_context.get("sector_performance", {})
        if sector_perf:
            avg_sector_perf = sum(sector_perf.values()) / len(sector_perf)
        else:
            avg_sector_perf = 0.0

        regime_str = market_context.get("market_regime", "neutral")
        regime_value = MARKET_REGIME_MAP.get(regime_str, 0.5)

        features = np.array(
            [
                suggestion.iv_rank,
                abs(suggestion.delta),
                float(suggestion.dte),
                suggestion.probability_of_profit,
                suggestion.expected_value,
                hv,
                avg_sector_perf,
                regime_value,
            ],
            dtype=np.float64,
        )

        return features

    def _generate_reasoning(
        self, suggestion: TradeSuggestion, score: float, feature_importances: dict
    ) -> str:
        """Textuelle Begründung für das Ranking generieren."""
        sorted_features = sorted(
            feature_importances.items(), key=lambda x: x[1], reverse=True
        )
        top_features = sorted_features[:3]

        if score >= 80:
            score_label = "sehr hoch"
            score_intro = "Hervorragender Trade"
        elif score >= 60:
            score_label = "hoch"
            score_intro = "Guter Trade"
        elif score >= 40:
            score_label = "mittel"
            score_intro = "Durchschnittlicher Trade"
        elif score >= 20:
            score_label = "niedrig"
            score_intro = "Unterdurchschnittlicher Trade"
        else:
            score_label = "sehr niedrig"
            score_intro = "Schwacher Trade"

        reasons: list[str] = []

        for feature_name, importance in top_features:
            if importance <= 0:
                continue
            reason = self._feature_reason(feature_name, suggestion)
            if reason:
                reasons.append(reason)

        reasoning_parts = f"{score_intro} (Score: {score:.0f}/100, Bewertung: {score_label})."

        if reasons:
            reasoning_parts += " " + " ".join(reasons)

        return reasoning_parts

    def _feature_reason(self, feature_name: str, suggestion: TradeSuggestion) -> str:
        """Einzelne Feature-Begründung generieren."""
        if feature_name == "iv_rank":
            if suggestion.iv_rank >= 50:
                return f"IV Rank von {suggestion.iv_rank:.0f} ist erhöht – gute Prämienumgebung."
            else:
                return f"IV Rank von {suggestion.iv_rank:.0f} ist moderat."
        elif feature_name == "delta":
            delta_abs = abs(suggestion.delta)
            if 0.15 <= delta_abs <= 0.30:
                return f"Delta von {suggestion.delta:.2f} liegt im idealen Bereich für Stillhalter."
            elif delta_abs < 0.15:
                return f"Delta von {suggestion.delta:.2f} ist konservativ."
            else:
                return f"Delta von {suggestion.delta:.2f} ist aggressiv."
        elif feature_name == "dte":
            if 20 <= suggestion.dte <= 45:
                return f"DTE von {suggestion.dte} Tagen ist optimal für Theta-Zerfall."
            elif suggestion.dte < 20:
                return f"DTE von {suggestion.dte} Tagen ist kurz."
            else:
                return f"DTE von {suggestion.dte} Tagen ist lang."
        elif feature_name == "probability_of_profit":
            pop_pct = suggestion.probability_of_profit * 100
            if pop_pct >= 70:
                return f"Gewinnwahrscheinlichkeit von {pop_pct:.0f}% ist hoch."
            elif pop_pct >= 50:
                return f"Gewinnwahrscheinlichkeit von {pop_pct:.0f}% ist akzeptabel."
            else:
                return f"Gewinnwahrscheinlichkeit von {pop_pct:.0f}% ist niedrig."
        elif feature_name == "expected_value":
            if suggestion.expected_value > 0:
                return f"Positiver Erwartungswert von ${suggestion.expected_value:.2f}."
            else:
                return f"Negativer Erwartungswert von ${suggestion.expected_value:.2f}."
        elif feature_name == "historical_volatility":
            return "Historische Volatilität berücksichtigt."
        elif feature_name == "sector_performance":
            return "Sektor-Performance fließt in die Bewertung ein."
        elif feature_name == "market_regime":
            return "Aktuelles Marktregime berücksichtigt."
        return ""

    def _rule_based_score(
        self, suggestion: TradeSuggestion, features: np.ndarray
    ) -> float:
        """Regelbasiertes Fallback-Scoring."""
        score = 0.0

        iv_rank_score = suggestion.iv_rank
        score += RULE_BASED_WEIGHTS["iv_rank"] * iv_rank_score

        ideal_delta = 0.20
        delta_abs = abs(suggestion.delta)
        delta_distance = abs(delta_abs - ideal_delta)
        delta_score = max(0.0, (1.0 - delta_distance / 0.30) * 100.0)
        score += RULE_BASED_WEIGHTS["delta_proximity"] * delta_score

        ideal_dte = 32.5
        dte_distance = abs(suggestion.dte - ideal_dte)
        dte_score = max(0.0, (1.0 - dte_distance / 30.0) * 100.0)
        score += RULE_BASED_WEIGHTS["dte"] * dte_score

        pop_score = suggestion.probability_of_profit * 100.0
        score += RULE_BASED_WEIGHTS["probability_of_profit"] * pop_score

        ev_normalized = (suggestion.expected_value + 500.0) / 1000.0
        ev_score = float(np.clip(ev_normalized * 100.0, 0.0, 100.0))
        score += RULE_BASED_WEIGHTS["expected_value"] * ev_score

        return float(np.clip(score, 0.0, 100.0))

    def _load_model(self, model_path: str):
        """Trainiertes XGBoost-Modell laden."""
        if not os.path.exists(model_path):
            logger.info(
                "Kein trainiertes Modell gefunden unter '%s'. "
                "Verwende regelbasiertes Scoring als Fallback.",
                model_path,
            )
            return None

        try:
            from xgboost import XGBRegressor

            model = XGBRegressor()
            model.load_model(model_path)
            logger.info("XGBoost-Modell erfolgreich geladen von '%s'.", model_path)
            return model
        except Exception as e:
            logger.warning(
                "Fehler beim Laden des Modells von '%s': %s. "
                "Verwende regelbasiertes Scoring als Fallback.",
                model_path,
                str(e),
            )
            return None
