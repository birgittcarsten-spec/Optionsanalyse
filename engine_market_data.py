"""Market Data Loader - Abruf und Normalisierung von Marktdaten aus externen APIs.

Stellt die abstrakte Basisklasse DataSourceAdapter sowie konkrete
Implementierungen für Interactive Brokers, Finnhub und Polygon.io bereit.
"""

import logging
import time
from abc import ABC, abstractmethod
from datetime import date, timedelta
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


class DataSourceError(Exception):
    """Fehler bei der Kommunikation mit einer Datenquelle."""

    def __init__(self, source: str, message: str, original_error: Optional[Exception] = None):
        self.source = source
        self.original_error = original_error
        full_message = f"[{source}] {message}"
        if original_error:
            full_message += f" (Ursache: {original_error})"
        super().__init__(full_message)


class DataSourceAdapter(ABC):
    """Abstrakte Basisklasse für Datenquellen-Adapter."""

    @abstractmethod
    def connect(self) -> bool:
        ...

    @abstractmethod
    def get_option_chain(self, underlying: str, expiration: Optional[date] = None) -> pd.DataFrame:
        ...

    @abstractmethod
    def get_stock_price(self, symbol: str) -> float:
        ...

    @abstractmethod
    def get_earnings_calendar(self, symbol: str) -> list[date]:
        ...


class IBAdapter(DataSourceAdapter):
    """Interactive Brokers Adapter via ib_insync."""

    def __init__(self, host: str = "127.0.0.1", port: int = 7497, client_id: int = 1):
        self.host = host
        self.port = port
        self.client_id = client_id
        self._ib = None
        self._connected = False

    def connect(self) -> bool:
        try:
            from ib_insync import IB
            self._ib = IB()
            self._ib.connect(self.host, self.port, clientId=self.client_id)
            self._connected = True
            return True
        except Exception as e:
            self._connected = False
            raise DataSourceError(
                source="InteractiveBrokers",
                message=f"Verbindung zu TWS fehlgeschlagen ({self.host}:{self.port})",
                original_error=e,
            )

    def get_option_chain(self, underlying: str, expiration: Optional[date] = None) -> pd.DataFrame:
        if not self._connected or self._ib is None:
            raise DataSourceError(
                source="InteractiveBrokers",
                message="Keine aktive Verbindung.",
            )
        try:
            from ib_insync import Stock, Option
            contract = Stock(underlying, "SMART", "USD")
            self._ib.qualifyContracts(contract)
            chains = self._ib.reqSecDefOptParams(
                contract.symbol, "", contract.secType, contract.conId
            )
            if not chains:
                return pd.DataFrame(
                    columns=["underlying", "strike", "expiration", "option_type",
                             "bid", "ask", "last", "volume", "open_interest", "dte"]
                )
            chain = chains[0]
            expirations = chain.expirations
            if expiration:
                expirations = [exp for exp in expirations if exp == expiration.strftime("%Y%m%d")]
            strikes = chain.strikes
            rows = []
            for exp in expirations:
                for strike in strikes:
                    for right in ["C", "P"]:
                        opt_contract = Option(underlying, exp, strike, right, "SMART")
                        ticker = self._ib.reqMktData(opt_contract)
                        self._ib.sleep(0.1)
                        exp_date = date(int(exp[:4]), int(exp[4:6]), int(exp[6:8]))
                        dte = (exp_date - date.today()).days
                        rows.append({
                            "underlying": underlying,
                            "strike": float(strike),
                            "expiration": exp_date,
                            "option_type": "call" if right == "C" else "put",
                            "bid": float(ticker.bid) if ticker.bid else 0.0,
                            "ask": float(ticker.ask) if ticker.ask else 0.0,
                            "last": float(ticker.last) if ticker.last else 0.0,
                            "volume": int(ticker.volume) if ticker.volume else 0,
                            "open_interest": 0,
                            "dte": dte,
                        })
            return pd.DataFrame(rows)
        except DataSourceError:
            raise
        except Exception as e:
            raise DataSourceError(
                source="InteractiveBrokers",
                message=f"Fehler beim Abruf der Optionskette für {underlying}",
                original_error=e,
            )

    def get_stock_price(self, symbol: str) -> float:
        if not self._connected or self._ib is None:
            raise DataSourceError(source="InteractiveBrokers", message="Keine aktive Verbindung.")
        try:
            from ib_insync import Stock
            contract = Stock(symbol, "SMART", "USD")
            self._ib.qualifyContracts(contract)
            ticker = self._ib.reqMktData(contract)
            self._ib.sleep(1)
            price = ticker.marketPrice()
            if price != price:
                raise DataSourceError(source="InteractiveBrokers", message=f"Kein gültiger Kurs für {symbol}")
            return float(price)
        except DataSourceError:
            raise
        except Exception as e:
            raise DataSourceError(source="InteractiveBrokers", message=f"Fehler beim Abruf des Kurses für {symbol}", original_error=e)

    def get_earnings_calendar(self, symbol: str) -> list[date]:
        return []


