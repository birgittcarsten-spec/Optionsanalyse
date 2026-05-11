"""Datenmodelle für die Plattform-Konfiguration.

Enthält typisierte Konfigurationsklassen mit Validierung,
die aus YAML-Dateien geladen werden können.
"""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


@dataclass
class StrategyConfig:
    """Konfiguration für eine einzelne Strategie."""

    min_iv_rank: float
    max_iv_rank: float = 100.0
    min_delta: float = 0.10
    max_delta: float = 0.30
    min_dte: int = 20
    max_dte: int = 45
    exclude_earnings_days: Optional[int] = None

    def validate(self) -> list[str]:
        """Konfiguration validieren."""
        errors: list[str] = []

        if self.min_iv_rank < 0:
            errors.append(f"min_iv_rank muss >= 0 sein, erhalten: {self.min_iv_rank}")
        if self.max_iv_rank < self.min_iv_rank:
            errors.append(
                f"max_iv_rank ({self.max_iv_rank}) muss >= min_iv_rank ({self.min_iv_rank}) sein"
            )
        if self.min_delta < 0:
            errors.append(f"min_delta muss >= 0 sein, erhalten: {self.min_delta}")
        if self.max_delta < self.min_delta:
            errors.append(
                f"max_delta ({self.max_delta}) muss >= min_delta ({self.min_delta}) sein"
            )
        if self.min_dte < 0:
            errors.append(f"min_dte muss >= 0 sein, erhalten: {self.min_dte}")
        if self.max_dte < self.min_dte:
            errors.append(
                f"max_dte ({self.max_dte}) muss >= min_dte ({self.min_dte}) sein"
            )
        if self.exclude_earnings_days is not None and self.exclude_earnings_days < 0:
            errors.append(
                f"exclude_earnings_days muss >= 0 sein, erhalten: {self.exclude_earnings_days}"
            )

        return errors


