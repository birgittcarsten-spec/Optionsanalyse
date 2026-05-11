"""Portfolio-Seite für das ThetaFlow AI Dashboard.

Manuelle Trade-Eingabe, P&L-Tracking, Risikokennzahlen.
Positionen werden im Session State gespeichert.
"""

import json
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import date, datetime, timedelta
from pathlib import Path

from pipeline import load_live_quotes


# ---------------------------------------------------------------------------
# Persistence (JSON file for positions)
# ---------------------------------------------------------------------------

PORTFOLIO_FILE = "portfolio_data.json"


def _load_positions() -> list[dict]:
    """Positionen aus Session State oder Datei laden."""
    if "portfolio_positions" not in st.session_state:
        # Try loading from file
        if Path(PORTFOLIO_FILE).exists():
            try:
                with open(PORTFOLIO_FILE, "r", encoding="utf-8") as f:
                    st.session_state.portfolio_positions = json.load(f)
            except (json.JSONDecodeError, IOError):
                st.session_state.portfolio_positions = []
        else:
            st.session_state.portfolio_positions = []
    return st.session_state.portfolio_positions


def _save_positions(positions: list[dict]):
    """Positionen in Session State und Datei speichern."""
    st.session_state.portfolio_positions = positions
    try:
        with open(PORTFOLIO_FILE, "w", encoding="utf-8") as f:
            json.dump(positions, f, indent=2, ensure_ascii=False)
    except IOError:
        pass  # On Streamlit Cloud, file write may not persist across restarts


def _add_position(position: dict):
    """Neue Position hinzufügen."""
    positions = _load_positions()
    position["id"] = len(positions) + 1
    position["created_at"] = datetime.now().isoformat()
    positions.append(position)
    _save_positions(positions)


def _update_position_status(idx: int, new_status: str, close_value: float = 0.0):
    """Position-Status aktualisieren (schließen/rollen)."""
    positions = _load_positions()
    if 0 <= idx < len(positions):
        positions[idx]["status"] = new_status
        if new_status == "closed":
            positions[idx]["current_value"] = close_value
            premium = positions[idx]["premium_received"]
            positions[idx]["pnl"] = round((premium - close_value) * 100, 2)
            if premium > 0:
                positions[idx]["pnl_pct"] = round(
                    (premium - close_value) / premium * 100, 2
                )
        _save_positions(positions)


def _delete_position(idx: int):
    """Position löschen."""
    positions = _load_positions()
    if 0 <= idx < len(positions):
        positions.pop(idx)
        _save_positions(positions)


# ---------------------------------------------------------------------------
# Trade Entry Form
# ---------------------------------------------------------------------------


