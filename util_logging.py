"""Logging-Konfiguration für ThetaFlow AI Platform.

Modulspezifische Log-Levels für kontrollierte Ausgabe.
"""

import logging
import sys
from typing import Optional

# Modulspezifische Log-Levels
LOGGING_CONFIG: dict[str, int] = {
    "market_data_loader": logging.INFO,
    "greeks_engine": logging.WARNING,
    "volatility_engine": logging.WARNING,
    "probability_engine": logging.WARNING,
    "strategy_engine": logging.INFO,
    "ai_ranking_engine": logging.INFO,
    "risk_analyzer": logging.WARNING,
    "backtesting_engine": logging.INFO,
}

# Standard-Format für Log-Nachrichten
DEFAULT_FORMAT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(
    level: int = logging.INFO,
    format_string: Optional[str] = None,
    date_format: Optional[str] = None,
) -> None:
    """Root-Logger konfigurieren und modulspezifische Levels setzen."""
    fmt = format_string or DEFAULT_FORMAT
    datefmt = date_format or DEFAULT_DATE_FORMAT

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    for module_name, module_level in LOGGING_CONFIG.items():
        logging.getLogger(module_name).setLevel(module_level)


def get_logger(module_name: str) -> logging.Logger:
    """Logger für ein spezifisches Modul erstellen."""
    logger = logging.getLogger(module_name)

    if module_name in LOGGING_CONFIG:
        logger.setLevel(LOGGING_CONFIG[module_name])

    return logger
