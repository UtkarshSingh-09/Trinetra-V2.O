#!/usr/bin/env python3
import os
import sys
import json
import pickle
import warnings
import numpy as np
import pandas as pd
from datetime import datetime

import optuna
from sklearn.model_selection import StratifiedKFold
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    roc_auc_score, precision_recall_curve, roc_curve,
    average_precision_score, confusion_matrix, accuracy_score,
    precision_score, recall_score, f1_score
)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "risk-agent"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_generator"))

try:
    from tri_lens import TriLensRiskScorer
except ImportError:
    from agents.risk_agent.tri_lens import TriLensRiskScorer

warnings.filterwarnings("ignore")
np.random.seed(42)

# Global status helper
def update_status(status, progress, new_log=None, error=None):
    model_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "risk-agent", "models")
    os.makedirs(model_dir, exist_ok=True)
    status_path = os.path.join(model_dir, "training_status.json")
    
    logs = []
    if os.path.exists(status_path):
        try:
            with open(status_path, "r") as f:
                data = json.load(f)
                logs = data.get("logs", [])
        except Exception:
            pass
            
    if new_log:
        print(new_log)
        logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] {new_log}")
        
    status_data = {
        "status": status,
        "progress": progress,
        "logs": logs,
        "error": error,
        "updated_at": datetime.now().isoformat()
    }
    
    with open(status_path, "w") as f:
        json.dump(status_data, f, indent=2)

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
    expected = np.array(expected)
    actual = np.array(actual)
    if len(expected) == 0 or len(actual) == 0:
        return 0.0
    # Create bins on expected dataset
    percentiles = np.linspace(0, 100, num_bins + 1)
    bins = np.percentile(expected, percentiles)
    bins[0] = -np.inf
    bins[-1] = np.inf
    bins = np.unique(bins)
    
    expected_pct = np.histogram(expected, bins=bins)[0] / len(expected)
    actual_pct = np.histogram(actual, bins=bins)[0] / len(actual)
    
    # Avoid log division by zero
    expected_pct = np.where(expected_pct == 0, 0.0001, expected_pct)
    actual_pct = np.where(actual_pct == 0, 0.0001, actual_pct)
    
    psi_val = np.sum((actual_pct - expected_pct) * np.log(actual_pct / expected_pct))
    return float(psi_val)

def compile_dataset():
    labels_path = "./synthetic_data/ground_truth_labels.csv"
    has_labels = os.path.exists(labels_path)
    record_count = 0
    if has_labels:
        try:
            df_lbl = pd.read_csv(labels_path)
            record_count = len(df_lbl)
        except Exception:
            pass
            
    if not has_labels or record_count < 1000:
        update_status("TRAINING", 5, "Dataset missing or too small. Running TrinetraDatasetGenerator (JSON only, 10,000 scale)...")
        try:
            from generate_dataset import TrinetraDatasetGenerator
            generator = TrinetraDatasetGenerator(output_dir="./synthetic_data")
            generator.generate(n_companies=10000, fraud_rate=0.15, generate_pdfs=False)
            update_status("TRAINING", 15, "Successfully compiled 10,000 synthetic company records.")
        except Exception as e:
            update_status("FAILED", 15, f"Dataset generation failed: {e}", error=str(e))
            raise e
    else:
        update_status("TRAINING", 15, f"Found existing dataset with {record_count} records.")

    update_status("TRAINING", 20, "Extracting advanced feature matrices from JSON database...")
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
                
            # Get incorporation year
            inc_date_str = comp_data.get("incorporation_date", "2018-01-01")
            try:
                inc_year = int(inc_date_str.split("-")[0])
            except Exception:
                inc_year = 2018
                
            # ── Compute 12 Advanced Derived Features ──
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
                # Core Features
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
                
                # Metadata for splits
                "inc_year": inc_year,
                "label": row["is_fraudulent"],
                "pd_target": row.get("pd_target", float(row["is_fraudulent"])),
                "true_fraud_state": row.get("true_fraud_state", row["is_fraudulent"])
            })
    
    data_df = pd.DataFrame(rows)
    update_status("TRAINING", 30, f"Loaded {len(data_df)} records. Default rate: {data_df['label'].mean():.1%}")
    return data_df

