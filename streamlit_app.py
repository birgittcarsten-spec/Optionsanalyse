"""ThetaFlow AI Platform - Streamlit Dashboard Entry Point.

Multi-Page App mit Seitennavigation für alle Analyse- und Empfehlungsseiten.
"""

import streamlit as st
from datetime import datetime

from pipeline import get_pipeline


def init_session_state():
    """Session State initialisieren und Pipeline starten."""
    if "initialized" not in st.session_state:
        st.session_state.initialized = True
        st.session_state.last_update = datetime.now()
        st.session_state.underlyings = [
            "AAPL", "MSFT", "SPY", "QQQ", "TSLA", "AMZN", "NVDA", "META"
        ]
        get_pipeline()


def main():
    """Streamlit Dashboard Hauptfunktion."""
    st.set_page_config(
        page_title="ThetaFlow AI",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    init_session_state()

    # Sidebar Navigation
    with st.sidebar:
        st.image("https://via.placeholder.com/200x60?text=ThetaFlow+AI", width=200)
        st.markdown("---")
        st.markdown("## Navigation")

        page = st.radio(
            "Seite wählen",
            options=[
                "🏠 Marktübersicht",
                "🔍 Scanner",
                "💼 Portfolio",
                "📊 Backtesting",
                "🤖 AI Insights",
            ],
            label_visibility="collapsed",
        )

        st.markdown("---")

        # Ticker-Verwaltung
        st.markdown("### 📌 Watchlist")
        
        # Aktuelle Ticker anzeigen
        current_tickers = st.session_state.underlyings
        st.caption(f"{len(current_tickers)} Ticker aktiv")
        
        # Ticker hinzufügen
        new_ticker = st.text_input(
            "Ticker hinzufügen",
            placeholder="z.B. GOOGL",
            key="new_ticker_input",
        )
        if st.button("➕ Hinzufügen", use_container_width=True, key="add_ticker_btn"):
            ticker = new_ticker.strip().upper()
            if ticker and ticker not in st.session_state.underlyings:
                st.session_state.underlyings.append(ticker)
                # Clear scanner cache so new ticker appears
                if "scanner_suggestions" in st.session_state:
                    del st.session_state.scanner_suggestions
                st.rerun()
            elif ticker in st.session_state.underlyings:
                st.warning(f"{ticker} ist bereits in der Watchlist.")
        
        # Ticker entfernen
        if len(current_tickers) > 1:
            remove_ticker = st.selectbox(
                "Ticker entfernen",
                options=[""] + current_tickers,
                key="remove_ticker_select",
            )
            if remove_ticker and st.button("🗑️ Entfernen", use_container_width=True, key="remove_ticker_btn"):
                st.session_state.underlyings.remove(remove_ticker)
                if "scanner_suggestions" in st.session_state:
                    del st.session_state.scanner_suggestions
                st.rerun()
        
        # Alle Ticker als Tags anzeigen
        st.caption(" · ".join(current_tickers))

        st.markdown("---")

        # Datenquelle wählen
        st.markdown("### 🔌 Datenquelle")
        data_source = st.radio(
            "Verbindung",
            options=["Finnhub API", "Interactive Brokers (lokal)"],
            index=0 if st.session_state.get("data_source", "finnhub") == "finnhub" else 1,
            key="data_source_radio",
        )
        
        if data_source == "Interactive Brokers (lokal)":
            st.session_state.data_source = "ib"
            ib_status = st.session_state.get("ib_connected", False)
            if ib_status:
                st.success("🟢 IB verbunden")
            else:
                st.warning("🔴 IB nicht verbunden")
                st.caption("TWS/Gateway muss auf Port 7497 laufen")
                if st.button("🔗 IB verbinden", use_container_width=True, key="ib_connect_btn"):
                    try:
                        import asyncio
                        try:
                            loop = asyncio.get_event_loop()
                        except RuntimeError:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                        
                        from ib_insync import IB, util
                        util.startLoop()  # ib_insync's eigene Event-Loop-Lösung
                        
                        ib = IB()
                        ib.connect("127.0.0.1", 7497, clientId=1)
                        
                        st.session_state.ib_connected = True
                        st.session_state.ib_instance = ib
                        st.success("✅ IB verbunden!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Verbindung fehlgeschlagen: {e}")
        else:
            st.session_state.data_source = "finnhub"
            st.caption("☁️ Cloud-Modus (Finnhub API)")

        st.markdown("---")

        st.markdown("### Daten-Status")
        last_update = st.session_state.get("last_update", datetime.now())
        st.caption(f"Letzte Aktualisierung:")
        st.caption(f"📅 {last_update.strftime('%d.%m.%Y %H:%M:%S')}")

        if st.button("🔄 Daten aktualisieren", use_container_width=True):
            pipeline = get_pipeline()
            pipeline.load_market_data(st.session_state.underlyings)
            st.session_state.last_update = datetime.now()
            st.rerun()

        st.markdown("---")
        st.markdown(
            "<div style='text-align: center; color: gray; font-size: 0.8em;'>"
            "ThetaFlow AI v1.0.0<br>Stillhalter-Strategien</div>",
            unsafe_allow_html=True,
        )

    # Seiten-Routing
    if page == "🏠 Marktübersicht":
        from page_market_overview import render_market_overview
        render_market_overview()
    elif page == "🔍 Scanner":
        from page_scanner import render_scanner
        render_scanner()
    elif page == "💼 Portfolio":
        from page_portfolio import render_portfolio
        render_portfolio()
    elif page == "📊 Backtesting":
        from page_backtesting import render_backtesting
        render_backtesting()
    elif page == "🤖 AI Insights":
        from page_ai_insights import render_ai_insights
        render_ai_insights()


if __name__ == "__main__":
    main()
