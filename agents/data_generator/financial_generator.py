import random
import numpy as np
import scipy.stats as stats
import math
from sector_profiles import SECTOR_PROFILES
from fraud_simulator import FraudSimulator
from macro_simulator import MacroEconomicSimulator

class FinancialProfileGenerator:
    """
    Generates correlated financial profiles for companies based on:
    - Sector specific distributions (SECTOR_PROFILES)
    - Target turnover class & value (Micro, Small, Medium)
    - Macro-economic regimes (via MacroEconomicSimulator)
    - Fraud signatures (via FraudSimulator)
    
    Ensures mathematical coherence between financial ratios and absolute values.
    """

    def __init__(self, regime: str = "neutral"):
        self.macro_sim = MacroEconomicSimulator(regime=regime)

    def generate(self, company_profile: dict) -> dict:
        """
        Generates a complete 3-year financial profile for the given company.
        """
        is_fraud = company_profile.get("is_fraudulent", False)
        fraud_type = company_profile.get("fraud_type", None)
        sector = company_profile.get("industry_sector", "IT Services")
        target_turnover = company_profile.get("target_turnover", 1_00_00_000)
        
        # Sector Profile
        prof = SECTOR_PROFILES.get(sector, SECTOR_PROFILES["IT Services"])

        # Determine years in business
        inc_date_str = company_profile.get("incorporation_date", "2018-01-01")
        try:
            inc_year = int(inc_date_str.split("-")[0])
            years_in_business = max(1, 2026 - inc_year)
        except Exception:
            years_in_business = random.randint(3, 15)

        # ── 1. Correlation Matrix for Gaussian Copula ──
        # Order: 0: DSCR, 1: ICR, 2: Leverage, 3: Current Ratio, 4: EBITDA Margin
        R = np.array([
            [1.0, 0.8, -0.7, 0.4, 0.5],   # DSCR
            [0.8, 1.0, -0.6, 0.3, 0.6],   # ICR
            [-0.7, -0.6, 1.0, -0.5, -0.4], # Leverage
            [0.4, 0.3, -0.5, 1.0, 0.3],   # Current Ratio
            [0.5, 0.6, -0.4, 0.3, 1.0]    # EBITDA Margin
        ])
        
        # Sample correlated standard normals
        z = np.random.multivariate_normal(mean=[0, 0, 0, 0, 0], cov=R)
        
        # Convert to uniform marginals via standard normal CDF
        u = [0.5 * (1 + math.erf(zi / math.sqrt(2))) for zi in z]
        
        # ── 2. Apply Marginal Distributions (Normal or Fat-tailed Student-t for Fraud) ──
        ratios = {}
        keys = ["dscr", "icr", "leverage", "current_ratio", "ebitda_margin"]
        
        for idx, key in enumerate(keys):
            p = prof[key]
            mean = p["mean"]
            std = p["std"]
            
            # Apply shifts if fraudulent
            if is_fraud:
                mean += p.get("fraud_shift", 0)
                # Map to fat-tailed Student-t with 5 degrees of freedom
                t_val = stats.t.ppf(u[idx], df=5)
                val = mean + std * t_val
            else:
                # Map to normal
                val = mean + std * z[idx]
                
            ratios[key] = val

        # Add revenue growth
        ratios["revenue_growth_yoy"] = np.random.normal(0.12, 0.06)

        # ── 3. Latent Behavioral Variables ──
        compliance_latent = np.random.normal(-1.2 if is_fraud else 0.6, 0.4)
        mgmt_latent = np.random.normal(-1.0 if is_fraud else 0.5, 0.5)

        cibil_score = int(np.clip(720 + 60 * mgmt_latent + np.random.normal(0, 25), 300, 900))
        promoter_holding_pct = float(np.clip(65.0 + 8.0 * mgmt_latent + np.random.normal(0, 5.0), 5.0, 99.0))
        
        is_sophisticated = company_profile.get("is_sophisticated", False)
        
        # GSTR & Bank divergence
        if is_fraud:
            if is_sophisticated:
                # Sophisticated fraudsters have metrics much closer to normal to avoid detection
                gst_discrepancy_pct = float(np.clip(8.0 + np.random.exponential(6.0), 2.0, 25.0))
                bank_divergence_pct = float(np.clip(6.0 + np.random.exponential(5.0), 2.0, 20.0))
                bounce_rate = float(np.clip(3.0 - 1.0 * mgmt_latent + np.random.exponential(2.0), 0.0, 12.0))
            else:
                # Unsophisticated fraudsters have blatant discrepancies
                gst_discrepancy_pct = float(np.clip(15.0 + np.random.exponential(10.0), 8.0, 50.0))
                bank_divergence_pct = float(np.clip(10.0 + np.random.exponential(8.0), 5.0, 45.0))
                bounce_rate = float(np.clip(5.0 - 1.5 * mgmt_latent + np.random.exponential(3.0), 2.0, 20.0))
        else:
            gst_discrepancy_pct = float(np.clip(4.0 - 2.0 * compliance_latent + np.random.exponential(2.0), 0.0, 18.0))
            bank_divergence_pct = float(np.clip(3.5 - compliance_latent + np.random.exponential(1.5), 0.0, 15.0))
            bounce_rate = float(np.clip(2.0 - 1.2 * mgmt_latent + np.random.exponential(1.0), 0.0, 10.0))
            
        web_sentiment_avg = float(np.clip(0.3 + 0.2 * mgmt_latent + np.random.normal(0, 0.15), -1.0, 1.0))
        ltv_ratio = float(np.clip(0.65 - 0.08 * compliance_latent + np.random.normal(0, 0.08), 0.1, 2.0))

        # Add behavioral variables to ratios dict
        ratios["cibil_score"] = cibil_score
        ratios["promoter_holding_pct"] = promoter_holding_pct
        ratios["gst_discrepancy_pct"] = gst_discrepancy_pct
        ratios["bank_divergence_pct"] = bank_divergence_pct
        ratios["bounce_rate"] = bounce_rate
        ratios["web_sentiment_avg"] = web_sentiment_avg
        ratios["ltv_ratio"] = ltv_ratio

        # Apply Macro Adjustments
        ratios = self.macro_sim.apply_macro_adjustments(sector, ratios)

        # Apply Fraud Archetype Specific Shifts
        if is_fraud and fraud_type:
            ratios = FraudSimulator.apply_financial_shifts(fraud_type, ratios)

        # Clip values to realistic bounds
        dscr = np.clip(ratios["dscr"], 0.1, 8.0)
        icr = np.clip(ratios["icr"], 0.1, 25.0)
        leverage = np.clip(ratios["leverage"], 0.05, 12.0)
        current_ratio = np.clip(ratios["current_ratio"], 0.1, 6.0)
        revenue_growth_yoy = np.clip(ratios["revenue_growth_yoy"], -0.6, 1.2)
        ebitda_margin = np.clip(ratios["ebitda_margin"], 0.005, 0.50)
        cibil_score = ratios["cibil_score"]
        promoter_holding_pct = ratios["promoter_holding_pct"]
        gst_discrepancy_pct = ratios["gst_discrepancy_pct"]
        bank_divergence_pct = ratios["bank_divergence_pct"]
        bounce_rate = ratios["bounce_rate"]
        web_sentiment_avg = ratios["web_sentiment_avg"]
        ltv_ratio = ratios["ltv_ratio"]

        # ── 4. Absolute Financial Numbers (3 Years of Data) ──
        # Year 3 (Current Year)
        rev_y3 = target_turnover
        # Year 2
        rev_y2 = rev_y3 / (1 + revenue_growth_yoy)
        # Year 1
        growth_y2 = np.clip(revenue_growth_yoy + np.random.normal(-0.04, 0.04), -0.5, 1.0)
        rev_y1 = rev_y2 / (1 + growth_y2)
        
        revenue_annual = [rev_y1, rev_y2, rev_y3]
        
        # EBITDA
        ebitda_y3 = rev_y3 * ebitda_margin
        ebitda_y2 = rev_y2 * np.clip(ebitda_margin + np.random.normal(-0.015, 0.015), 0.005, 0.50)
        ebitda_y1 = rev_y1 * np.clip(ebitda_margin + np.random.normal(-0.03, 0.015), 0.005, 0.50)
        ebitda_annual = [ebitda_y1, ebitda_y2, ebitda_y3]
        
        # Debt & Equity values matching leverage
        net_worth = rev_y3 * 0.4
        total_debt = net_worth * leverage
        
        # Interest expense based on debt and macro simulated repo rate
        interest_rate = self.macro_sim.get_interest_rate("fy26")
        interest_expense = total_debt * interest_rate
        
        # Ensure ICR coherence
        if interest_expense > 0:
            icr = ebitda_y3 / interest_expense
        else:
            icr = 99.0
            
        # Depreciation & Net Profit
        depreciation = net_worth * 0.05
        ebt_y3 = ebitda_y3 - interest_expense - depreciation
        tax_y3 = max(0.0, ebt_y3 * 0.25)
        np_y3 = ebt_y3 - tax_y3
        
        ebt_y2 = ebitda_y2 - (total_debt * 0.9 * self.macro_sim.get_interest_rate("fy25")) - depreciation
        tax_y2 = max(0.0, ebt_y2 * 0.25)
        np_y2 = ebt_y2 - tax_y2
        
        ebt_y1 = ebitda_y1 - (total_debt * 0.8 * self.macro_sim.get_interest_rate("fy24")) - depreciation
        tax_y1 = max(0.0, ebt_y1 * 0.25)
        np_y1 = ebt_y1 - tax_y1
        
        net_profit_annual = [np_y1, np_y2, np_y3]
        
        # Short term assets & liabilities
        current_liabilities = total_debt * 0.4
        current_assets = current_liabilities * current_ratio
        share_capital = net_worth * 0.3
        
        return {
            "dscr": float(np.round(dscr, 4)),
            "icr": float(np.round(icr, 4)),
            "leverage": float(np.round(leverage, 4)),
            "current_ratio": float(np.round(current_ratio, 4)),
            "revenue_growth_yoy": float(np.round(revenue_growth_yoy, 4)),
            "ebitda_margin": float(np.round(ebitda_margin, 4)),
            "cibil_score": int(cibil_score),
            "promoter_holding_pct": float(np.round(promoter_holding_pct, 2)),
            "gst_discrepancy_pct": float(np.round(gst_discrepancy_pct, 2)),
            "bank_divergence_pct": float(np.round(bank_divergence_pct, 2)),
            "web_sentiment_avg": float(np.round(web_sentiment_avg, 4)),
            "bounce_rate": float(np.round(bounce_rate, 2)),
            "years_in_business": int(years_in_business),
            "ltv_ratio": float(np.round(ltv_ratio, 4)),
            
            # Absolute financial values
            "revenue_annual": [float(v) for v in revenue_annual],
            "ebitda_annual": [float(v) for v in ebitda_annual],
            "net_profit_annual": [float(v) for v in net_profit_annual],
            "total_debt": float(total_debt),
            "net_worth": float(net_worth),
            "current_assets": float(current_assets),
            "current_liabilities": float(current_liabilities),
            "share_capital": float(share_capital),
            "interest_expense": float(interest_expense),
            "interest_rate": float(interest_rate)
        }
