"""Datenmodell für Handelsvorschläge.

Repräsentiert einen konkreten Handelsvorschlag, der von der Strategy Engine
generiert und optional von der AI Ranking Engine bewertet wurde.
"""

from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class TradeSuggestion:
    """Ein konkreter Handelsvorschlag mit allen relevanten Kennzahlen."""

    underlying: str
    strike: float
    expiration: date
    option_type: str  # "call" oder "put"
    strategy_type: str
    premium_bid: float
    delta: float
    iv_rank: float
    dte: int
    probability_of_profit: float
    expected_value: float
    combined_score: float
    ai_score: Optional[float] = None
    ai_reasoning: Optional[str] = None