def _render_trade_entry_form():
    """Formular zur manuellen Trade-Eingabe."""
    st.markdown("### ➕ Neuen Trade eintragen")

    with st.form("new_trade_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)

        with col1:
            underlying = st.text_input("Underlying (Ticker)", value="AAPL").upper()
            strategy_type = st.selectbox(
                "Strategie",
                options=["cash_secured_put", "covered_call", "wheel", "iron_condor"],
                format_func=lambda x: {
                    "cash_secured_put": "Cash Secured Put",
                    "covered_call": "Covered Call",
                    "wheel": "Wheel Strategy",
                    "iron_condor": "Iron Condor",
                }.get(x, x),
            )
            option_type = st.selectbox("Optionstyp", options=["put", "call"])

        with col2:
            strike = st.number_input("Strike ($)", min_value=1.0, value=100.0, step=5.0)
            premium_received = st.number_input(
                "Erhaltene Prämie ($/Aktie)", min_value=0.01, value=2.00, step=0.25
            )
            entry_date = st.date_input("Eröffnungsdatum", value=date.today())

        with col3:
            expiration = st.date_input(
                "Verfallsdatum", value=date.today() + timedelta(days=30)
            )
            contracts = st.number_input("Anzahl Kontrakte", min_value=1, value=1, step=1)
            margin_used = st.number_input(
                "Margin-Bedarf ($)", min_value=0.0, value=strike * 20, step=100.0
            )

        submitted = st.form_submit_button("✅ Trade eintragen", use_container_width=True)

        if submitted:
            if not underlying:
                st.error("Bitte Ticker eingeben.")
            elif expiration <= entry_date:
                st.error("Verfallsdatum muss nach Eröffnungsdatum liegen.")
            else:
                new_position = {
                    "underlying": underlying,
                    "strategy_type": strategy_type,
                    "option_type": option_type,
                    "entry_date": entry_date.isoformat(),
                    "strike": strike,
                    "expiration": expiration.isoformat(),
                    "premium_received": premium_received,
                    "contracts": contracts,
                    "margin_used": margin_used,
                    "current_value": premium_received,  # Initial: at entry price
                    "pnl": 0.0,
                    "pnl_pct": 0.0,
                    "status": "open",
                }
                _add_position(new_position)
                st.success(
                    f"✅ {underlying} {strategy_type.replace('_', ' ').title()} "
                    f"${strike:.0f} {option_type.upper()} eingetragen "
                    f"(Prämie: ${premium_received:.2f} × {contracts} Kontrakte)"
                )
                st.rerun()


# ---------------------------------------------------------------------------
# Position Management
# ---------------------------------------------------------------------------


def _render_position_actions(positions: list[dict]):
    """Aktionen für bestehende Positionen (Schließen, Rollen, Löschen)."""
    open_positions = [(i, p) for i, p in enumerate(positions) if p["status"] == "open"]

    if not open_positions:
        st.info("Keine offenen Positionen. Trage oben einen neuen Trade ein.")
        return

    st.markdown("### ⚡ Position verwalten")

    col1, col2 = st.columns([2, 1])

    with col1:
        selected_pos_idx = st.selectbox(
            "Position auswählen",
            options=[i for i, _ in open_positions],
            format_func=lambda i: (
                f"{positions[i]['underlying']} | "
                f"${positions[i]['strike']:.0f} {positions[i].get('option_type', 'put').upper()} | "
                f"Verfall: {positions[i]['expiration']} | "
                f"Prämie: ${positions[i]['premium_received']:.2f}"
            ),
        )

    with col2:
        action = st.selectbox("Aktion", options=["Schließen", "Rollen", "Löschen"])

    if action == "Schließen":
        close_value = st.number_input(
            "Schließungspreis ($/Aktie)", min_value=0.0, value=0.0, step=0.25,
            help="0.00 = wertlos verfallen (voller Gewinn)"
        )
        if st.button("Position schließen", type="primary"):
            _update_position_status(selected_pos_idx, "closed", close_value)
            st.success("Position geschlossen.")
            st.rerun()

    elif action == "Rollen":
        if st.button("Position als gerollt markieren"):
            _update_position_status(selected_pos_idx, "rolled", 0.0)
            st.success("Position als gerollt markiert. Trage den neuen Trade oben ein.")
            st.rerun()

    elif action == "Löschen":
        if st.button("⚠️ Position löschen", type="secondary"):
            _delete_position(selected_pos_idx)
            st.warning("Position gelöscht.")
            st.rerun()


# ---------------------------------------------------------------------------
# Portfolio Analytics
# ---------------------------------------------------------------------------


def _calculate_risk_metrics(positions: list[dict]) -> dict:
    """Risikokennzahlen aus echten Positionen berechnen."""
    open_positions = [p for p in positions if p["status"] == "open"]

    if not open_positions:
        return {
            "max_drawdown": 0.0, "var_95": 0.0, "cvar_95": 0.0,
            "margin_usage": 0.0, "portfolio_exposure": 0.0,
        }

    total_margin = sum(p.get("margin_used", p["strike"] * 20) for p in open_positions)
    total_exposure = sum(
        p["strike"] * 100 * p.get("contracts", 1) for p in open_positions
    )
    total_pnl = sum(p["pnl"] for p in open_positions)
    total_premium = sum(p["premium_received"] * 100 * p.get("contracts", 1) for p in open_positions)

    # Simplified risk metrics based on position data
    margin_usage = total_margin / 100_000 if total_margin > 0 else 0.0  # Assume 100k account
    max_drawdown = min(0.0, total_pnl / total_exposure) if total_exposure > 0 else 0.0

    return {
        "max_drawdown": max_drawdown,
        "var_95": -0.02 * len(open_positions),  # Simplified estimate
        "cvar_95": -0.03 * len(open_positions),
        "margin_usage": min(margin_usage, 1.0),
        "portfolio_exposure": total_exposure,
    }


def _render_pnl_chart(positions: list[dict]):
    """P&L-Verteilung nach Position."""
    open_positions = [p for p in positions if p["status"] == "open"]
    if not open_positions:
        return

    fig = go.Figure()
    symbols = [f"{p['underlying']} ${p['strike']:.0f}" for p in open_positions]
    pnls = [p["pnl"] for p in open_positions]
    colors = ["#22c55e" if pnl >= 0 else "#ef4444" for pnl in pnls]

    fig.add_trace(go.Bar(
        x=symbols, y=pnls, marker_color=colors,
        text=[f"${pnl:+.0f}" for pnl in pnls], textposition="auto",
    ))
    fig.update_layout(
        title="P&L nach Position", xaxis_title="Position",
        yaxis_title="P&L ($)", template="plotly_white", height=300,
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_risk_gauge(risk_metrics: dict):
    """Risiko-Gauges."""
    col1, col2 = st.columns(2)
    with col1:
        fig = go.Figure(go.Indicator(
            mode="gauge+number", value=risk_metrics["margin_usage"] * 100,
            title={"text": "Margin-Auslastung (%)"},
            number={"suffix": "%"},
            gauge={"axis": {"range": [0, 100]}, "bar": {"color": "#6366f1"},
                   "steps": [{"range": [0, 50], "color": "#d1fae5"},
                             {"range": [50, 80], "color": "#fef3c7"},
                             {"range": [80, 100], "color": "#fee2e2"}],
                   "threshold": {"line": {"color": "red", "width": 4},
                                 "thickness": 0.75, "value": 80}},
        ))
        fig.update_layout(height=250, margin=dict(t=40, b=0))
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=risk_metrics["portfolio_exposure"] / 1000,
            title={"text": "Portfolio Exposure ($k)"},
            number={"suffix": "k"},
            gauge={"axis": {"range": [0, 500]}, "bar": {"color": "#f59e0b"}},
        ))
        fig.update_layout(height=250, margin=dict(t=40, b=0))
        st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Main Render
