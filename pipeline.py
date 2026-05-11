"""ThetaFlow AI Platform - Data Pipeline Integration Layer.

Orchestriert den vollständigen Datenfluss:
MarketDataLoader → GreeksEngine → VolatilityEngine → ProbabilityEngine →
StrategyEngine → AIRankingEngine → RiskAnalyzer
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

from bt_simulator import BacktestConfig, BacktestingEngine, BacktestResult
from engine_ai_ranking import AIRankingEngine, RankedSuggestion
from engine_greeks import GreeksEngine
from engine_market_data import DataSourceError, MarketDataLoader
from engine_probability import ProbabilityEngine
from engine_risk import RiskAnalyzer, RiskMetrics
from engine_strategy import StrategyEngine
from engine_volatility import VolatilityEngine
from model_config import PlatformConfig
from model_trade import TradeSuggestion
from util_serialization import DataEnvelope, SerializationService

logger = logging.getLogger("pipeline")

MARKET_DATA_TTL_SECONDS = 300
COMPUTED_DATA_TTL_SECONDS = 900


@st.cache_resource
def _get_platform_config() -> PlatformConfig:
    """Load platform configuration (singleton, cached as resource)."""
    return PlatformConfig.load()


@st.cache_resource
def _get_serialization_service() -> SerializationService:
    """Create SerializationService instance (singleton)."""
    config = _get_platform_config()
    base_path = Path(config.data_path) / "processed"
    return SerializationService(base_path=base_path, version=config.version)


@st.cache_resource
def _get_greeks_engine() -> GreeksEngine:
    """Create GreeksEngine instance (singleton)."""
    config = _get_platform_config()
    risk_free_rate = config.risk_thresholds.get("risk_free_rate", 0.05)
    return GreeksEngine(risk_free_rate=risk_free_rate)


@st.cache_resource
def _get_volatility_engine() -> VolatilityEngine:
    """Create VolatilityEngine instance (singleton)."""
    return VolatilityEngine()


@st.cache_resource
def _get_probability_engine() -> ProbabilityEngine:
    """Create ProbabilityEngine instance (singleton)."""
    return ProbabilityEngine()


@st.cache_resource
def _get_strategy_engine() -> StrategyEngine:
    """Create StrategyEngine instance (singleton)."""
    config = _get_platform_config()
    strategies_config = {}
    for name, strat_config in config.strategies.items():
        strategies_config[name] = {
            "min_iv_rank": strat_config.min_iv_rank,
            "max_iv_rank": strat_config.max_iv_rank,
            "min_delta": strat_config.min_delta,
            "max_delta": strat_config.max_delta,
            "min_dte": strat_config.min_dte,
            "max_dte": strat_config.max_dte,
        }
        if strat_config.exclude_earnings_days is not None:
            strategies_config[name]["exclude_earnings_days"] = strat_config.exclude_earnings_days
    return StrategyEngine(config={"strategies": strategies_config})


@st.cache_resource
def _get_ai_ranking_engine() -> AIRankingEngine:
    """Create AIRankingEngine instance (singleton)."""
    config = _get_platform_config()
    model_path = str(Path(config.model_path) / "xgboost_ranking.json")
    return AIRankingEngine(model_path=model_path)


@st.cache_resource
def _get_risk_analyzer() -> RiskAnalyzer:
    """Create RiskAnalyzer instance (singleton)."""
    config = _get_platform_config()
    return RiskAnalyzer(config=config.risk_thresholds)


class DataPipeline:
    """Orchestrates the full ThetaFlow data pipeline."""

    def __init__(self):
        self.config = _get_platform_config()
        self.serialization = _get_serialization_service()
        self.greeks_engine = _get_greeks_engine()
        self.volatility_engine = _get_volatility_engine()
        self.probability_engine = _get_probability_engine()
        self.strategy_engine = _get_strategy_engine()
        self.ai_ranking_engine = _get_ai_ranking_engine()
        self.risk_analyzer = _get_risk_analyzer()

    def initialize(self) -> None:
        """Initialize pipeline and load cached data on startup."""
        if "pipeline_initialized" not in st.session_state:
            st.session_state.pipeline_initialized = True
            st.session_state.option_chains = {}
            st.session_state.enriched_chains = {}
            st.session_state.volatility_data = {}
            st.session_state.spot_prices = {}
            st.session_state.trade_suggestions = []
            st.session_state.ranked_suggestions = []
            st.session_state.risk_metrics = None
            st.session_state.backtest_results = {}
            st.session_state.last_data_load = None
            st.session_state.pipeline_errors = []
            self._load_cached_data()

    def load_market_data(
        self, underlyings: list[str], loader: Optional[MarketDataLoader] = None
    ) -> dict[str, pd.DataFrame]:
        """Load market data for given underlyings."""
        option_chains: dict[str, pd.DataFrame] = {}
        spot_prices: dict[str, float] = {}
        errors: list[str] = []

        for symbol in underlyings:
            try:
                if loader is not None:
                    chain = loader.load_option_chain(symbol)
                    option_chains[symbol] = chain
                    try:
                        stock_data = loader.load_stock_data([symbol])
                        if not stock_data.empty and "price" in stock_data.columns:
                            spot_prices[symbol] = float(
                                stock_data.loc[stock_data["symbol"] == symbol, "price"].iloc[0]
                            )
                    except (DataSourceError, Exception) as e:
                        logger.warning("Spot-Preis für %s nicht verfügbar: %s", symbol, e)
                else:
                    cached = st.session_state.get("option_chains", {}).get(symbol)
                    if cached is not None:
                        option_chains[symbol] = cached
            except DataSourceError as e:
                errors.append(f"{symbol}: {e}")
                fallback = self._load_persisted_chain(symbol)
                if fallback is not None:
                    option_chains[symbol] = fallback
            except Exception as e:
                errors.append(f"{symbol}: {e}")

        st.session_state.option_chains = option_chains
        st.session_state.spot_prices.update(spot_prices)
        st.session_state.last_data_load = datetime.now(timezone.utc)
        st.session_state.pipeline_errors = errors
        self._persist_option_chains(option_chains)
        return option_chains

    def compute_greeks(
        self, chain: pd.DataFrame, spot_prices: Optional[dict[str, float]] = None
    ) -> pd.DataFrame:
        """Enrich option chain with Greeks calculations."""
        if spot_prices is None:
            spot_prices = st.session_state.get("spot_prices", {})
        enriched = self.greeks_engine.enrich_option_chain(chain, spot_prices)
        self._persist_data(enriched, "greeks")
        return enriched

    def compute_volatility(
        self, prices: pd.Series, option_chain: Optional[pd.DataFrame] = None
    ) -> dict:
        """Calculate volatility metrics for an underlying."""
        vol_data = {}
        if len(prices) >= 61:
            vol_data["hv_60"] = self.volatility_engine.calculate_historical_volatility(prices, window=60)
        if len(prices) >= 31:
            vol_data["hv_30"] = self.volatility_engine.calculate_historical_volatility(prices, window=30)
        if len(prices) >= 21:
            vol_data["hv_20"] = self.volatility_engine.calculate_historical_volatility(prices, window=20)

        if option_chain is not None and not option_chain.empty:
            try:
                iv_current = self.volatility_engine.extract_implied_volatility(option_chain)
                vol_data["iv_current"] = iv_current
                if len(prices) >= 253:
                    iv_history = prices.rolling(window=20).std() * (252 ** 0.5) / prices
                    iv_history = iv_history.dropna()
                    if not iv_history.empty:
                        vol_data["iv_rank"] = self.volatility_engine.calculate_iv_rank(iv_current, iv_history.tail(252))
                        vol_data["iv_percentile"] = self.volatility_engine.calculate_iv_percentile(iv_current, iv_history.tail(252))
                        vol_data["rating"] = self.volatility_engine.rate_volatility(vol_data["iv_rank"]).value
            except (ValueError, Exception) as e:
                logger.warning("IV-Berechnung fehlgeschlagen: %s", e)
        return vol_data

    def scan_strategies(
        self, enriched_chain: pd.DataFrame, volatility_data: dict, earnings: Optional[dict[str, list]] = None
    ) -> list[TradeSuggestion]:
        """Run all strategy scanners on enriched option chain."""
        if earnings is None:
            earnings = {}
        all_suggestions: list[TradeSuggestion] = []
        try:
            all_suggestions.extend(self.strategy_engine.scan_covered_calls(enriched_chain, volatility_data))
        except Exception as e:
            logger.warning("Covered Call Scan fehlgeschlagen: %s", e)
        try:
            all_suggestions.extend(self.strategy_engine.scan_cash_secured_puts(enriched_chain, volatility_data, earnings))
        except Exception as e:
            logger.warning("Cash Secured Put Scan fehlgeschlagen: %s", e)
        try:
            all_suggestions.extend(self.strategy_engine.scan_wheel_strategy(enriched_chain, volatility_data))
        except Exception as e:
            logger.warning("Wheel Strategy Scan fehlgeschlagen: %s", e)
        try:
            all_suggestions.extend(self.strategy_engine.scan_iron_condors(enriched_chain, volatility_data))
        except Exception as e:
            logger.warning("Iron Condor Scan fehlgeschlagen: %s", e)

        all_suggestions.sort(key=lambda s: s.combined_score, reverse=True)
        st.session_state.trade_suggestions = all_suggestions
        return all_suggestions

    def rank_suggestions(
        self, suggestions: list[TradeSuggestion], market_context: Optional[dict] = None
    ) -> list[RankedSuggestion]:
        """Rank trade suggestions using AI engine."""
        if market_context is None:
            market_context = {}
        ranked = self.ai_ranking_engine.rank_suggestions(suggestions, market_context)
        st.session_state.ranked_suggestions = ranked
        return ranked

    def compute_risk(
        self, portfolio: pd.DataFrame, market_data: Optional[pd.DataFrame] = None
    ) -> RiskMetrics:
        """Compute risk metrics for the portfolio."""
        if market_data is None:
            market_data = pd.DataFrame()
        metrics = self.risk_analyzer.calculate_risk_metrics(portfolio, market_data)
        st.session_state.risk_metrics = metrics
        return metrics

    def run_backtest(self, config: BacktestConfig) -> Optional[BacktestResult]:
        """Run a backtest with the given configuration."""
        try:
            engine = BacktestingEngine(config)
            historical_chains = st.session_state.get("option_chains", {})
            if not historical_chains:
                return None
            all_chains = pd.concat(list(historical_chains.values()), ignore_index=True) if historical_chains else pd.DataFrame()
            historical_prices = st.session_state.get("historical_prices", pd.DataFrame())
            if all_chains.empty:
                return None
            result = engine.run_backtest(all_chains, historical_prices)
            backtest_key = f"{config.strategy_type}_{config.start_date}_{config.end_date}"
            st.session_state.backtest_results[backtest_key] = result
            return result
        except Exception as e:
            logger.error("Backtest fehlgeschlagen: %s", e)
            return None

    def _persist_option_chains(self, chains: dict[str, pd.DataFrame]) -> None:
        for symbol, chain in chains.items():
            if chain.empty:
                continue
            try:
                envelope = DataEnvelope(data=chain, timestamp=datetime.now(timezone.utc), version=self.config.version, data_type=f"option_chain_{symbol.lower()}")
                self.serialization.serialize(envelope, format="parquet")
            except Exception as e:
                logger.warning("Persistierung für %s fehlgeschlagen: %s", symbol, e)

    def _persist_data(self, data: pd.DataFrame, data_type: str) -> None:
        if data.empty:
            return
        try:
            envelope = DataEnvelope(data=data, timestamp=datetime.now(timezone.utc), version=self.config.version, data_type=data_type)
            self.serialization.serialize(envelope, format="parquet")
        except Exception as e:
            logger.warning("Persistierung für '%s' fehlgeschlagen: %s", data_type, e)

    def _load_persisted_chain(self, symbol: str) -> Optional[pd.DataFrame]:
        try:
            data_dir = Path(self.config.data_path) / "processed"
            if not data_dir.exists():
                return None
            pattern = f"option_chain_{symbol.lower()}_*.parquet"
            files = sorted(data_dir.glob(pattern), reverse=True)
            if not files:
                pattern_json = f"option_chain_{symbol.lower()}_*.json"
                files = sorted(data_dir.glob(pattern_json), reverse=True)
            if files:
                envelope = self.serialization.deserialize(files[0])
                return envelope.data
            return None
        except Exception:
            return None

    def _load_cached_data(self) -> None:
        config = self.config
        data_dir = Path(config.data_path) / "processed"
        if not data_dir.exists():
            return
        for symbol in config.underlyings:
            chain = self._load_persisted_chain(symbol)
            if chain is not None:
                st.session_state.option_chains[symbol] = chain


def get_pipeline() -> DataPipeline:
    """Get or create the DataPipeline instance."""
    if "data_pipeline" not in st.session_state:
        pipeline = DataPipeline()
        pipeline.initialize()
        st.session_state.data_pipeline = pipeline
    return st.session_state.data_pipeline
