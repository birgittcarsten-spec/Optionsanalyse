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
