"""Datenmodell für Portfolio-Positionen.

Repräsentiert eine einzelne Position im Portfolio des Traders,
inklusive P&L-Berechnung und Status-Tracking.
"""

from dataclasses import dataclass
from datetime import date


@dataclass
class PortfolioPosition:
    """Eine einzelne Position im Portfolio."""

    underlying: str
    strategy_type: str
    entry_date: date
    strike: float
    expiration: date
    premium_received: float
    current_value: float
    pnl: float
    pnl_pct: float
    status: str  # "open", "closed", "rolled"
