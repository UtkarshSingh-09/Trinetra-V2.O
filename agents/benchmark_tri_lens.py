import os
import json
import csv
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score

import sys
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "risk-agent"))
from tri_lens import TriLensRiskScorer

def load_data():
    labels_path = "./synthetic_data/ground_truth_labels.csv"
    if not os.path.exists(labels_path):
        raise FileNotFoundError("Synthetic dataset ground_truth_labels.csv not found! Run generate_dataset.py first.")
        
    labels_df = pd.read_csv(labels_path)
    
    rows = []
    for idx, row in labels_df.iterrows():
        comp_id = row["company_id"]
        fin_path = f"./synthetic_data/financials/{comp_id}_financials.json"
        if os.path.exists(fin_path):
            with open(fin_path, "r") as f:
                fin_data = json.load(f)
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
                "label": row["is_fraudulent"]
            })
    return pd.DataFrame(rows)

def old_weighted_average(row):
    # Old simple weighted average formula mapping from risk-agent/main.py
    # Normalizing features on the fly
    dscr_norm = max(0.0, min(1.0, (2.5 - row["dscr"]) / 2.0))
    lev_norm = max(0.0, min(1.0, row["leverage"] / 5.0))
    rev_norm = max(0.0, min(1.0, (0.4 - row["revenue_growth_yoy"]) / 0.7))
    ebitda_norm = max(0.0, min(1.0, (0.3 - row["ebitda_margin"]) / 0.28))
    gst_norm = max(0.0, min(1.0, (row["gst_discrepancy_pct"] / 100) / 0.5))
    bounce_norm = max(0.0, min(1.0, row["bounce_rate"] / 20.0))
    lit_norm = 0.2
    news_norm = 0.5
    
    score = (
        0.25 * dscr_norm +
        0.18 * lev_norm +
        0.12 * rev_norm +
        0.10 * ebitda_norm +
        0.12 * gst_norm +
        0.08 * bounce_norm +
        0.10 * lit_norm +
        0.05 * news_norm
    )
    return score

def run_benchmark():
    print("==========================================================")
    # Load dataset
    try:
        df = load_data()
    except Exception as e:
        print(f"Error loading dataset: {e}")
        return
        
    print(f"Loaded {len(df)} company records for benchmarking.")
    y_true = df["label"].values
    
    # Extract features
    features_df = df.drop(columns=["label"])
    
    # 1. Baseline Old Score
    print("[*] Running Baseline Old Weighted Average Model...")
    old_scores = features_df.apply(old_weighted_average, axis=1).values
    
    # 2. Tri-Lens Risk Score (No DP)
    print("[*] Running Tri-Lens Attention-Weighted Fusion Model...")
    tri_scorer = TriLensRiskScorer(epsilon=0.0)
    tri_scores = []
    for idx, row in features_df.iterrows():
        tri_scores.append(tri_scorer.score(row.to_dict())["final_score"])
    tri_scores = np.array(tri_scores)
    
    # Compute metrics
    # Map raw scores to binary decision based on threshold > 0.55 (HIGH/REJECT)
    old_preds = (old_scores > 0.55).astype(int)
    tri_preds = (tri_scores > 0.55).astype(int)
    
    metrics = {
        "Old Weighted Average": {
            "Accuracy": accuracy_score(y_true, old_preds),
            "Precision": precision_score(y_true, old_preds, zero_division=0),
            "Recall": recall_score(y_true, old_preds, zero_division=0),
            "F1-Score": f1_score(y_true, old_preds, zero_division=0),
            "AUC-ROC": roc_auc_score(y_true, old_scores)
        },
        "Tri-Lens Score (Proposed)": {
            "Accuracy": accuracy_score(y_true, tri_preds),
            "Precision": precision_score(y_true, tri_preds, zero_division=0),
            "Recall": recall_score(y_true, tri_preds, zero_division=0),
            "F1-Score": f1_score(y_true, tri_preds, zero_division=0),
            "AUC-ROC": roc_auc_score(y_true, tri_scores)
        }
    }
    
    print("\n==========================================================")
    print("📊 BENCHMARK METRICS COMPARISON")
    print("==========================================================")
    print(f"{'Metric':<15} {'Old Weighted':<15} {'Tri-Lens (Proposed)':<20}")
    print("-" * 55)
    for metric in ["Accuracy", "Precision", "Recall", "F1-Score", "AUC-ROC"]:
        val_old = metrics["Old Weighted Average"][metric]
        val_tri = metrics["Tri-Lens Score (Proposed)"][metric]
        print(f"{metric:<15} {val_old:<15.4f} {val_tri:<20.4f}")
    print("==========================================================\n")
    
    # 3. Differential Privacy Epsilon-Accuracy Tradeoff Curve
    print("[*] Running Differential Privacy Epsilon-Accuracy Tradeoff Experiments...")
    epsilons = [0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0]
    dp_results = []
    
    for eps in epsilons:
        dp_scorer = TriLensRiskScorer(epsilon=eps)
        dp_scores = []
        for idx, row in features_df.iterrows():
            dp_scores.append(dp_scorer.score(row.to_dict())["final_score"])
        dp_scores = np.array(dp_scores)
        dp_preds = (dp_scores > 0.55).astype(int)
        
        acc = accuracy_score(y_true, dp_preds)
        auc = roc_auc_score(y_true, dp_scores)
        mae = np.mean(np.abs(dp_scores - tri_scores)) # MAE relative to non-private Tri-Lens score
        
        dp_results.append({
            "epsilon": eps,
            "Accuracy": round(acc, 4),
            "AUC-ROC": round(auc, 4),
            "MAE": round(mae, 4)
        })
        
    print("==========================================================")
    print("🔒 DIFFERENTIAL PRIVACY EPSILON-ACCURACY TRADEOFF")
    print("==========================================================")
    print(f"{'Epsilon (ε)':<15} {'Accuracy':<15} {'AUC-ROC':<15} {'MAE (vs Non-Private)':<20}")
    print("-" * 65)
    for res in dp_results:
        print(f"{res['epsilon']:<15.2f} {res['Accuracy']:<15.4f} {res['AUC-ROC']:<15.4f} {res['MAE']:<20.4f}")
    print("==========================================================\n")
    
    # Save results to output
    output = {
        "comparison": metrics,
        "dp_tradeoff": dp_results
    }
    with open("./synthetic_data/benchmark_results.json", "w") as f:
        json.dump(output, f, indent=4)
    print("[+] Saved benchmark results to ./synthetic_data/benchmark_results.json")

if __name__ == "__main__":
    run_benchmark()
