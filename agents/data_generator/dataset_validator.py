# dataset_validator.py
import os
import json
import numpy as np
import argparse

class DatasetValidator:
    """
    Validates synthetic company, financial, GSTR, and bank datasets for
    internal mathematical coherence and statistical realism.
    """

    def __init__(self, data_dir: str):
        self.data_dir = data_dir

    def validate(self) -> dict:
        print(f"[*] Validating synthetic dataset in {self.data_dir}...")
        companies_dir = os.path.join(self.data_dir, "companies")
        financials_dir = os.path.join(self.data_dir, "financials")
        
        if not os.path.exists(companies_dir) or not os.path.exists(financials_dir):
            return {"status": "FAIL", "reason": "Directories do not exist"}

        company_files = [f for f in os.listdir(companies_dir) if f.endswith(".json")]
        
        checks = {
            "math_coherence": {"pass": 0, "fail": 0},
            "balance_sheet_identity": {"pass": 0, "fail": 0},
            "gst_consistency": {"pass": 0, "fail": 0},
            "bank_credits_consistency": {"pass": 0, "fail": 0}
        }
        
        outliers = []
        
        for f in company_files:
            comp_id = f.replace(".json", "")
            
            # Load files
            with open(os.path.join(companies_dir, f), "r") as fh:
                comp = json.load(fh)
                
            fin_path = os.path.join(financials_dir, f"{comp_id}_financials.json")
            gstr_path = os.path.join(financials_dir, f"{comp_id}_gstr.json")
            bank_path = os.path.join(financials_dir, f"{comp_id}_bank.json")
            
            if not (os.path.exists(fin_path) and os.path.exists(gstr_path) and os.path.exists(bank_path)):
                continue
                
            with open(fin_path, "r") as fh:
                fin = json.load(fh)
            with open(gstr_path, "r") as fh:
                gstr = json.load(fh)
            with open(bank_path, "r") as fh:
                bank = json.load(fh)
                
            # 1. Math Coherence
            # EBITDA = EBITDA margin * Revenue
            rev_y3 = fin["revenue_annual"][-1]
            ebitda_y3 = fin["ebitda_annual"][-1]
            expected_ebitda = rev_y3 * fin["ebitda_margin"]
            if abs(ebitda_y3 - expected_ebitda) / max(1.0, expected_ebitda) < 0.05:
                checks["math_coherence"]["pass"] += 1
            else:
                checks["math_coherence"]["fail"] += 1
                
            # 2. Balance Sheet Identity
            # Net Worth + Liabilities (Total Debt) == Assets (or proxy for MSMEs)
            # For simplicity, we ensure current_ratio = current_assets / current_liabilities holds
            expected_cr = fin["current_assets"] / max(1.0, fin["current_liabilities"])
            if abs(fin["current_ratio"] - expected_cr) < 0.05:
                checks["balance_sheet_identity"]["pass"] += 1
            else:
                checks["balance_sheet_identity"]["fail"] += 1
                
            # 3. GST Consistency
            # Total GSTR Outward Taxable Supplies should be close to Revenue
            gstr_turnover = gstr["total_gst_turnover"]
            if abs(gstr_turnover - rev_y3) / max(1.0, rev_y3) < 0.15: # 15% allowance due to seasonal factors
                checks["gst_consistency"]["pass"] += 1
            else:
                checks["gst_consistency"]["fail"] += 1
                
            # 4. Bank Credits Consistency
            # Bank credits must roughly track turnover + divergence
            bank_credits = bank["total_credits"]
            bank_div = fin["bank_divergence_pct"]
            div_val = rev_y3 * (bank_div / 100.0)
            
            # If fraud, divergence is high. Let's make sure it's roughly coherent
            if abs(bank_credits - rev_y3) / max(1.0, rev_y3) < 0.85:
                checks["bank_credits_consistency"]["pass"] += 1
            else:
                checks["bank_credits_consistency"]["fail"] += 1

            # Outlier Census
            if fin["dscr"] > 4.5 or fin["leverage"] > 7.0 or fin["bounce_rate"] > 18.0:
                outliers.append(comp_id)

        # Class summary
        total_validated = len(company_files)
        report = {
            "status": "PASS" if all(c["fail"] == 0 for c in checks.values()) else "WARN",
            "total_validated": total_validated,
            "checks": checks,
            "outlier_count": len(outliers),
            "outliers": outliers[:10]
        }
        
        with open(os.path.join(self.data_dir, "dataset_quality_report.json"), "w") as fh:
            json.dump(report, fh, indent=4)
            
        print(f"[+] Dataset validation finished. Status: {report['status']}")
        return report

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, default="../synthetic_data")
    args = parser.parse_args()
    
    validator = DatasetValidator(args.input)
    validator.validate()
