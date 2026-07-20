import numpy as np
import os
import json
import sys

# Ensure data_generator path is visible for importing sector profiles
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data_generator")))
try:
    from sector_profiles import SECTOR_PROFILES
except ImportError:
    SECTOR_PROFILES = {}

class TriLensRiskScorer:
    """
    Patent-worthy Tri-Lens Risk Scoring algorithm:
    1. Financial Lens: Solvency, liquidity, and growth features.
    2. Behavioral Lens: GST compliance, bank cash flows, circular trading, cheque bounces.
    3. Contextual Lens: Web news sentiment, litigation severity, regulatory headwinds.
    
    Dynamically fuses the lenses using an Attention-Weighted model based on feature confidence.
    Optionally applies Differential Privacy (Laplace mechanism) to the final risk score.
    """

    # Static lens base weights
    BASE_WEIGHTS = {
        "financial": 0.45,
        "behavioral": 0.35,
        "contextual": 0.20
    }

    FINANCIAL_BOUNDS = {
        "dscr": (0.5, 2.5, "inverse"),
        "icr": (1.0, 5.0, "inverse"),
        "leverage": (0.2, 4.0, "direct"),
        "current_ratio": (0.5, 2.5, "inverse"),
        "revenue_growth_yoy": (-0.2, 0.5, "inverse"),
        "ebitda_margin": (0.02, 0.30, "inverse"),
        "ltv_ratio": (0.1, 1.5, "direct")
    }

    BEHAVIORAL_BOUNDS = {
        "gst_discrepancy_pct": (0.0, 30.0, "direct"),
        "circular_trade_index": (0.0, 0.40, "direct"),
        "bounce_rate": (0.0, 15.0, "direct"),
        "bank_divergence_pct": (0.0, 25.0, "direct")
    }

    CONTEXTUAL_BOUNDS = {
        "web_sentiment_avg": (-0.8, 0.8, "inverse"),
        "litigation_count": (0.0, 5.0, "direct"),
        "years_in_business": (1.0, 15.0, "inverse"),
        "cibil_score": (300.0, 900.0, "inverse"),
        "promoter_holding_pct": (15.0, 95.0, "inverse")
    }

    def __init__(self, epsilon: float = 0.0):
        self.epsilon = epsilon
        
        weights_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "models", "tri_lens_weights.json"))
        if os.path.exists(weights_path):
            try:
                with open(weights_path, "r", encoding="utf-8") as f:
                    weights = json.load(f)
                if all(k in weights for k in ["financial", "behavioral", "contextual"]):
                    self.BASE_WEIGHTS = {k: float(weights[k]) for k in ["financial", "behavioral", "contextual"]}
            except Exception as e:
                print(f"[TriLens] Failed to load learned weights, using defaults: {e}")

    def _normalize(self, val: float, bounds: dict, feat_name: str, sector: str = None) -> float:
        """Helper to normalize a feature value to a [0, 1] risk score."""
        if feat_name not in bounds:
            return 0.5
            
        lo, hi, direction = bounds[feat_name]
        
        # Sector adaptive adjustments
        if sector and SECTOR_PROFILES and sector in SECTOR_PROFILES:
            prof = SECTOR_PROFILES[sector]
            if feat_name in prof:
                mean = prof[feat_name]["mean"]
                std = prof[feat_name]["std"]
                lo = max(0.01, mean - 2 * std)
                hi = mean + 2 * std
        
        # Non-linear risk mapping using a sigmoid curve for tail risk features
        if feat_name in ["leverage", "bounce_rate", "gst_discrepancy_pct", "bank_divergence_pct"]:
            k = 6.0 / (hi - lo) if hi != lo else 1.0
            x0 = (hi + lo) / 2.0
            ratio = 1.0 / (1.0 + np.exp(-k * (val - x0)))
            return (1.0 - ratio) if direction == "inverse" else ratio
        
        clipped = max(lo, min(hi, val))
        rng = hi - lo
        ratio = (clipped - lo) / rng if rng != 0 else 0.0
        return (1.0 - ratio) if direction == "inverse" else ratio

    def compute_financial_lens(self, features: dict) -> tuple[float, float]:
        """Computes Financial Lens sub-score and confidence."""
        sector = features.get("industry_sector")
        present_feats = [k for k in self.FINANCIAL_BOUNDS.keys() if k in features]
        if not present_feats:
            return 0.5, 0.0
            
        scores = []
        for feat in present_feats:
            scores.append(self._normalize(features[feat], self.FINANCIAL_BOUNDS, feat, sector))
            
        lens_score = np.mean(scores)
        confidence = len(present_feats) / len(self.FINANCIAL_BOUNDS)
        return float(lens_score), float(confidence)

    def compute_behavioral_lens(self, features: dict) -> tuple[float, float]:
        """Computes Behavioral Lens sub-score and confidence."""
        sector = features.get("industry_sector")
        present_feats = [k for k in self.BEHAVIORAL_BOUNDS.keys() if k in features]
        if not present_feats:
            return 0.5, 0.0
            
        scores = []
        for feat in present_feats:
            scores.append(self._normalize(features[feat], self.BEHAVIORAL_BOUNDS, feat, sector))
            
        lens_score = np.mean(scores)
        confidence = len(present_feats) / len(self.BEHAVIORAL_BOUNDS)
        return float(lens_score), float(confidence)

    def compute_contextual_lens(self, features: dict) -> tuple[float, float]:
        """Computes Contextual Lens sub-score and confidence."""
        sector = features.get("industry_sector")
        present_feats = [k for k in self.CONTEXTUAL_BOUNDS.keys() if k in features]
        if not present_feats:
            return 0.5, 0.0
            
        scores = []
        for feat in present_feats:
            scores.append(self._normalize(features[feat], self.CONTEXTUAL_BOUNDS, feat, sector))
            
        lens_score = np.mean(scores)
        confidence = len(present_feats) / len(self.CONTEXTUAL_BOUNDS)
        return float(lens_score), float(confidence)

    def attention_fusion(self, scores: dict, confidences: dict) -> float:
        """
        Computes attention weights dynamically based on base weights and confidence.
        fused_score = sum(alpha_i * score_i)
        """
        attn_vals = {}
        for lens in self.BASE_WEIGHTS.keys():
            attn_vals[lens] = self.BASE_WEIGHTS[lens] * confidences.get(lens, 0.0)
            
        sum_attn = sum(attn_vals.values())
        if sum_attn == 0:
            attn_weights = {k: 1.0 / len(self.BASE_WEIGHTS) for k in self.BASE_WEIGHTS}
        else:
            attn_weights = {k: v / sum_attn for k, v in attn_vals.items()}
            
        fused = sum(attn_weights[k] * scores.get(k, 0.5) for k in self.BASE_WEIGHTS)
        return float(fused), attn_weights

    def apply_differential_privacy(self, score: float) -> float:
        if self.epsilon <= 0:
            return score
            
        sensitivity = 0.01
        scale = sensitivity / self.epsilon
        noise = np.random.laplace(0, scale)
        
        dp_score = np.clip(score + noise, 0.0, 1.0)
        return float(dp_score)

    def score(self, features: dict) -> dict:
        """Main entry point to compute Tri-Lens score."""
        fin_score, fin_conf = self.compute_financial_lens(features)
        beh_score, beh_conf = self.compute_behavioral_lens(features)
        con_score, con_conf = self.compute_contextual_lens(features)
        
        scores = {
            "financial": fin_score,
            "behavioral": beh_score,
            "contextual": con_score
        }
        
        confidences = {
            "financial": fin_conf,
            "behavioral": beh_conf,
            "contextual": con_conf
        }
        
        fused_score, attn_weights = self.attention_fusion(scores, confidences)
        final_score = self.apply_differential_privacy(fused_score)
        
        return {
            "final_score": round(final_score, 4),
            "raw_fused_score": round(fused_score, 4),
            "lens_scores": {k: round(v, 4) for k, v in scores.items()},
            "lens_confidences": {k: round(v, 4) for k, v in confidences.items()},
            "attention_weights": {k: round(v, 4) for k, v in attn_weights.items()},
            "dp_applied": self.epsilon > 0,
            "epsilon": self.epsilon
        }
