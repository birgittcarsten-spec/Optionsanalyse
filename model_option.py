"""Datenmodell für Optionskontrakte.

Repräsentiert einen einzelnen Optionskontrakt aus einer Option Chain
mit allen relevanten Marktdaten und berechneten Greeks.
"""

from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class OptionContract:
    """Ein einzelner Optionskontrakt aus der Option Chain."""

    underlying: str
    strike: float
    expiration: date
    option_type: str  # "call" oder "put"
    bid: float
    ask: float
    last: float
    volume: int
    open_interest: int
    dte: int
    iv: Optional[float] = None
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None
    rho: Optional[float] = None
