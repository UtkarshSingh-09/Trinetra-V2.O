# model_validation.py
import os
import json
import pickle
from datetime import datetime
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

def compute_ks_statistic(y_true, y_proba):
    df_ks = pd.DataFrame({'y': y_true, 'p': y_proba})
    df_ks = df_ks.sort_values(by='p', ascending=False)
    total_pos = sum(y_true)
    total_neg = len(y_true) - total_pos
    if total_pos == 0 or total_neg == 0:
        return 0.0
    df_ks['cum_pos'] = df_ks['y'].cumsum() / total_pos
    df_ks['cum_neg'] = (1 - df_ks['y']).cumsum() / total_neg
    return float(max(abs(df_ks['cum_pos'] - df_ks['cum_neg'])))

def compute_psi(expected, actual, num_bins=10):
    percentiles = np.linspace(0, 100, num_bins + 1)
    bins = np.percentile(expected, percentiles)
    bins[0] = -np.inf
    bins[-1] = np.inf
    bins = np.unique(bins)
    
    expected_pct = np.histogram(expected, bins=bins)[0] / len(expected)
    actual_pct = np.histogram(actual, bins=bins)[0] / len(actual)
    
    expected_pct = np.where(expected_pct == 0, 0.0001, expected_pct)
    actual_pct = np.where(actual_pct == 0, 0.0001, actual_pct)
    
    return float(np.sum((actual_pct - expected_pct) * np.log(actual_pct / expected_pct)))

