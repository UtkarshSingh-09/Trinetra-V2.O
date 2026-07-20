# fraud_simulator.py
import random
import numpy as np

FRAUD_ARCHETYPES = [
    "circular_trading",
    "revenue_inflation",
    "shell_company",
    "evergreening",
    "benami_siphoning",
    "seasonal_manipulation"
]

class FraudSimulator:
    """
    Simulates forensic signatures of specific financial and tax fraud archetypes
    across the financial profiles, GSTR records, and bank statement generators.
    """

    @staticmethod
    def get_archetype_for_sector(sector: str, sector_profile: dict) -> str:
        """Picks a sector-appropriate fraud archetype."""
        archetypes = sector_profile.get("fraud_archetypes", FRAUD_ARCHETYPES)
        return random.choice(archetypes)

    @staticmethod
    def apply_financial_shifts(fraud_type: str, financial_ratios: dict) -> dict:
        """Modifies financial ratios based on the fraud archetype."""
        if fraud_type == "circular_trading":
            financial_ratios["ebitda_margin"] = max(0.01, financial_ratios["ebitda_margin"] - np.random.uniform(0.02, 0.05))
            financial_ratios["dscr"] = max(0.2, financial_ratios["dscr"] - np.random.uniform(0.1, 0.3))
            financial_ratios["icr"] = max(0.3, financial_ratios["icr"] - np.random.uniform(0.2, 0.4))
            financial_ratios["gst_discrepancy_pct"] += np.random.uniform(5.0, 15.0)
            financial_ratios["bank_divergence_pct"] += np.random.uniform(2.0, 10.0)
        elif fraud_type == "revenue_inflation":
            financial_ratios["revenue_growth_yoy"] += np.random.uniform(0.15, 0.35)
            financial_ratios["ebitda_margin"] = max(0.01, financial_ratios["ebitda_margin"] - np.random.uniform(0.02, 0.05)) # Margin deterioration
            financial_ratios["bank_divergence_pct"] += np.random.uniform(10.0, 25.0) # Ledger >> Bank credits
            financial_ratios["gst_discrepancy_pct"] += np.random.uniform(5.0, 20.0)
        elif fraud_type == "shell_company":
            financial_ratios["cibil_score"] = int(np.random.uniform(450, 650))
            financial_ratios["gst_discrepancy_pct"] += np.random.uniform(15.0, 30.0)
            financial_ratios["bank_divergence_pct"] += np.random.uniform(10.0, 25.0)
        elif fraud_type == "evergreening":
            financial_ratios["leverage"] = min(8.0, financial_ratios["leverage"] + np.random.uniform(0.5, 2.0))
            financial_ratios["dscr"] = max(0.2, financial_ratios["dscr"] - np.random.uniform(0.1, 0.3))
            financial_ratios["icr"] = max(0.3, financial_ratios["icr"] - np.random.uniform(0.2, 0.5))
            financial_ratios["bounce_rate"] += np.random.uniform(4.0, 10.0)
        elif fraud_type == "benami_siphoning":
            financial_ratios["promoter_holding_pct"] = max(5.0, financial_ratios["promoter_holding_pct"] - np.random.uniform(10.0, 25.0))
            financial_ratios["net_worth"] = max(financial_ratios.get("net_worth", 1_00_000) * np.random.uniform(0.6, 0.9), 50_000)
            financial_ratios["bank_divergence_pct"] += np.random.uniform(8.0, 20.0)
        elif fraud_type == "seasonal_manipulation":
            financial_ratios["revenue_growth_yoy"] += np.random.uniform(0.10, 0.25)
            financial_ratios["gst_discrepancy_pct"] += np.random.uniform(5.0, 15.0)
            
        return financial_ratios