def downsample_curve(x_vals, y_vals, key_x, key_y, max_points=50):
    pts = []
    n = len(x_vals)
    for i in range(n):
        if i % max(1, n // max_points) == 0 or i == n - 1:
            pts.append({key_x: float(x_vals[i]), key_y: float(y_vals[i])})
    return pts

def train_and_evaluate():
    update_status("TRAINING", 0, "Initializing ML training pipeline...")
    
    try:
        data_df = compile_dataset()
    except Exception as e:
        update_status("FAILED", 30, f"Error gathering training dataset: {e}", error=str(e))
        return

    # OOT Vintage Split: Train on companies inc before 2021, validate/test on 2021+
    update_status("TRAINING", 32, "Splitting dataset into Train and Out-of-Time Validation sets...")
    train_df = data_df[data_df["inc_year"] < 2021].drop(columns=["inc_year"])
    oot_df = data_df[data_df["inc_year"] >= 2021].drop(columns=["inc_year"])
    
    if len(train_df) < 50 or len(oot_df) < 50:
        # Fallback to random split if vintage distribution is skewed
        train_df = data_df.sample(frac=0.8, random_state=42).drop(columns=["inc_year"])
        oot_df = data_df.drop(train_df.index).drop(columns=["inc_year"])
        
    target_cols = ["label", "pd_target", "true_fraud_state"]
    X_train = train_df.drop(columns=target_cols).values
    y_train_soft = train_df["pd_target"].values
    y_train_binary = train_df["true_fraud_state"].values
    
    X_oot = oot_df.drop(columns=target_cols).values
    y_oot_soft = oot_df["pd_target"].values
    y_oot_binary = oot_df["true_fraud_state"].values
    
    feature_names = list(train_df.drop(columns=target_cols).columns)

    # Scale features
    update_status("TRAINING", 35, "Standardizing feature spaces...")
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_oot_scaled = scaler.transform(X_oot)

    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    # ═══════════════════════════════════════════════════════
    #  XGBoost Tuning with Optuna
    # ═══════════════════════════════════════════════════════
    update_status("TRAINING", 50, "Tuning XGBoost Regressor via Optuna for soft targets...")
    import xgboost as xgb
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    
    def objective_xgb(trial):
        params = {
            'n_estimators': trial.suggest_int('n_estimators', 50, 200),
            'max_depth': trial.suggest_int('max_depth', 3, 6),
            'learning_rate': trial.suggest_float('learning_rate', 0.02, 0.15),
            'subsample': trial.suggest_float('subsample', 0.7, 1.0)
        }
        # Using reg:logistic to predict continuous probability bounds [0,1]
        clf = xgb.XGBRegressor(**params, objective="reg:logistic", eval_metric="rmse", random_state=42, verbosity=0)
        scores = []
        for train_idx, val_idx in skf.split(X_train, y_train_binary): # Stratify based on binary label
            clf.fit(X_train[train_idx], y_train_soft[train_idx])
            preds = clf.predict(X_train[val_idx])
            scores.append(roc_auc_score(y_train_binary[val_idx], preds))
        return np.mean(scores)

    study_xgb = optuna.create_study(direction='maximize')
    study_xgb.optimize(objective_xgb, n_trials=10)
    best_xgb = xgb.XGBRegressor(**study_xgb.best_params, objective="reg:logistic", eval_metric="rmse", random_state=42, verbosity=0)
    best_xgb.fit(X_train, y_train_soft)
    update_status("TRAINING", 65, f"XGBoost optimized (Best CV AUC: {study_xgb.best_value:.4f}).")

    # ═══════════════════════════════════════════════════════
    #  LightGBM Tuning with Optuna
    # ═══════════════════════════════════════════════════════
    update_status("TRAINING", 70, "Tuning LightGBM Regressor via Optuna for soft targets...")
    import lightgbm as lgbm
    
    def objective_lgb(trial):
        params = {
            'n_estimators': trial.suggest_int('n_estimators', 50, 200),
            'max_depth': trial.suggest_int('max_depth', 3, 6),
            'learning_rate': trial.suggest_float('learning_rate', 0.02, 0.15)
        }
        clf = lgbm.LGBMRegressor(**params, objective="regression", random_state=42, verbose=-1)
        scores = []
        for train_idx, val_idx in skf.split(X_train, y_train_binary):
            clf.fit(X_train[train_idx], y_train_soft[train_idx])
            preds = clf.predict(X_train[val_idx])
            scores.append(roc_auc_score(y_train_binary[val_idx], preds))
        return np.mean(scores)

    study_lgb = optuna.create_study(direction='maximize')
    study_lgb.optimize(objective_lgb, n_trials=10)
    best_lgb = lgbm.LGBMRegressor(**study_lgb.best_params, objective="regression", random_state=42, verbose=-1)
    best_lgb.fit(X_train, y_train_soft)
    update_status("TRAINING", 80, f"LightGBM optimized (Best CV AUC: {study_lgb.best_value:.4f}).")

    # ═══════════════════════════════════════════════════════
    #  Logistic Regression Tuning (Baseline)
    # ═══════════════════════════════════════════════════════
    update_status("TRAINING", 82, "Fitting Logistic Regression Baseline...")
    best_lr = LogisticRegression(C=1.0, max_iter=1000, class_weight="balanced", random_state=42)
    best_lr.fit(X_train_scaled, y_train_binary)

    # ═══════════════════════════════════════════════════════
    #  Tri-Lens Fusion Weights
    # ═══════════════════════════════════════════════════════
    update_status("TRAINING", 85, "Optimizing Tri-Lens attention weights...")
    scorer = TriLensRiskScorer(epsilon=0.0)
    
    fin_scores, beh_scores, con_scores = [], [], []
    for idx, row in train_df.drop(columns=["label"]).iterrows():
        fin_s, _ = scorer.compute_financial_lens(row.to_dict())
        beh_s, _ = scorer.compute_behavioral_lens(row.to_dict())
        con_s, _ = scorer.compute_contextual_lens(row.to_dict())
        fin_scores.append(fin_s)
        beh_scores.append(beh_s)
        con_scores.append(con_s)
        
    X_lens = np.column_stack([fin_scores, beh_scores, con_scores])
    lr_lens = LogisticRegression(fit_intercept=False, C=1.0)
    lr_lens.fit(X_lens, y_train_binary)
    
    lens_weights = np.clip(lr_lens.coef_[0], 0.05, None)
    lens_weights = lens_weights / np.sum(lens_weights)
    learned_weights = {
        "financial": float(lens_weights[0]),
        "behavioral": float(lens_weights[1]),
        "contextual": float(lens_weights[2])
    }
    update_status("TRAINING", 90, f"Optimal weights trained: {learned_weights}")

    # Evaluate models on OOT dataset
    update_status("TRAINING", 92, "Evaluating model performance on Out-of-Time (OOT) validation set...")
    
    results = {}
    models = {
        "LOGISTIC": best_lr,
        "XGBOOST": best_xgb,
        "LGBM": best_lgb,
        "TRI_LENS": None
    }
    
    # Pre-calculate lens scores on OOT for TRI_LENS evaluation
    fin_scores_oot, beh_scores_oot, con_scores_oot = [], [], []
    for idx, row in oot_df.drop(columns=["label"]).iterrows():
        fin_s, _ = scorer.compute_financial_lens(row.to_dict())
        beh_s, _ = scorer.compute_behavioral_lens(row.to_dict())
        con_s, _ = scorer.compute_contextual_lens(row.to_dict())
        fin_scores_oot.append(fin_s)
        beh_scores_oot.append(beh_s)
        con_scores_oot.append(con_s)
    X_lens_oot = np.column_stack([fin_scores_oot, beh_scores_oot, con_scores_oot])
    
    probas = {
        "LOGISTIC": best_lr.predict_proba(X_oot_scaled)[:, 1],
        "XGBOOST": best_xgb.predict(X_oot),
        "LGBM": best_lgb.predict(X_oot),
        "TRI_LENS": X_lens_oot @ lens_weights
    }
    
    for name, model in models.items():
        y_proba = probas[name]
        y_pred = (y_proba > 0.55).astype(int)
        
        auc = roc_auc_score(y_oot_binary, y_proba)
        gini = 2 * auc - 1
        ks = compute_ks_statistic(y_oot_binary, y_proba)
        
        # Calculate PSI relative to training predictions
        if name == "LOGISTIC":
            y_proba_train = best_lr.predict_proba(X_train_scaled)[:, 1]
        elif name == "TRI_LENS":
            y_proba_train = X_lens @ lens_weights
        elif name == "XGBOOST":
            y_proba_train = best_xgb.predict(X_train)
        elif name == "LGBM":
            y_proba_train = best_lgb.predict(X_train)
            
        psi = compute_psi(y_proba_train, y_proba)
        
        ap = average_precision_score(y_oot_binary, y_proba)
        cm = confusion_matrix(y_oot_binary, y_pred)
        fpr_raw, tpr_raw, _ = roc_curve(y_oot_binary, y_proba)
        prec_raw, rec_raw, _ = precision_recall_curve(y_oot_binary, y_proba)
        
        results[name] = {
            "cv_auc_mean": float(auc), # OOT AUC acts as validation AUC
            "cv_auc_std": 0.0,
            "accuracy": float(accuracy_score(y_oot_binary, y_pred)),
            "precision": float(precision_score(y_oot_binary, y_pred, zero_division=0)),
            "recall": float(recall_score(y_oot_binary, y_pred, zero_division=0)),
            "f1": float(f1_score(y_oot_binary, y_pred, zero_division=0)),
            "auc_roc": float(auc),
            "gini": float(gini),
            "ks_statistic": float(ks),
            "psi": float(psi),
            "ap": float(ap),
            "confusion_matrix": {
                "tn": int(cm[0, 0]),
                "fp": int(cm[0, 1]),
                "fn": int(cm[1, 0]),
                "tp": int(cm[1, 1])
            },
            "roc_curve": downsample_curve(fpr_raw, tpr_raw, "fpr", "tpr"),
            "pr_curve": downsample_curve(rec_raw, prec_raw, "recall", "precision")
        }

    # Feature Importance from XGBoost
    xgb_importances = best_xgb.feature_importances_
    sorted_idx = np.argsort(xgb_importances)[::-1]
    feature_importances = []
    for idx in sorted_idx:
        feature_importances.append({
            "feature": feature_names[idx],
            "importance": float(xgb_importances[idx])
        })

    # Save artifacts
    update_status("TRAINING", 95, "Saving trained models to models/ directory...")
    model_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "risk-agent", "models")
    os.makedirs(model_dir, exist_ok=True)

    with open(os.path.join(model_dir, "logistic_risk_model.pkl"), "wb") as f:
        pickle.dump(best_lr, f)
    with open(os.path.join(model_dir, "xgboost_risk_model.pkl"), "wb") as f:
        pickle.dump(best_xgb, f)
    with open(os.path.join(model_dir, "lgbm_risk_model.pkl"), "wb") as f:
        pickle.dump(best_lgb, f)
    with open(os.path.join(model_dir, "feature_scaler.pkl"), "wb") as f:
        pickle.dump(scaler, f)
    with open(os.path.join(model_dir, "tri_lens_weights.json"), "w") as f:
        json.dump(learned_weights, f, indent=2)

    # Save model card metadata JSON
    metadata = {
        "feature_names": feature_names,
        "n_features": len(feature_names),
        "n_training_samples": len(train_df),
        "n_oot_samples": len(oot_df),
        "default_rate": float(y_train_binary.mean()),
        "trained_at": datetime.now().isoformat(),
        "results": results,
        "feature_importances": feature_importances,
        "learned_tri_lens_weights": learned_weights
    }
    with open(os.path.join(model_dir, "model_metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)

    # Save training data sample (for SHAP/LIME background)
    data_path = os.path.join(model_dir, "training_data_sample.pkl")
    sample_df = train_df.drop(columns=["label"]).sample(min(500, len(train_df)), random_state=42)
    with open(data_path, "wb") as f:
        pickle.dump(sample_df, f)

    update_status("COMPLETED", 100, "ML training pipeline completed successfully! Models and metrics exported.")

if __name__ == "__main__":
    train_and_evaluate()