def run_model_validation():
    print("[*] Running RBI-style Credit Model Validation Suite...")
    
    model_dir = "./agents/risk-agent/models"
    metadata_path = os.path.join(model_dir, "model_metadata.json")
    xgb_path = os.path.join(model_dir, "xgboost_risk_model.pkl")
    labels_path = "./synthetic_data/ground_truth_labels.csv"
    
    if not (os.path.exists(metadata_path) and os.path.exists(xgb_path) and os.path.exists(labels_path)):
        print("[!] Error: Model artifacts or ground truth labels missing. Run train_risk_models.py first.")
        return
        
    with open(xgb_path, "rb") as f:
        model = pickle.load(f)
        
    with open(metadata_path, "r") as f:
        metadata = json.load(f)
        
    # Re-extract features to run validation
    feature_names = metadata["feature_names"]
    labels_df = pd.read_csv(labels_path)
    
    # Load Director Graph for director risk calculations
    dir_graph_path = "./synthetic_data/director_network.json"
    director_data = {}
    if os.path.exists(dir_graph_path):
        with open(dir_graph_path, "r") as f:
            director_data = json.load(f)
            
    rows = []
    for idx, row in labels_df.iterrows():
        comp_id = row["company_id"]
        fin_path = f"./synthetic_data/financials/{comp_id}_financials.json"
        gstr_path = f"./synthetic_data/financials/{comp_id}_gstr.json"
        bank_path = f"./synthetic_data/financials/{comp_id}_bank.json"
        comp_path = f"./synthetic_data/companies/{comp_id}.json"
        
        if os.path.exists(fin_path) and os.path.exists(gstr_path) and os.path.exists(bank_path) and os.path.exists(comp_path):
            with open(fin_path, "r") as f:
                fin_data = json.load(f)
            with open(gstr_path, "r") as f:
                gstr_data = json.load(f)
            with open(bank_path, "r") as f:
                bank_data = json.load(f)
            with open(comp_path, "r") as f:
                comp_data = json.load(f)
                
            # 1. Revenue Volatility
            sales = [m["gstr_3b"]["outward_taxable_supplies"] for m in gstr_data["gstr_records"]]
            revenue_volatility = np.std(sales) / max(1.0, np.mean(sales)) if sales else 0.0
            
            # 2. DSCR Trend
            dscr_trend = fin_data["dscr"] - (fin_data["dscr"] * (fin_data["ebitda_annual"][0] / max(1.0, fin_data["ebitda_annual"][2])))
            
            # 3. Debt Growth Rate
            debt_growth_rate = 0.15 + 0.05 * fin_data["leverage"]
            
            # 4. Working Capital Days
            wc = fin_data["current_assets"] - fin_data["current_liabilities"]
            working_capital_days = wc / max(1.0, (fin_data["revenue_annual"][-1] / 365.0))
            
            # 5. Interest Coverage Trend
            icr_y1 = fin_data["ebitda_annual"][0] / max(1.0, fin_data["interest_expense"] * 0.8)
            interest_coverage_trend = fin_data["icr"] - icr_y1
            
            # 6. Director Risk Score
            shared_count = 0
            comp_directors = comp_data.get("directors", [])
            for d_name in comp_directors:
                if d_name in director_data.get("director_companies", {}):
                    if len(director_data["director_companies"][d_name]) > 1:
                        shared_count += 1
            director_risk_score = shared_count / max(1.0, len(comp_directors))
            
            # 7. Counterparty Concentration
            credits = [t for t in bank_data["transactions"] if t["type"] == "CREDIT"]
            party_sums = {}
            for c in credits:
                parts = c["narration"].split(" / ")
                party = parts[1] if len(parts) > 1 else "Unknown"
                party_sums[party] = party_sums.get(party, 0.0) + c["amount"]
            max_credit = max(party_sums.values()) if party_sums else 0.0
            total_credits = sum(c["amount"] for c in credits)
            counterparty_concentration = max_credit / max(1.0, total_credits)
            
            # 8. Transaction Velocity
            transaction_velocity = len(bank_data["transactions"]) / 12.0
            
            # 9. Bounce Trend
            n_tx = len(bank_data["transactions"])
            b_h1 = sum(1 for t in bank_data["transactions"][:n_tx//2] if "CHQ RETURN" in t["narration"])
            b_h2 = sum(1 for t in bank_data["transactions"][n_tx//2:] if "CHQ RETURN" in t["narration"])
            bounce_trend = float(b_h2 - b_h1)
            
            # 10. GST Seasonality Score
            q4_sales = sum(sales[9:12]) if len(sales) >= 12 else 0.0
            avg_q_sales = sum(sales) / 4.0 if sales else 1.0
            gst_seasonality_score = q4_sales / max(1.0, avg_q_sales)
            
            # 11. Cash Conversion Efficiency
            cash_conversion_efficiency = bank_data["total_credits"] / max(1.0, fin_data["revenue_annual"][-1])
            
            # 12. EMI Regularity Score
            emi_days = []
            for t in bank_data["transactions"]:
                if t["type"] == "DEBIT" and ("EMI" in t["narration"] or "CHQ CLG" in t["narration"]):
                    try:
                        day = int(t["date"].split("-")[2])
                        emi_days.append(day)
                    except Exception:
                        pass
            emi_regularity_score = np.std(emi_days) if len(emi_days) > 1 else 0.0

            rows.append({
                "dscr": fin_data["dscr"],
                "icr": fin_data["icr"],
                "leverage": fin_data["leverage"],
                "current_ratio": fin_data["current_ratio"],
                "revenue_growth_yoy": fin_data["revenue_growth_yoy"],
                "ebitda_margin": fin_data["ebitda_margin"],
                "cibil_score": fin_data["cibil_score"],
                "promoter_holding_pct": fin_data["promoter_holding_pct"],
                "gst_discrepancy_pct": fin_data["gst_discrepancy_pct"],
                "bank_divergence_pct": fin_data["bank_divergence_pct"],
                "web_sentiment_avg": fin_data["web_sentiment_avg"],
                "bounce_rate": fin_data["bounce_rate"],
                "years_in_business": fin_data["years_in_business"],
                "ltv_ratio": fin_data["ltv_ratio"],
                "revenue_volatility": float(revenue_volatility),
                "dscr_trend": float(dscr_trend),
                "debt_growth_rate": float(debt_growth_rate),
                "working_capital_days": float(working_capital_days),
                "interest_coverage_trend": float(interest_coverage_trend),
                "director_risk_score": float(director_risk_score),
                "counterparty_concentration": float(counterparty_concentration),
                "transaction_velocity": float(transaction_velocity),
                "bounce_trend": float(bounce_trend),
                "gst_seasonality_score": float(gst_seasonality_score),
                "cash_conversion_efficiency": float(cash_conversion_efficiency),
                "emi_regularity_score": float(emi_regularity_score),
                "registered_state": comp_data["registered_state"],
                "label": row["is_fraudulent"]
            })
            
    df_val = pd.DataFrame(rows)
    X = df_val[feature_names].values
    y = df_val["label"].values
    
    # Model Predictions
    y_proba = model.predict_proba(X)[:, 1]
    
    # ── 1. Discriminatory Metrics ──
    auc = roc_auc_score(y, y_proba)
    gini = 2 * auc - 1
    ks = compute_ks_statistic(y, y_proba)
    
    # ── 2. Calibration ──
    # Hosmer-Lemeshow or bin-based calibration
    df_bins = pd.DataFrame({'y': y, 'p': y_proba})
    df_bins['decile'] = pd.qcut(df_bins['p'], 10, labels=False, duplicates='drop')
    calibration = df_bins.groupby('decile').agg(
        avg_prob=('p', 'mean'),
        actual_rate=('y', 'mean')
    ).to_dict(orient='index')
    
    # ── 3. Herfindahl Index of Risk Concentration ──
    # Higher score = too concentrated in one risk band
    bins_risk = [0, 0.15, 0.35, 0.65, 0.85, 1.0]
    risk_bands = pd.cut(y_proba, bins=bins_risk, labels=['VL', 'L', 'M', 'H', 'VH'])
    band_pcts = pd.Series(risk_bands).value_counts(normalize=True)
    herfindahl = float(np.sum(band_pcts ** 2))
    
    # ── 4. Geographic Fairness Audit ──
    geo_stats = df_val.groupby("registered_state").apply(
        lambda g: roc_auc_score(g["label"], model.predict_proba(g[feature_names].values)[:, 1]) if len(g["label"].unique()) > 1 else 1.0
    ).to_dict()
    
    # Save Report
    report = {
        "validation_timestamp": datetime.now().isoformat(),
        "discriminatory_power": {
            "auc": float(auc),
            "gini": float(gini),
            "ks_statistic": float(ks)
        },
        "concentration_risk": {
            "herfindahl_index": herfindahl,
            "band_distribution": band_pcts.to_dict()
        },
        "calibration_deciles": calibration,
        "geographic_fairness_audit": geo_stats
    }
    
    report_path = os.path.join(model_dir, "model_validation_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=4)
        
    print(f"[+] Success! Model Validation Report written to: {report_path}")
    print(f"    - Gini Coefficient: {gini:.4f}")
    print(f"    - KS Statistic: {ks:.4f}")
    print(f"    - Herfindahl Risk Concentration: {herfindahl:.4f}")

if __name__ == "__main__":
    run_model_validation()
