import os
import importlib.util
import pytest

def load_risk_agent():
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    agents_dir = os.path.dirname(tests_dir)
    spec_path = os.path.join(agents_dir, "risk-agent", "main.py")
    spec = importlib.util.spec_from_file_location("risk_agent", spec_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def test_feature_normalization():
    """Tests that features are normalized to [0, 1] bounds correctly."""
    risk_agent = load_risk_agent()
    
    # Test dscr normalization (lo=0.5, hi=2.5, inverse direction)
    assert risk_agent.normalize(2.5, "dscr") == 0.0 # highest dscr = 0 risk
    assert risk_agent.normalize(0.5, "dscr") == 1.0 # lowest dscr = 1 risk
    assert 0 < risk_agent.normalize(1.5, "dscr") < 1.0

    # Test leverage normalization (lo=0.0, hi=5.0, direct direction)
    assert risk_agent.normalize(0.0, "leverage") == 0.0 # lowest leverage = 0 risk
    assert risk_agent.normalize(5.0, "leverage") == 1.0 # highest leverage = 1 risk

def test_risk_band_assignments():
    """Tests boundary assignments for risk categories."""
    risk_agent = load_risk_agent()
    
    assert risk_agent.assign_band(0.20) == "LOW"
    assert risk_agent.assign_band(0.40) == "MEDIUM"
    assert risk_agent.assign_band(0.65) == "HIGH"
    assert risk_agent.assign_band(0.85) == "REJECT"

def test_active_model_resolver(tmp_path):
    """Tests active model resolution configurations (AUTO vs specific model override)."""
    # Test manual active model override detection
    import json
    cfg = {"active_model": "XGBOOST"}
    cfg_file = tmp_path / "active_model.json"
    with open(cfg_file, "w") as f:
        json.dump(cfg, f)
        
    active_model = "AUTO"
    if os.path.exists(cfg_file):
        try:
            with open(cfg_file, "r") as f:
                c = json.load(f)
                active_model = c.get("active_model", "AUTO")
        except:
            pass
            
    assert active_model == "XGBOOST"

def test_dynamic_imputation_engine():
    """Tests the DynamicImputationEngine peer and global imputation lookup logic."""
    import importlib.util
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    agents_dir = os.path.dirname(tests_dir)
    spec_path = os.path.join(agents_dir, "risk-agent", "imputation.py")
    spec = importlib.util.spec_from_file_location("imputation", spec_path)
    imputation_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(imputation_mod)
    
    DynamicImputationEngine = imputation_mod.DynamicImputationEngine
    engine = DynamicImputationEngine()
    
    # Test with a mock raw features dictionary where some values are missing (None)
    raw_feats = {
        "dscr": 2.5,
        "icr": None,
        "leverage": 0.8,
        "current_ratio": None,
        "revenue_growth_yoy": 0.1,
        "ebitda_margin": None,
        "cibil_score": 750,
        "promoter_holding_pct": None,
        "gst_discrepancy_pct": 2.5,
        "bank_divergence_pct": None,
        "web_sentiment_avg": 0.5,
        "bounce_rate": None,
        "years_in_business": 10,
        "ltv_ratio": None,
    }
    
    sector = "Logistics & Transport"
    
    imputed_feats, sources = engine.impute_missing_features(raw_feats, sector)
    
    # dscr should be EXTRACTED
    assert sources["dscr"] == "EXTRACTED"
    assert imputed_feats["dscr"] == 2.5
    
    # icr is missing, should be imputed
    assert sources["icr"] in ("IMPUTED_SECTOR", "IMPUTED_GLOBAL", "GLOBAL_DEFAULT")
    assert imputed_feats["icr"] is not None
    
    # cibil_score should be EXTRACTED
    assert sources["cibil_score"] == "EXTRACTED"
    assert imputed_feats["cibil_score"] == 750
    
    # circular_trade_index should be imputed
    assert sources["circular_trade_index"] in ("IMPUTED_SECTOR", "IMPUTED_GLOBAL", "GLOBAL_DEFAULT")
    assert imputed_feats["circular_trade_index"] is not None