class FinnhubAdapter(DataSourceAdapter):
    """Finnhub API Adapter."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._base_url = "https://finnhub.io/api/v1"
        self._connected = False

    def connect(self) -> bool:
        if not self.api_key:
            raise DataSourceError(source="Finnhub", message="Kein API-Key konfiguriert.")
        try:
            import requests
            response = requests.get(
                f"{self._base_url}/stock/profile2",
                params={"symbol": "AAPL", "token": self.api_key},
                timeout=10,
            )
            if response.status_code == 401:
                raise DataSourceError(source="Finnhub", message="Ungültiger API-Key")
            if response.status_code == 429:
                raise DataSourceError(source="Finnhub", message="API-Rate-Limit erreicht.")
            response.raise_for_status()
            self._connected = True
            return True
        except DataSourceError:
            raise
        except Exception as e:
            raise DataSourceError(source="Finnhub", message="Verbindung fehlgeschlagen", original_error=e)

    def get_option_chain(self, underlying: str, expiration: Optional[date] = None) -> pd.DataFrame:
        if not self._connected:
            raise DataSourceError(source="Finnhub", message="Keine aktive Verbindung.")
        try:
            import requests
            response = requests.get(
                f"{self._base_url}/stock/option-chain",
                params={"symbol": underlying, "token": self.api_key},
                timeout=30,
            )
            if response.status_code != 200:
                raise DataSourceError(source="Finnhub", message=f"Optionskette für {underlying} nicht verfügbar")
            data = response.json()
            rows = []
            for chain_entry in data.get("data", []):
                exp_str = chain_entry.get("expirationDate", "")
                if not exp_str:
                    continue
                exp_date = date.fromisoformat(exp_str)
                if expiration and exp_date != expiration:
                    continue
                dte = (exp_date - date.today()).days
                for option_type_key, option_type_name in [("options.C", "call"), ("options.P", "put")]:
                    options_data = chain_entry.get(option_type_key, [])
                    for opt in options_data:
                        rows.append({
                            "underlying": underlying,
                            "strike": float(opt.get("strike", 0)),
                            "expiration": exp_date,
                            "option_type": option_type_name,
                            "bid": float(opt.get("bid", 0)),
                            "ask": float(opt.get("ask", 0)),
                            "last": float(opt.get("lastPrice", 0)),
                            "volume": int(opt.get("volume", 0)),
                            "open_interest": int(opt.get("openInterest", 0)),
                            "dte": dte,
                        })
            return pd.DataFrame(rows, columns=["underlying", "strike", "expiration", "option_type", "bid", "ask", "last", "volume", "open_interest", "dte"])
        except DataSourceError:
            raise
        except Exception as e:
            raise DataSourceError(source="Finnhub", message=f"Fehler beim Abruf für {underlying}", original_error=e)

    def get_stock_price(self, symbol: str) -> float:
        if not self._connected:
            raise DataSourceError(source="Finnhub", message="Keine aktive Verbindung.")
        try:
            import requests
            response = requests.get(f"{self._base_url}/quote", params={"symbol": symbol, "token": self.api_key}, timeout=10)
            if response.status_code != 200:
                raise DataSourceError(source="Finnhub", message=f"Kurs für {symbol} nicht verfügbar")
            data = response.json()
            price = data.get("c", 0.0)
            if not price or price <= 0:
                raise DataSourceError(source="Finnhub", message=f"Kein gültiger Kurs für {symbol}")
            return float(price)
        except DataSourceError:
            raise
        except Exception as e:
            raise DataSourceError(source="Finnhub", message=f"Fehler beim Abruf des Kurses für {symbol}", original_error=e)

    def get_earnings_calendar(self, symbol: str) -> list[date]:
        if not self._connected:
            raise DataSourceError(source="Finnhub", message="Keine aktive Verbindung.")
        try:
            import requests
            today = date.today()
            response = requests.get(
                f"{self._base_url}/calendar/earnings",
                params={"symbol": symbol, "from": today.isoformat(), "to": date(today.year + 1, today.month, today.day).isoformat(), "token": self.api_key},
                timeout=10,
            )
            if response.status_code != 200:
                return []
            data = response.json()
            earnings_dates = []
            for entry in data.get("earningsCalendar", []):
                if entry.get("symbol") == symbol:
                    earnings_date = date.fromisoformat(entry["date"])
                    if earnings_date >= today:
                        earnings_dates.append(earnings_date)
            return sorted(earnings_dates)
        except DataSourceError:
            raise
        except Exception as e:
            raise DataSourceError(source="Finnhub", message=f"Fehler beim Abruf des Earnings-Kalenders für {symbol}", original_error=e)


class PolygonAdapter(DataSourceAdapter):
    """Polygon.io Adapter (optional)."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._base_url = "https://api.polygon.io"
        self._connected = False

    def connect(self) -> bool:
        if not self.api_key:
            raise DataSourceError(source="Polygon", message="Kein API-Key konfiguriert.")
        try:
            import requests
            response = requests.get(f"{self._base_url}/v3/reference/tickers", params={"ticker": "AAPL", "apiKey": self.api_key}, timeout=10)
            if response.status_code in (401, 403):
                raise DataSourceError(source="Polygon", message="Ungültiger API-Key")
            if response.status_code == 429:
                raise DataSourceError(source="Polygon", message="API-Rate-Limit erreicht.")
            response.raise_for_status()
            self._connected = True
            return True
        except DataSourceError:
            raise
        except Exception as e:
            raise DataSourceError(source="Polygon", message="Verbindung fehlgeschlagen", original_error=e)

    def get_option_chain(self, underlying: str, expiration: Optional[date] = None) -> pd.DataFrame:
        if not self._connected:
            raise DataSourceError(source="Polygon", message="Keine aktive Verbindung.")
        try:
            import requests
            params = {"underlying_ticker": underlying, "apiKey": self.api_key, "limit": 250}
            if expiration:
                params["expiration_date"] = expiration.isoformat()
            response = requests.get(f"{self._base_url}/v3/snapshot/options/{underlying}", params=params, timeout=30)
            if response.status_code != 200:
                raise DataSourceError(source="Polygon", message=f"Optionskette für {underlying} nicht verfügbar")
            data = response.json()
            rows = []
            for result in data.get("results", []):
                details = result.get("details", {})
                day = result.get("day", {})
                exp_str = details.get("expiration_date", "")
                if not exp_str:
                    continue
                exp_date = date.fromisoformat(exp_str)
                dte = (exp_date - date.today()).days
                contract_type = details.get("contract_type", "").lower()
                if contract_type not in ("call", "put"):
                    continue
                rows.append({
                    "underlying": underlying,
                    "strike": float(details.get("strike_price", 0)),
                    "expiration": exp_date,
                    "option_type": contract_type,
                    "bid": float(result.get("last_quote", {}).get("bid", 0)),
                    "ask": float(result.get("last_quote", {}).get("ask", 0)),
                    "last": float(day.get("close", 0)),
                    "volume": int(day.get("volume", 0)),
                    "open_interest": int(result.get("open_interest", 0)),
                    "dte": dte,
                })
            return pd.DataFrame(rows, columns=["underlying", "strike", "expiration", "option_type", "bid", "ask", "last", "volume", "open_interest", "dte"])
        except DataSourceError:
            raise
        except Exception as e:
            raise DataSourceError(source="Polygon", message=f"Fehler beim Abruf für {underlying}", original_error=e)

    def get_stock_price(self, symbol: str) -> float:
        if not self._connected:
            raise DataSourceError(source="Polygon", message="Keine aktive Verbindung.")
        try:
            import requests
            response = requests.get(f"{self._base_url}/v2/aggs/ticker/{symbol}/prev", params={"apiKey": self.api_key}, timeout=10)
            if response.status_code != 200:
                raise DataSourceError(source="Polygon", message=f"Kurs für {symbol} nicht verfügbar")
            data = response.json()
            results = data.get("results", [])
            if not results:
                raise DataSourceError(source="Polygon", message=f"Kein gültiger Kurs für {symbol}")
            price = results[0].get("c", 0.0)
            if not price or price <= 0:
                raise DataSourceError(source="Polygon", message=f"Kein gültiger Kurs für {symbol}")
            return float(price)
        except DataSourceError:
            raise
        except Exception as e:
            raise DataSourceError(source="Polygon", message=f"Fehler beim Abruf des Kurses für {symbol}", original_error=e)

    def get_earnings_calendar(self, symbol: str) -> list[date]:
        if not self._connected:
            raise DataSourceError(source="Polygon", message="Keine aktive Verbindung.")
        return []


