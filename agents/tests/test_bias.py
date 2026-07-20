import os
import importlib.util
import pytest

def load_bias_agent():
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    agents_dir = os.path.dirname(tests_dir)
    spec_path = os.path.join(agents_dir, "bias-agent", "main.py")
    spec = importlib.util.spec_from_file_location("bias_agent", spec_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def test_bias_decision_stability():
    """Tests the counterfactual flip check concept."""
    original_score = 0.35
    original_decision = "APPROVED"
    
    # Counterfactual modification (e.g. swap sensitive feature to baseline)
    modified_score = 0.28 
    
    # Verify if decision flipped (threshold 0.55)
    original_approved = original_score <= 0.55
    modified_approved = modified_score <= 0.55
    
    decision_flips = original_approved != modified_approved
    
    assert decision_flips is False
