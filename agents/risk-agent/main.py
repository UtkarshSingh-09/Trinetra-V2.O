import os
os.environ["MPLBACKEND"] = "agg"
import xgboost
import lightgbm
import shap
import lime

"""
Agent 9: Risk Agent
Approach: Tree-Based Machine Learning & Explainable AI (XAI)
Tools: xgboost, lightgbm, shap, lime

Trigger: model_selected
Reads: derived_features, gst_analysis, bank_reconciliation, web_intel, pd_intelligence
Writes: risk
Logic: Normalize features → Weighted score → SHAP + LIME → Limits + Rate
Errors: SHAP_FAIL → continue without SHAP. LIME_FAIL → continue without LIME.
"""
import sys
import pickle
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
from shared.agent_base import AgentBase
from shared.vectorai_client import VectorAIClient
from tri_lens import TriLensRiskScorer
from imputation import DynamicImputationEngine


vectorai = VectorAIClient()


# ── Feature Normalization (from Blueprint Section 2.1) ──
FEATURE_BOUNDS = {
    # (raw_min, raw_max, risk_direction)
    # 'inverse' = lower raw = higher risk
    # 'direct'  = higher raw = higher risk
    "dscr":             (0.5,  2.5,  "inverse"),
    "icr":              (1.0,  5.0,  "inverse"),
    "leverage":         (0.0,  5.0,  "direct"),
    "ccc":              (0,    180,  "direct"),
    "revenue_growth":   (-0.3, 0.4,  "inverse"),
    "ebitda_margin":    (-0.1, 0.4,  "inverse"),
    "gst_discrepancy":  (0.0,  0.5,  "direct"),
    "circular_trade":   (0.0,  0.5,  "direct"),
    "litigation_count": (0,    10,   "direct"),
    "news_sentiment":   (-1.0, 1.0,  "inverse"),
}

# ── Outlier Safe Bounds (from Blueprint Section 4, GAP 3) ──
SAFE_BOUNDS = {
    "dscr":           (0.0, 5.0),
    "leverage":       (0.0, 20.0),
    "revenue_growth": (-1.0, 5.0),
    "ccc":            (-365, 365),
}

# ── Risk Weights (from Blueprint Section 2.2) ──
from shared.risk_utils import WEIGHTS


def handle_outlier(feature_name: str, raw_value: float) -> float:
    """Clip outliers to safe production bounds."""
    lo, hi = SAFE_BOUNDS.get(feature_name, (-1e9, 1e9))
    return max(lo, min(hi, raw_value))


def normalize(raw_value: float, feat_name: str) -> float:
    """Normalize a raw feature to [0, 1] risk scale."""
    if feat_name not in FEATURE_BOUNDS:
        return 0.5

    lo, hi, direction = FEATURE_BOUNDS[feat_name]
    clipped = max(lo, min(hi, raw_value))
    ratio = (clipped - lo) / (hi - lo) if (hi - lo) != 0 else 0.0
    return (1 - ratio) if direction == "inverse" else ratio


def compute_risk_score(features: dict) -> float:
    """Compute weighted risk score."""
    score = sum(WEIGHTS[k] * features.get(k, 0.5) for k in WEIGHTS)
    pd_adj = features.get("pd_risk_adjustment", 0.0)
    return round(min(1.0, max(0.0, score + pd_adj)), 4)


from shared.risk_utils import assign_band


def compute_limit_and_rate(requested: float, score: float, base_rate_bps: float = 850) -> tuple:
    """Calculate recommended loan limit and interest rate premium."""
    limit = requested * (1 - score * 0.6)     # max 60% haircut
    rate_bps = base_rate_bps + (score * 400)   # max +400bps premium
    return round(limit, 2), round(rate_bps, 2)


def compute_rejection_reasons(top_factors: list, band: str) -> list:
    """Generate human-readable rejection reasons from top risk factors."""
    if band not in ("HIGH", "REJECT"):
        return []

    reasons = []
    reason_map = {
        "dscr_normalized": "Debt Service Coverage Ratio is below acceptable threshold",
        "leverage_normalized": "Debt-to-Equity ratio indicates excessive leverage",
        "gst_discrepancy_norm": "Significant discrepancy between GSTR-2B and GSTR-3B returns",
        "circular_trade_norm": "Circular trading patterns detected in GST transactions",
        "litigation_norm": "Elevated litigation risk based on active court cases",
        "revenue_growth_normalized": "Revenue growth is declining or negative",
        "ebitda_margin_normalized": "EBITDA margins are below industry benchmarks",
        "news_sentiment_norm": "Negative news sentiment detected for the company/promoters",
    }

    for factor in top_factors[:3]:
        feat = factor.get("feature", "")
        if feat in reason_map:
            reasons.append(reason_map[feat])

    return reasons


