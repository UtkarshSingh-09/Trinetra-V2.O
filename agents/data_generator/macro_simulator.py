# macro_simulator.py
import random

class MacroEconomicSimulator:
    """
    Simulates macroeconomic environments (expansion, contraction, neutral)
    and policy cycles (RBI repo rate, inflation/WPI/CPI, GDP trends)
    to adjust financial indicators realistically.
    """

    def __init__(self, regime: str = "neutral"):
        self.regime = regime.lower()
        
        # Calibration of policy rates
        # Repo rates: FY24 (~6.5%), FY25 (~6.5%), FY26 (~6.25%)
        self.repo_rates = {
            "fy24": 0.0650,
            "fy25": 0.0650,
            "fy26": 0.0625
        }
        
        # Inflation indices
        if self.regime == "contraction":
            self.gdp_multiplier = 0.85
            self.inflation_rate = 0.075  # High inflation / stagflation
            self.credit_spread = 0.025   # High risk premium
        elif self.regime == "expansion":
            self.gdp_multiplier = 1.15
            self.inflation_rate = 0.045  # Goldilocks zone
            self.credit_spread = 0.012   # Low risk premium
        else: # Neutral
            self.gdp_multiplier = 1.00
            self.inflation_rate = 0.055
            self.credit_spread = 0.018

    def get_interest_rate(self, fiscal_year: str) -> float:
        """Returns repo rate + credit spread + random variation."""
        base_rate = self.repo_rates.get(fiscal_year.lower(), 0.0650)
        spread = self.credit_spread + random.uniform(0.015, 0.045)
        return float(base_rate + spread)

    def apply_macro_adjustments(self, sector: str, ratios: dict) -> dict:
        """
        Adjusts generated financial ratios based on macro regime and sector sensitivity.
        """
        # Construction and Steel are highly sensitive; IT and Healthcare are defensive
        if sector in ["Construction & Infrastructure", "Real Estate", "Steel Fabrication"]:
            sensitivity = 1.3
        elif sector in ["IT Services", "Healthcare Services", "Pharma Manufacturing"]:
            sensitivity = 0.6
        else:
            sensitivity = 1.0

        # Adjust EBITDA margin due to inflation impact
        margin_impact = -0.015 * sensitivity * (self.inflation_rate / 0.05)
        ratios["ebitda_margin"] = max(0.01, ratios["ebitda_margin"] + margin_impact)

        # Adjust DSCR and ICR based on credit cycle & interest rates
        if self.regime == "contraction":
            ratios["dscr"] = max(0.2, ratios["dscr"] * (1 - 0.15 * sensitivity))
            ratios["icr"] = max(0.3, ratios["icr"] * (1 - 0.20 * sensitivity))
            ratios["revenue_growth_yoy"] = ratios["revenue_growth_yoy"] - 0.08 * sensitivity
        elif self.regime == "expansion":
            ratios["dscr"] = ratios["dscr"] * (1 + 0.10 * sensitivity)
            ratios["icr"] = ratios["icr"] * (1 + 0.12 * sensitivity)
            ratios["revenue_growth_yoy"] = ratios["revenue_growth_yoy"] + 0.06 * sensitivity

        return ratios
