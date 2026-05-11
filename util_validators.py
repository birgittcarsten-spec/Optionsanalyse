"""Eingabevalidierung für Optionsparameter.

Validiert Parameter wie Spot-Preis, Strike, DTE und implizite Volatilität,
die für die Berechnung von Greeks und Wahrscheinlichkeiten benötigt werden.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ValidationResult:
    """Ergebnis einer Validierung.

    Attributes:
        is_valid: True wenn alle Validierungen bestanden wurden.
        errors: Liste der Fehlermeldungen bei ungültigen Eingaben.
    """

    is_valid: bool
    errors: list[str]


def validate_spot(spot: float) -> Optional[str]:
    """Spot-Preis validieren."""
    if spot is None:
        return "spot darf nicht None sein"
    if not isinstance(spot, (int, float)):
        return f"spot muss eine Zahl sein, erhalten: {type(spot).__name__}"
    if spot <= 0:
        return f"spot muss größer als 0 sein, erhalten: {spot}"
    return None


def validate_strike(strike: float) -> Optional[str]:
    """Strike-Preis validieren."""
    if strike is None:
        return "strike darf nicht None sein"
    if not isinstance(strike, (int, float)):
        return f"strike muss eine Zahl sein, erhalten: {type(strike).__name__}"
    if strike <= 0:
        return f"strike muss größer als 0 sein, erhalten: {strike}"
    return None


def validate_dte(dte: int) -> Optional[str]:
    """Days to Expiration validieren."""
    if dte is None:
        return "dte darf nicht None sein"
    if not isinstance(dte, (int, float)):
        return f"dte muss eine Zahl sein, erhalten: {type(dte).__name__}"
    if dte <= 0:
        return f"dte muss größer als 0 sein, erhalten: {dte}"
    return None


def validate_iv(iv: float) -> Optional[str]:
    """Implizite Volatilität validieren."""
    if iv is None:
        return "iv darf nicht None sein"
    if not isinstance(iv, (int, float)):
        return f"iv muss eine Zahl sein, erhalten: {type(iv).__name__}"
    if iv <= 0:
        return f"iv muss größer als 0 sein, erhalten: {iv}"
    return None


def validate_option_type(option_type: str) -> Optional[str]:
    """Optionstyp validieren."""
    if option_type is None:
        return "option_type darf nicht None sein"
    if not isinstance(option_type, str):
        return f"option_type muss ein String sein, erhalten: {type(option_type).__name__}"
    if option_type.lower() not in ("call", "put"):
        return f"option_type muss 'call' oder 'put' sein, erhalten: '{option_type}'"
    return None


def validate_option_params(
    spot: float,
    strike: float,
    dte: int,
    iv: float,
    option_type: Optional[str] = None,
) -> ValidationResult:
    """Alle Optionsparameter gemeinsam validieren."""
    errors: list[str] = []

    spot_error = validate_spot(spot)
    if spot_error:
        errors.append(spot_error)

    strike_error = validate_strike(strike)
    if strike_error:
        errors.append(strike_error)

    dte_error = validate_dte(dte)
    if dte_error:
        errors.append(dte_error)

    iv_error = validate_iv(iv)
    if iv_error:
        errors.append(iv_error)

    if option_type is not None:
        type_error = validate_option_type(option_type)
        if type_error:
            errors.append(type_error)

    return ValidationResult(is_valid=len(errors) == 0, errors=errors)