class MarketDataLoader:
    """Hauptklasse für den Marktdaten-Abruf mit Adapter-Orchestrierung."""

    OPTION_CHAIN_COLUMNS = [
        "underlying", "strike", "expiration", "option_type",
        "bid", "ask", "last", "volume", "open_interest", "dte",
    ]

    def __init__(self, adapters: list[DataSourceAdapter], config: Optional[dict] = None):
        if not adapters:
            raise ValueError("Mindestens ein Adapter muss konfiguriert sein.")
        self.adapters = adapters
        self.config = config or {}
        self._max_retries = self.config.get("max_retries", 3)
        self._base_delay = self.config.get("base_delay", 1.0)

    def _execute_with_retry(self, operation_name: str, func, *args, **kwargs):
        """Operation mit Retry und exponentiellem Backoff ausführen."""
        errors: list[str] = []
        for adapter in self.adapters:
            adapter_name = type(adapter).__name__
            last_error: Optional[Exception] = None
            for attempt in range(1, self._max_retries + 1):
                try:
                    result = func(adapter, *args, **kwargs)
                    return result
                except DataSourceError as e:
                    last_error = e
                    delay = self._base_delay * (2 ** (attempt - 1))
                    if attempt < self._max_retries:
                        time.sleep(delay)
                except Exception as e:
                    last_error = e
                    delay = self._base_delay * (2 ** (attempt - 1))
                    if attempt < self._max_retries:
                        time.sleep(delay)
            error_msg = f"{adapter_name}: {last_error}"
            errors.append(error_msg)

        aggregated_msg = f"{operation_name} fehlgeschlagen. Alle Adapter erschöpft. Fehler: {'; '.join(errors)}"
        raise DataSourceError(source="MarketDataLoader", message=aggregated_msg)

    def _normalize_option_chain(self, df: pd.DataFrame, underlying: str) -> pd.DataFrame:
        """Option Chain DataFrame in einheitliches Schema normalisieren."""
        if df.empty:
            return pd.DataFrame(columns=self.OPTION_CHAIN_COLUMNS)

        normalized = pd.DataFrame()
        normalized["underlying"] = df["underlying"] if "underlying" in df.columns else underlying
        normalized["strike"] = pd.to_numeric(df.get("strike", 0), errors="coerce").fillna(0.0)
        normalized["expiration"] = pd.to_datetime(df.get("expiration", pd.NaT), errors="coerce").dt.date
        normalized["option_type"] = df.get("option_type", "").astype(str).str.lower()
        normalized["bid"] = pd.to_numeric(df.get("bid", 0), errors="coerce").fillna(0.0)
        normalized["ask"] = pd.to_numeric(df.get("ask", 0), errors="coerce").fillna(0.0)
        normalized["last"] = pd.to_numeric(df.get("last", 0), errors="coerce").fillna(0.0)
        normalized["volume"] = pd.to_numeric(df.get("volume", 0), errors="coerce").fillna(0).astype(int)
        normalized["open_interest"] = pd.to_numeric(df.get("open_interest", 0), errors="coerce").fillna(0).astype(int)
        normalized["dte"] = pd.to_numeric(df.get("dte", 0), errors="coerce").fillna(0).astype(int)

        return normalized[self.OPTION_CHAIN_COLUMNS]

    def load_option_chain(self, underlying: str) -> pd.DataFrame:
        """Optionskette laden und normalisieren."""
        def _fetch_chain(adapter: DataSourceAdapter, symbol: str) -> pd.DataFrame:
            return adapter.get_option_chain(symbol)

        raw_df = self._execute_with_retry(f"load_option_chain({underlying})", _fetch_chain, underlying)
        normalized = self._normalize_option_chain(raw_df, underlying)
        return normalized

    def load_stock_data(self, symbols: list[str]) -> pd.DataFrame:
        """Aktienkurse für mehrere Symbole laden."""
        rows: list[dict] = []
        for symbol in symbols:
            try:
                def _fetch_price(adapter: DataSourceAdapter, sym: str) -> float:
                    return adapter.get_stock_price(sym)
                price = self._execute_with_retry(f"load_stock_data({symbol})", _fetch_price, symbol)
                rows.append({"symbol": symbol, "price": float(price), "timestamp": pd.Timestamp.now()})
            except DataSourceError:
                rows.append({"symbol": symbol, "price": float("nan"), "timestamp": pd.Timestamp.now()})
        return pd.DataFrame(rows, columns=["symbol", "price", "timestamp"])

    def load_historical_prices(self, symbol: str, days: int = 252) -> pd.DataFrame:
        """Historische Kursdaten laden."""
        def _fetch_historical(adapter: DataSourceAdapter, sym: str) -> pd.DataFrame:
            if hasattr(adapter, "get_historical_prices"):
                return adapter.get_historical_prices(sym, days)
            price = adapter.get_stock_price(sym)
            return pd.DataFrame([{"date": date.today(), "symbol": sym, "close": float(price)}])

        raw_df = self._execute_with_retry(f"load_historical_prices({symbol}, {days})", _fetch_historical, symbol)
        normalized = pd.DataFrame()
        normalized["date"] = pd.to_datetime(raw_df.get("date", pd.NaT), errors="coerce").dt.date
        normalized["symbol"] = raw_df.get("symbol", symbol)
        normalized["close"] = pd.to_numeric(raw_df.get("close", 0), errors="coerce").fillna(0.0)
        return normalized