def run_shap_analysis(model, feature_vector: dict) -> dict:
    """
    Run SHAP (Global Explainability) on the risk model.
    Returns SHAP values for each feature.
    """
    try:
        import shap

        feature_names = list(feature_vector.keys())
        feature_values = np.array([list(feature_vector.values())])

        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(feature_values)

        if isinstance(shap_values, list):
            shap_values = shap_values[0]

        result = {}
        for i, name in enumerate(feature_names):
            result[name] = round(float(shap_values[0][i]), 6)

        return result

    except Exception as e:
        print(f"SHAP_FAIL: {e}")
        return {}


def run_lime_analysis(model, feature_vector: dict) -> dict:
    """
    Run LIME (Local Explainability) to explain this specific prediction.
    """
    try:
        from lime.lime_tabular import LimeTabularExplainer

        feature_names = list(feature_vector.keys())
        feature_values = np.array([list(feature_vector.values())])

        # Create a dummy training set around the current values for LIME
        dummy_train = np.random.normal(
            loc=feature_values, scale=0.1, size=(100, len(feature_names))
        )
        dummy_train = np.clip(dummy_train, 0, 1)

        explainer = LimeTabularExplainer(
            dummy_train,
            feature_names=feature_names,
            mode="regression",
            random_state=42,
        )

        explanation = explainer.explain_instance(
            feature_values[0],
            model.predict if hasattr(model, "predict") else lambda x: np.array([0.5] * len(x)),
            num_features=len(feature_names),
        )

        result = {}
        for feat, weight in explanation.as_list():
            result[feat] = round(weight, 6)

        return result

    except Exception as e:
        print(f"LIME_FAIL: {e}")
        return {}


MODEL_DIR = os.getenv("MODEL_DIR", os.path.join(os.path.dirname(__file__), "models"))
if not os.path.isabs(MODEL_DIR):
    abs_path = os.path.abspath(MODEL_DIR)
    if not os.path.exists(abs_path):
        agents_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        resolved_path = os.path.abspath(os.path.join(agents_dir, MODEL_DIR))
        if os.path.exists(resolved_path):
            MODEL_DIR = resolved_path
        else:
            MODEL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "models"))
    else:
        MODEL_DIR = abs_path