@dataclass
class PlatformConfig:
    """Gesamtkonfiguration der ThetaFlow AI Plattform."""

    underlyings: list[str]
    strategies: dict[str, StrategyConfig]
    risk_thresholds: dict[str, float]
    data_sources: dict[str, dict]
    data_path: Path = Path("data/")
    model_path: Path = Path("data/models/")
    version: str = "1.0.0"

    def validate(self) -> list[str]:
        """Gesamtkonfiguration validieren."""
        errors: list[str] = []

        if not self.underlyings:
            errors.append("underlyings darf nicht leer sein")

        for name, strategy in self.strategies.items():
            strategy_errors = strategy.validate()
            for error in strategy_errors:
                errors.append(f"Strategie '{name}': {error}")

        if "margin_threshold" in self.risk_thresholds:
            margin = self.risk_thresholds["margin_threshold"]
            if not (0.0 <= margin <= 1.0):
                errors.append(
                    f"margin_threshold muss zwischen 0.0 und 1.0 liegen, erhalten: {margin}"
                )

        if "var_threshold" in self.risk_thresholds:
            var = self.risk_thresholds["var_threshold"]
            if not (0.0 <= var <= 1.0):
                errors.append(
                    f"var_threshold muss zwischen 0.0 und 1.0 liegen, erhalten: {var}"
                )

        return errors

    @classmethod
    def from_dict(cls, data: dict) -> "PlatformConfig":
        """PlatformConfig aus einem Dictionary erstellen."""
        strategies = {}
        for name, strategy_data in data.get("strategies", {}).items():
            strategies[name] = StrategyConfig(
                min_iv_rank=strategy_data.get("min_iv_rank", 25),
                max_iv_rank=strategy_data.get("max_iv_rank", 100.0),
                min_delta=strategy_data.get("min_delta", 0.10),
                max_delta=strategy_data.get("max_delta", 0.30),
                min_dte=strategy_data.get("min_dte", 20),
                max_dte=strategy_data.get("max_dte", 45),
                exclude_earnings_days=strategy_data.get("exclude_earnings_days"),
            )

        risk_data = data.get("risk", {})
        risk_thresholds = {
            "margin_threshold": risk_data.get("margin_threshold", 0.80),
            "var_threshold": risk_data.get("var_threshold", 0.05),
            "max_position_size_pct": risk_data.get("max_position_size_pct", 0.10),
        }

        platform_data = data.get("platform", {})

        return cls(
            underlyings=data.get("underlyings", []),
            strategies=strategies,
            risk_thresholds=risk_thresholds,
            data_sources=data.get("data_sources", {}),
            data_path=Path(platform_data.get("data_path", "data/")),
            model_path=Path(platform_data.get("model_path", "data/models/")),
            version=platform_data.get("version", "1.0.0"),
        )

    @classmethod
    def load(
        cls,
        config_path: Path = Path("default_config.yaml"),
        env_path: Optional[Path] = None,
    ) -> "PlatformConfig":
        """Konfiguration aus YAML laden mit Validierung und Fallback."""
        # Load environment variables via python-dotenv
        if env_path is not None:
            load_dotenv(dotenv_path=env_path)
        else:
            # Try to find .env in the current directory
            default_env = Path(".env")
            if default_env.exists():
                load_dotenv(dotenv_path=default_env)
            else:
                load_dotenv()  # Search in default locations

        # Load YAML configuration
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except FileNotFoundError:
            logger.warning(
                "Konfigurationsdatei '%s' nicht gefunden. "
                "Verwende Standardkonfiguration.",
                config_path,
            )
            data = {}
        except yaml.YAMLError as e:
            logger.warning(
                "Fehler beim Parsen der Konfigurationsdatei '%s': %s. "
                "Verwende Standardkonfiguration.",
                config_path,
                e,
            )
            data = {}

        # Override data_sources connection params from environment variables
        data = cls._apply_env_overrides(data)

        # Create config from dict
        config = cls.from_dict(data)

        # Validate and apply fallback for invalid values
        errors = config.validate()
        if errors:
            for error in errors:
                logger.warning("Konfigurationsfehler: %s", error)
            config = cls._apply_fallback(config, data)

        return config

    @classmethod
    def _apply_env_overrides(cls, data: dict) -> dict:
        """Umgebungsvariablen in die Konfiguration integrieren."""
        data_sources = data.get("data_sources", {})

        ib_config = data_sources.get("interactive_brokers", {})
        if os.environ.get("IB_HOST"):
            ib_config["host"] = os.environ["IB_HOST"]
        if os.environ.get("IB_PORT"):
            try:
                ib_config["port"] = int(os.environ["IB_PORT"])
            except ValueError:
                logger.warning(
                    "Ungültiger IB_PORT Wert: '%s'. Verwende Standardwert.",
                    os.environ["IB_PORT"],
                )
        if os.environ.get("IB_CLIENT_ID"):
            try:
                ib_config["client_id"] = int(os.environ["IB_CLIENT_ID"])
            except ValueError:
                logger.warning(
                    "Ungültiger IB_CLIENT_ID Wert: '%s'. Verwende Standardwert.",
                    os.environ["IB_CLIENT_ID"],
                )
        if ib_config:
            data_sources["interactive_brokers"] = ib_config

        finnhub_config = data_sources.get("finnhub", {})
        if os.environ.get("FINNHUB_API_KEY"):
            finnhub_config["api_key"] = os.environ["FINNHUB_API_KEY"]
        if finnhub_config:
            data_sources["finnhub"] = finnhub_config

        polygon_config = data_sources.get("polygon", {})
        if os.environ.get("POLYGON_API_KEY"):
            polygon_config["api_key"] = os.environ["POLYGON_API_KEY"]
        if polygon_config:
            data_sources["polygon"] = polygon_config

        if data_sources:
            data["data_sources"] = data_sources

        return data

    @classmethod
    def _apply_fallback(cls, config: "PlatformConfig", original_data: dict) -> "PlatformConfig":
        """Fallback auf Standardwerte für ungültige Konfigurationsfelder."""
        underlyings = config.underlyings if config.underlyings else ["SPY"]

        strategies = {}
        for name, strategy in config.strategies.items():
            strategy_errors = strategy.validate()
            if strategy_errors:
                logger.warning(
                    "Strategie '%s' hat ungültige Werte. Verwende Standardwerte.",
                    name,
                )
                strategies[name] = StrategyConfig(min_iv_rank=25)
            else:
                strategies[name] = strategy

        risk_thresholds = dict(config.risk_thresholds)
        if "margin_threshold" in risk_thresholds:
            margin = risk_thresholds["margin_threshold"]
            if not (0.0 <= margin <= 1.0):
                risk_thresholds["margin_threshold"] = 0.80

        if "var_threshold" in risk_thresholds:
            var = risk_thresholds["var_threshold"]
            if not (0.0 <= var <= 1.0):
                risk_thresholds["var_threshold"] = 0.05

        return cls(
            underlyings=underlyings,
            strategies=strategies,
            risk_thresholds=risk_thresholds,
            data_sources=config.data_sources,
            data_path=config.data_path,
            model_path=config.model_path,
        )
