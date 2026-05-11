"""Greek-KPI-Definitionen für ThetaFlow AI.

Fachliche Definitionen und praxisbezogene Interpretationen der Options-Greeks
(Delta, Gamma, Theta, Vega, Rho) im Kontext von Stillhalter-Strategien.
"""

from typing import Optional


# Zentrale KPI-Definitionen für alle Greeks
_KPI_DEFINITIONS: dict[str, dict] = {
    "delta": {
        "name": "Delta",
        "definition": (
            "Delta misst die Sensitivität des Optionspreises gegenüber einer "
            "Veränderung des Basiswertkurses um eine Einheit. Mathematisch ist "
            "Delta die erste partielle Ableitung des Optionspreises nach dem "
            "Kurs des Underlyings: Δ = ∂V/∂S. Für Calls liegt Delta zwischen "
            "0 und 1, für Puts zwischen -1 und 0. Delta kann auch als "
            "approximative Wahrscheinlichkeit interpretiert werden, dass die "
            "Option am Verfallstag im Geld (ITM) endet."
        ),
        "interpretation": (
            "Für Stillhalter (Optionsverkäufer) ist ein niedriges absolutes "
            "Delta wünschenswert, da es eine geringere Wahrscheinlichkeit "
            "bedeutet, dass die Option ins Geld läuft. Günstige Bereiche für "
            "Short Puts: Delta zwischen -0.10 und -0.30 (entspricht ca. "
            "10-30% ITM-Wahrscheinlichkeit). Für Covered Calls: Delta "
            "zwischen 0.15 und 0.30. Ein Delta nahe 0 bietet maximalen "
            "Schutz, aber geringere Prämien. Ein Delta über 0.30 (absolut) "
            "erhöht das Zuweisungsrisiko deutlich."
        ),
        "unit": "Einheitslos (0 bis ±1)",
        "favorable_range": {"min": 0.10, "max": 0.30},
    },
    "gamma": {
        "name": "Gamma",
        "definition": (
            "Gamma misst die Änderungsrate von Delta bei einer Veränderung "
            "des Basiswertkurses um eine Einheit. Mathematisch ist Gamma die "
            "zweite partielle Ableitung des Optionspreises nach dem Kurs des "
            "Underlyings: Γ = ∂²V/∂S². Gamma ist für Calls und Puts immer "
            "positiv und erreicht sein Maximum bei At-the-Money-Optionen "
            "mit kurzer Restlaufzeit."
        ),
        "interpretation": (
            "Für Stillhalter ist Gamma ein Risikofaktor: Ein hohes Gamma "
            "bedeutet, dass sich Delta bei Kursbewegungen schnell ändert, "
            "was das Risiko plötzlicher Verluste erhöht. Stillhalter sind "
            "grundsätzlich 'short Gamma' – sie profitieren von stabilen "
            "Kursen. Günstig sind niedrige Gamma-Werte (< 0.05), die bei "
            "Out-of-the-Money-Optionen mit längerer Restlaufzeit auftreten. "
            "Vorsicht bei Gamma > 0.10, besonders kurz vor Verfall, da hier "
            "das 'Gamma-Risiko' stark ansteigt."
        ),
        "unit": "1/Kurseinheit",
        "favorable_range": {"min": 0.00, "max": 0.05},
    },
    "theta": {
        "name": "Theta",
        "definition": (
            "Theta misst den täglichen Zeitwertverfall einer Option – also "
            "wie viel Wert die Option pro Tag verliert, wenn alle anderen "
            "Faktoren konstant bleiben. Mathematisch ist Theta die partielle "
            "Ableitung des Optionspreises nach der Zeit: Θ = ∂V/∂t. Theta "
            "ist für Long-Positionen negativ (Wertverlust) und wird "
            "üblicherweise als negativer Wert pro Tag angegeben."
        ),
        "interpretation": (
            "Theta ist der wichtigste Greek für Stillhalter, da der "
            "Zeitwertverfall die primäre Ertragsquelle darstellt. Ein "
            "betragsmäßig hohes (negatives) Theta ist günstig für "
            "Optionsverkäufer – es bedeutet, dass die verkaufte Option "
            "schnell an Wert verliert. Optimale Theta-Werte hängen von der "
            "Prämie ab, aber generell gilt: Je höher der tägliche "
            "Zeitwertverfall relativ zur erhaltenen Prämie, desto besser. "
            "Der Zeitwertverfall beschleunigt sich in den letzten 30-45 "
            "Tagen vor Verfall, weshalb Stillhalter oft Optionen mit "
            "20-45 DTE verkaufen."
        ),
        "unit": "USD/Tag",
        "favorable_range": {"min": -0.50, "max": -0.01},
    },
    "vega": {
        "name": "Vega",
        "definition": (
            "Vega misst die Sensitivität des Optionspreises gegenüber einer "
            "Veränderung der impliziten Volatilität um einen Prozentpunkt. "
            "Mathematisch: ν = ∂V/∂σ. Vega ist für Calls und Puts immer "
            "positiv und erreicht sein Maximum bei At-the-Money-Optionen "
            "mit langer Restlaufzeit. Vega ist kein griechischer Buchstabe, "
            "wird aber konventionell zu den 'Greeks' gezählt."
        ),
        "interpretation": (
            "Für Stillhalter ist Vega ein zweischneidiges Schwert: "
            "Optionsverkäufer sind 'short Vega' – sie profitieren von "
            "sinkender impliziter Volatilität. Daher ist es günstig, "
            "Optionen bei hoher IV (IV Rank > 30) zu verkaufen und auf "
            "einen Rückgang der Volatilität zu setzen (Volatility Crush). "
            "Ein niedriges Vega (< 0.10) reduziert das Risiko durch "
            "Volatilitätsänderungen. Hohe Vega-Werte (> 0.20) bedeuten "
            "erhöhtes Risiko bei steigender Volatilität, bieten aber auch "
            "höhere Prämien beim Verkauf."
        ),
        "unit": "USD/Prozentpunkt IV",
        "favorable_range": {"min": 0.01, "max": 0.15},
    },
    "rho": {
        "name": "Rho",
        "definition": (
            "Rho misst die Sensitivität des Optionspreises gegenüber einer "
            "Veränderung des risikofreien Zinssatzes um einen Prozentpunkt. "
            "Mathematisch: ρ = ∂V/∂r. Für Calls ist Rho positiv (steigende "
            "Zinsen erhöhen den Call-Wert), für Puts negativ (steigende "
            "Zinsen senken den Put-Wert). Rho hat bei kurzfristigen "
            "Optionen einen relativ geringen Einfluss."
        ),
        "interpretation": (
            "Für Stillhalter mit kurzfristigen Strategien (DTE 20-45) ist "
            "Rho in der Regel der am wenigsten relevante Greek, da "
            "Zinsänderungen über kurze Zeiträume minimal sind. Bei "
            "längerfristigen Positionen oder in Phasen starker "
            "Zinsänderungen kann Rho jedoch relevant werden. Für "
            "Put-Verkäufer (Cash Secured Puts) sind steigende Zinsen "
            "tendenziell günstig, da sie den Put-Wert senken. Typische "
            "Rho-Werte für kurzfristige Optionen liegen nahe 0 und "
            "erfordern keine aktive Steuerung."
        ),
        "unit": "USD/Prozentpunkt Zins",
        "favorable_range": {"min": -0.05, "max": 0.05},
    },
}


def get_kpi_definition(greek_name: str) -> dict:
    """Fachliche Definition und Interpretation eines Greek-KPIs abrufen."""
    key = greek_name.strip().lower()
    if key not in _KPI_DEFINITIONS:
        valid_names = ", ".join(sorted(_KPI_DEFINITIONS.keys()))
        raise KeyError(
            f"Unbekannter Greek-KPI: '{greek_name}'. "
            f"Gültige Werte: {valid_names}"
        )
    return _KPI_DEFINITIONS[key].copy()


def get_all_kpi_definitions() -> dict[str, dict]:
    """Alle Greek-KPI-Definitionen abrufen."""
    return {key: value.copy() for key, value in _KPI_DEFINITIONS.items()}