# ---------------------------------------------------------------------------


def render_portfolio():
    """Portfolio-Seite rendern."""
    st.title("💼 Portfolio")
    st.caption("Trades manuell eintragen, P&L tracken, Risiko überwachen")

    positions = _load_positions()

    # KPI-Karten
    open_positions = [p for p in positions if p["status"] == "open"]
    closed_positions = [p for p in positions if p["status"] == "closed"]
    total_pnl_open = sum(p["pnl"] for p in open_positions)
    total_pnl_closed = sum(p["pnl"] for p in closed_positions)
    total_premium_received = sum(
        p["premium_received"] * 100 * p.get("contracts", 1) for p in positions
    )

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Offene Positionen", len(open_positions))
    with col2:
        st.metric("P&L (offen)", f"${total_pnl_open:+,.0f}")
    with col3:
        st.metric("P&L (geschlossen)", f"${total_pnl_closed:+,.0f}")
    with col4:
        win_count = sum(1 for p in closed_positions if p["pnl"] > 0)
        total_closed = len(closed_positions)
        win_rate = (win_count / total_closed * 100) if total_closed > 0 else 0
        st.metric("Win Rate", f"{win_rate:.0f}%")
    with col5:
        st.metric("Prämien gesamt", f"${total_premium_received:,.0f}")

    st.markdown("---")

    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs(
        ["➕ Neuer Trade", "📋 Positionen", "📈 Analyse", "⚠️ Risiko"]
    )

    with tab1:
        _render_trade_entry_form()

    with tab2:
        if not positions:
            st.info("Noch keine Trades eingetragen. Nutze den Tab 'Neuer Trade'.")
        else:
            # Position management
            _render_position_actions(positions)

            st.markdown("---")
            st.markdown("### Alle Positionen")

            strategy_display = {
                "covered_call": "Covered Call", "cash_secured_put": "Cash Secured Put",
                "wheel": "Wheel", "iron_condor": "Iron Condor",
            }
            status_display = {
                "open": "🟢 Offen", "closed": "✅ Geschlossen", "rolled": "🔄 Gerollt",
            }

            table_data = []
            for p in positions:
                contracts = p.get("contracts", 1)
                table_data.append({
                    "Underlying": p["underlying"],
                    "Strategie": strategy_display.get(p["strategy_type"], p["strategy_type"]),
                    "Strike": f"${p['strike']:.2f}",
                    "Typ": p.get("option_type", "put").upper(),
                    "Kontrakte": contracts,
                    "Eröffnung": p["entry_date"],
                    "Verfall": p["expiration"],
                    "Prämie": f"${p['premium_received']:.2f}",
                    "P&L": f"${p['pnl']:+.0f}",
                    "P&L %": f"{p['pnl_pct']:+.1f}%",
                    "Status": status_display.get(p["status"], p["status"]),
                })

            df = pd.DataFrame(table_data)
            st.dataframe(df, use_container_width=True, hide_index=True)

    with tab3:
        if not positions:
            st.info("Noch keine Trades für Analyse vorhanden.")
        else:
            _render_pnl_chart(positions)

            # Summary stats
            col1, col2, col3 = st.columns(3)
            with col1:
                total_trades = len(positions)
                st.metric("Trades gesamt", total_trades)
            with col2:
                avg_premium = np.mean([p["premium_received"] for p in positions])
                st.metric("Ø Prämie", f"${avg_premium:.2f}")
            with col3:
                avg_dte = np.mean([
                    (date.fromisoformat(p["expiration"]) - date.fromisoformat(p["entry_date"])).days
                    for p in positions
                ])
                st.metric("Ø DTE bei Eröffnung", f"{avg_dte:.0f} Tage")

    with tab4:
        risk_metrics = _calculate_risk_metrics(positions)

        if risk_metrics["margin_usage"] >= 0.80:
            st.error(f"⚠️ Margin-Auslastung bei {risk_metrics['margin_usage']:.0%} – Schwellenwert überschritten!")

        _render_risk_gauge(risk_metrics)

        st.markdown("### Risikokennzahlen")
        risk_df = pd.DataFrame([
            {"Kennzahl": "Portfolio Exposure", "Wert": f"${risk_metrics['portfolio_exposure']:,.0f}"},
            {"Kennzahl": "Margin-Auslastung", "Wert": f"{risk_metrics['margin_usage']:.0%}"},
            {"Kennzahl": "Max Drawdown (geschätzt)", "Wert": f"{risk_metrics['max_drawdown']:.2%}"},
            {"Kennzahl": "Offene Positionen", "Wert": str(len(open_positions))},
        ])
        st.dataframe(risk_df, use_container_width=True, hide_index=True)
