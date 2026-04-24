"""
Agent 8: Model Selector Agent
Approach: Metadata Heuristics
Tools: Pure Python logic, pickle

Trigger: web_intel_completed, mca_completed
Reads: derived_features
Writes: risk.model_used
Logic: Feature count and distribution check. Selects the best ML model.
       <50 samples → Logistic. Tabular → XGBoost. Mixed → LightGBM.
Errors: MODEL_NOT_FOUND → fallback RULE_FALLBACK.
"""
import sys
import os
import pickle

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.agent_base import AgentBase
from shared.vectorai_client import VectorAIClient


vectorai = VectorAIClient()

# Model file paths (pre-trained .pkl files stored in S3 or local)
MODEL_DIR = os.getenv("MODEL_DIR", os.path.join(os.path.dirname(__file__), "..", "risk-agent", "models"))


def count_populated_features(derived_features: dict) -> int:
    """Count how many derived features have non-zero values."""
    count = 0
    for key, value in derived_features.items():
        if key.endswith("_normalized"):
            continue
        if isinstance(value, (int, float)) and value != 0.0:
            count += 1
    return count


def has_mixed_data(ucso: dict) -> bool:
    """
    Check if the data is 'mixed' (has both structured financials and
    unstructured web intel), which benefits from LightGBM.
    """
    has_financials = bool(ucso.get("financials", {}).get("revenue_annual"))
    has_web = bool(ucso.get("web_intel", {}).get("promoter_news"))
    has_pd = bool(ucso.get("pd_intelligence", {}).get("transcript_text"))
    return has_financials and (has_web or has_pd)


def select_model(derived_features: dict, ucso: dict) -> tuple:
    """
    Select the best ML model based on data availability.

    Returns:
        (model_name: str, model_version: str, model_object or None)
    """
    feature_count = count_populated_features(derived_features)

    if feature_count < 4:
        # Very sparse data → use simple logistic regression
        model_name = "LOGISTIC"
    elif has_mixed_data(ucso):
        # Mixed structured + unstructured data → LightGBM handles this well
        model_name = "LGBM"
    else:
        # Standard tabular financial data → XGBoost is king
        model_name = "XGBOOST"

    # Try to load pre-trained model
    model_files = {
        "LOGISTIC": "logistic_risk_model.pkl",
        "XGBOOST": "xgboost_risk_model.pkl",
        "LGBM": "lgbm_risk_model.pkl",
    }

    model_file = os.path.join(MODEL_DIR, model_files.get(model_name, ""))
    model_object = None

    if os.path.exists(model_file):
        try:
            with open(model_file, "rb") as f:
                model_object = pickle.load(f)
        except Exception:
            pass

    if model_object is None:
        # Fallback to rule-based scoring
        model_name = "RULE_FALLBACK"

    return model_name, "v1.0", model_object


class ModelSelectorAgent(AgentBase):
    AGENT_NAME = "model-selector-agent"
    LISTEN_TOPICS = ["web_intel_completed", "mca_completed"]
    OUTPUT_NAMESPACE = "risk"
    OUTPUT_EVENT = "model_selected"

    def process(self, application_id: str, ucso: dict) -> dict:
        """
        Analyze derived features and select the best ML model.
        """
        derived_features = ucso.get("derived_features", {})

        model_name, model_version, model_object = select_model(
            derived_features, ucso
        )

        self.logger.info(
            f"Selected model: {model_name} (v{model_version}) for {application_id}",
            extra={"agent_name": self.AGENT_NAME, "application_id": application_id},
        )

        similar_profiles = vectorai.search(
            collection="financial_profiles",
            query_text=" ".join(
                [
                    f"{k}={v}"
                    for k, v in derived_features.items()
                    if isinstance(v, (int, float))
                ]
            ),
            top_k=5,
            min_score=0.70,
        )
        past_models = [
            r.get("metadata", {}).get("model_used")
            for r in similar_profiles
            if r.get("metadata", {}).get("model_used")
        ]
        if past_models and past_models.count("XGBOOST") >= 3 and model_name != "RULE_FALLBACK":
            model_name = "XGBOOST"

        vectorai.upsert(
            collection="application_summaries",
            doc_id=f"{application_id}_model_selection",
            text=f"Model selected: {model_name} for application {application_id}",
            metadata={
                "application_id": application_id,
                "agent": self.AGENT_NAME,
                "model_used": model_name,
                "feature_count": count_populated_features(derived_features),
                "phase": "model_selection",
            },
        )

        return {
            "model_used": model_name,
            "model_version": model_version,
        }


if __name__ == "__main__":
    agent = ModelSelectorAgent()
    agent.run()