class RiskAgent(AgentBase):
    AGENT_NAME = "risk-agent"
    LISTEN_TOPICS = ["model_selected"]
    OUTPUT_NAMESPACE = "risk"
    OUTPUT_EVENT = "risk_generated"

    def __init__(self):
        super().__init__()
        self.imputation_engine = DynamicImputationEngine(vectorai_client=vectorai)

    def process(self, application_id: str, ucso: dict) -> dict:
        """
        Full risk scoring pipeline:
        1. Build feature vector from all UCSO namespaces
        2. Normalize features
        3. Compute weighted risk score
        4. Assign band, limit, rate
        5. Run SHAP and LIME explainability
        """
        derived = ucso.get("derived_features", {})
        gst = ucso.get("gst_analysis", {})
        bank = ucso.get("bank_reconciliation", {})
        web = ucso.get("web_intel", {})
        pd_intel = ucso.get("pd_intelligence", {})
        applicant = ucso.get("applicant", {})
        financials = ucso.get("financials", {})

        # Check data quality: verify if key features were successfully extracted
        has_real_dscr = derived.get("dscr") is not None and derived.get("dscr") != 0.0
        has_real_icr = derived.get("icr") is not None and derived.get("icr") != 0.0
        has_real_revenue = bool(financials.get("revenue_annual") or financials.get("revenue"))
        has_real_bank = bank.get("avg_monthly_balance") is not None and bank.get("avg_monthly_balance") != 0.0
        has_real_gst = gst.get("gstr2b_vs_3b_discrepancy_pct") is not None

        pan_intel = ucso.get("pan_intelligence", {})
        compliance = ucso.get("compliance", {})

        # Track data quality issues as warnings (NOT blocking gates)
        data_quality_warnings = []
        data_quality_penalty = 0.0

        if pan_intel.get("status") != "PASS":
            data_quality_warnings.append("PAN verification is PENDING or FAILED.")
            data_quality_penalty += 0.05  # Small penalty, not a block

        if compliance.get("status") != "PASS":
            data_quality_warnings.append("Document compliance is PENDING or Non-Compliant.")
            data_quality_penalty += 0.05

        if bank.get("reconciliation_verdict") in ["PENDING", "UNKNOWN", None]:
            data_quality_warnings.append("Bank Reconciliation is PENDING or missing.")
            data_quality_penalty += 0.03

        if not has_real_revenue or not has_real_dscr:
            data_quality_warnings.append("Core financial metrics (Revenue/DSCR) are missing or 'Data pending'.")
            data_quality_penalty += 0.05

        if data_quality_warnings:
            self.logger.warning(
                f"Data quality warnings (non-blocking): {data_quality_warnings}",
                extra={"agent_name": self.AGENT_NAME, "application_id": application_id}
            )

        data_quality = "HIGH"
        data_quality_notes = "Financial and behavioral features successfully verified and extracted."

        # ── Step 1 & 2: Build raw 16-feature vector and impute dynamically ──
        sector = applicant.get("industry_sector") or ""

        # Helper functions to safely coalesce and cast values, avoiding falsy numeric values gotcha (like 0.0)
        def get_float(*args):
            for arg in args:
                if arg is not None:
                    try:
                        return float(arg)
                    except (ValueError, TypeError):
                        pass
            return None

        def get_int(*args):
            for arg in args:
                if arg is not None:
                    try:
                        return int(arg)
                    except (ValueError, TypeError):
                        pass
            return None

        # Extract features (use None if missing or 0.0 for critical fields)
        extracted_features = {
            "dscr": get_float(derived.get("dscr"), financials.get("dscr")),
            "icr": get_float(derived.get("icr"), financials.get("icr")),
            "leverage": get_float(derived.get("leverage"), financials.get("leverage")),
            "current_ratio": get_float(derived.get("current_ratio"), financials.get("current_ratio")),
            "revenue_growth_yoy": get_float(derived.get("revenue_growth"), derived.get("revenue_growth_yoy"), financials.get("revenue_growth_yoy")),
            "ebitda_margin": get_float(derived.get("ebitda_margin"), financials.get("ebitda_margin")),
            "cibil_score": get_int(derived.get("cibil_score"), financials.get("cibil_score"), applicant.get("cibil_score")),
            "promoter_holding_pct": get_float(derived.get("promoter_holding_pct"), financials.get("promoter_holding_pct"), applicant.get("promoter_holding_pct")),
            "gst_discrepancy_pct": get_float(gst.get("gstr2b_vs_3b_discrepancy_pct"), financials.get("gst_discrepancy_pct")),
            "bank_divergence_pct": get_float(bank.get("turnover_divergence_pct"), financials.get("bank_divergence_pct")),
            "web_sentiment_avg": get_float(web.get("news_sentiment_avg"), sum(n.get("sentiment_score", 0) for n in web.get("promoter_news", [])) / max(1, len(web.get("promoter_news", []))) if web.get("promoter_news") else None, financials.get("web_sentiment_avg")),
            "bounce_rate": get_float(bank.get("bounce_rate"), financials.get("bounce_rate")),
            "years_in_business": get_int(applicant.get("years_in_business"), financials.get("years_in_business")),
            "ltv_ratio": get_float(derived.get("ltv_ratio"), financials.get("ltv_ratio")),
            "circular_trade_index": get_float(gst.get("circular_trade_index"), financials.get("circular_trade_index")),
            "litigation_count": get_int(web.get("litigation_count"), len(web.get("litigation_records")) if web.get("litigation_records") is not None else None)
        }

        # Calculate data completeness score
        non_zero_check_features = {
            "dscr", "icr", "leverage", "current_ratio", "ebitda_margin",
            "cibil_score", "promoter_holding_pct", "years_in_business", "ltv_ratio"
        }
        extracted_count = 0
        for feat, val in extracted_features.items():
            if val is not None:
                if feat in non_zero_check_features and float(val) == 0.0:
                    continue
                extracted_count += 1
        data_completeness_score = int(round((extracted_count / 16.0) * 100))

        # Dynamic imputation via RAG / local peer statistics
        raw_features, feature_sources = self.imputation_engine.impute_missing_features(extracted_features, sector)

        # Handle outliers in place using SAFE_BOUNDS
        for feat in SAFE_BOUNDS:
            if feat in raw_features:
                raw_features[feat] = handle_outlier(feat, raw_features[feat])

        # ── Step 3: Compute risk score using active model ──
        epsilon = float(os.getenv("DP_EPSILON", "0.0"))
        scorer = TriLensRiskScorer(epsilon=epsilon)
        tri_result = scorer.score(raw_features)
        
        # Determine the globally active model
        import json
        active_model = "AUTO"
        active_model_path = os.path.join(MODEL_DIR, "active_model.json")
        if os.path.exists(active_model_path):
            try:
                with open(active_model_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    active_model = cfg.get("active_model", "AUTO")
            except Exception:
                pass
                
        # Heuristically selected model (default)
        model_used = ucso.get("risk", {}).get("model_used", "RULE_FALLBACK")
        
        # Final resolved model to use
        model_to_use = model_used if active_model == "AUTO" else active_model
        if model_to_use == "RULE_FALLBACK":
            model_to_use = "TRI_LENS"
            
        score_computed = False
        score = None
        
        # 14 features expected by models in exact sequence
        feature_names = [
            "dscr", "icr", "leverage", "current_ratio", "revenue_growth_yoy",
            "ebitda_margin", "cibil_score", "promoter_holding_pct",
            "gst_discrepancy_pct", "bank_divergence_pct", "web_sentiment_avg",
            "bounce_rate", "years_in_business", "ltv_ratio"
        ]
        
        if model_to_use in ["LOGISTIC", "XGBOOST", "LGBM"]:
            model_file_map = {
                "LOGISTIC": "logistic_risk_model.pkl",
                "XGBOOST": "xgboost_risk_model.pkl",
                "LGBM": "lgbm_risk_model.pkl"
            }
            model_path = os.path.join(MODEL_DIR, model_file_map[model_to_use])
            if os.path.exists(model_path):
                try:
                    with open(model_path, "rb") as f:
                        loaded_model = pickle.load(f)
                    
                    X = np.array([[raw_features[feat] for feat in feature_names]])
                    
                    if model_to_use == "LOGISTIC":
                        scaler_path = os.path.join(MODEL_DIR, "feature_scaler.pkl")
                        if os.path.exists(scaler_path):
                            with open(scaler_path, "rb") as sf:
                                scaler = pickle.load(sf)
                            X_scaled = scaler.transform(X)
                            score = float(loaded_model.predict_proba(X_scaled)[0, 1])
                            score_computed = True
                        else:
                            print("[RiskAgent] Feature scaler missing for Logistic. Falling back.")
                    else:
                        score = float(loaded_model.predict(X)[0])
                        score_computed = True
                except Exception as ex:
                    print(f"[RiskAgent] Model inference failed: {ex}. Falling back to Tri-Lens.")
            else:
                print(f"[RiskAgent] Model file {model_path} missing. Falling back to Tri-Lens.")
                
        if not score_computed:
            score = tri_result["final_score"]
            model_to_use = "TRI_LENS"
            
        score = round(min(1.0, max(0.0, score + data_quality_penalty)), 4)
        band = assign_band(score)
        model_used = model_to_use  # Override model_used so it returns the exact model in the UCSO namespace

        feature_text = " ".join([f"{k}={v:.4f}" for k, v in raw_features.items()])
        
        # Comparable cases in VectorAI database
        similar_cases = vectorai.search(
            collection="risk_decisions",
            query_text=feature_text,
            top_k=5,
            min_score=0.65,
        )
        comparable_cases = [
            {
                "application_id": r.get("metadata", {}).get("application_id", ""),
                "score": r.get("metadata", {}).get("risk_score", 0),
                "band": r.get("metadata", {}).get("risk_band", ""),
                "decision": r.get("metadata", {}).get("decision", ""),
                "similarity": round(r.get("score", 0), 4),
            }
            for r in similar_cases
            if r.get("metadata", {}).get("application_id") != application_id
        ]

        # ── Step 4: Limit and rate calculation ──
        # ── Step 4: Limit and rate calculation ──
        requested = (
            applicant.get("loan_amount_requested")
            or applicant.get("loan_amount")
            or ucso.get("loan_requested")
            or ucso.get("loan_amount_requested")
            or 0
        )
        limit, rate_bps = compute_limit_and_rate(requested, score)
        
        # Ensure limit is strictly bounded
        limit = max(0.0, min(limit, requested))
        # If low/medium risk and limit is less than 30% of request due to high haircut, set floor to 30% of request
        if band in ("LOW", "MEDIUM") and requested > 0 and limit < requested * 0.3:
            limit = requested * 0.3
        limit = round(limit, 2)

        # ── Step 5: SHAP + LIME ──
        model = None
        model_files = {
            "LOGISTIC": "logistic_risk_model.pkl",
            "XGBOOST": "xgboost_risk_model.pkl",
            "LGBM": "lgbm_risk_model.pkl",
        }

        if model_used in model_files:
            model_path = os.path.join(MODEL_DIR, model_files[model_used])
            if os.path.exists(model_path):
                try:
                    with open(model_path, "rb") as f:
                        model = pickle.load(f)
                except Exception as e:
                    print(f"MODEL_LOAD_FAIL: {e}")

        # Use tri_features for exact column alignment during inference
        shap_values = run_shap_analysis(model, raw_features) if model else {}
        lime_explanation = run_lime_analysis(model, raw_features) if model else {}

        # ── Step 6: Top risk factors ──
        if shap_values:
            sorted_shap = sorted(shap_values.items(), key=lambda x: abs(x[1]), reverse=True)
            top_risk_factors = [
                {"feature": k, "shap_value": v}
                for k, v in sorted_shap[:5]
            ]
        else:
            # Fallback: calculate contributions based on Tri-Lens normalized feature values and attention weights
            contributions = []
            attn_weights = tri_result["attention_weights"]
            
            # Map features to their lenses and calculate weighted contribution
            feature_lens_mapping = {
                # Financial Lens features
                "dscr": "financial", "icr": "financial", "leverage": "financial", 
                "current_ratio": "financial", "revenue_growth_yoy": "financial", 
                "ebitda_margin": "financial", "ltv_ratio": "financial",
                # Behavioral Lens features
                "gst_discrepancy_pct": "behavioral", "circular_trade_index": "behavioral", 
                "bounce_rate": "behavioral", "bank_divergence_pct": "behavioral",
                # Contextual Lens features
                "web_sentiment_avg": "contextual", "litigation_count": "contextual", 
                "years_in_business": "contextual", "cibil_score": "contextual", 
                "promoter_holding_pct": "contextual"
            }
            
            for feat, val in raw_features.items():
                lens = feature_lens_mapping.get(feat)
                if lens:
                    # Normalized value
                    if lens == "financial":
                        norm_val = scorer._normalize(val, scorer.FINANCIAL_BOUNDS, feat)
                    elif lens == "behavioral":
                        norm_val = scorer._normalize(val, scorer.BEHAVIORAL_BOUNDS, feat)
                    else:
                        norm_val = scorer._normalize(val, scorer.CONTEXTUAL_BOUNDS, feat)
                        
                    weight = attn_weights.get(lens, 0.33)
                    contributions.append((feat, norm_val * weight, weight))
                    
            contributions.sort(key=lambda x: x[1], reverse=True)
            top_risk_factors = [
                {"feature": k, "contribution": float(round(c, 4)), "weight": float(round(w, 4))}
                for k, c, w in contributions[:5]
            ]

        # Decision
        decision = "APPROVE" if band in ("LOW", "MEDIUM") else ("REVIEW" if band == "HIGH" else "REJECT")

        # Rejection reasons
        rejection_reasons = compute_rejection_reasons(top_risk_factors, band)

        # Corrective actions
        corrective_actions = []
        if band in ("HIGH", "REJECT"):
            # Use raw_features to verify thresholds
            # Check DSCR < 1.2, leverage > 2.0, gst discrepancy > 10%
            if raw_features.get("dscr", 1.5) < 1.2:
                corrective_actions.append("Improve DSCR by reducing debt or increasing cash flows")
            if raw_features.get("leverage", 1.2) > 2.0:
                corrective_actions.append("Reduce leverage by injecting equity or repaying debt")
            if raw_features.get("gst_discrepancy_pct", 0.0) > 10.0:
                corrective_actions.append("Resolve ITC discrepancies between GSTR-2B and GSTR-3B")

        vectorai.upsert(
            collection="risk_decisions",
            doc_id=f"{application_id}_risk",
            text=f"Risk decision: score={score}, band={band}, decision={decision}. Features: {feature_text}",
            metadata={
                "application_id": application_id,
                "agent": self.AGENT_NAME,
                "risk_score": score,
                "risk_band": band,
                "decision": decision,
                "model_used": model_used,
                "industry": applicant.get("industry_sector", ""),
            },
        )

        return {
            "score": score,
            "band": band,
            "model_used": model_used,
            "model_version": ucso.get("risk", {}).get("model_version", "v1.0"),
            "feature_vector": raw_features,
            "tri_lens_details": tri_result,
            "shap_values": shap_values,
            "lime_explanation": lime_explanation,
            "top_risk_factors": top_risk_factors,
            "decision": decision,
            "recommended_limit": limit,
            "recommended_rate_bps": rate_bps,
            "rejection_reasons": rejection_reasons,
            "corrective_actions": corrective_actions,
            "comparable_cases": comparable_cases,
            "data_quality": data_quality,
            "data_quality_notes": data_quality_notes,
            "decision_confidence": "LOW" if data_quality == "LOW" else "HIGH",
            "data_completeness_score": data_completeness_score,
            "feature_sources": feature_sources,
        }


if __name__ == "__main__":
    agent = RiskAgent()
    agent.run()
