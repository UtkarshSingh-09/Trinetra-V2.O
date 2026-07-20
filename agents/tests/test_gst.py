import os
import importlib.util
import pytest

def load_gst_agent():
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    agents_dir = os.path.dirname(tests_dir)
    spec_path = os.path.join(agents_dir, "gst-agent", "main.py")
    spec = importlib.util.spec_from_file_location("gst_agent", spec_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def test_itc_discrepancy_calculation():
    """Tests ITC divergence logic between GSTR-2B input credit and GSTR-3B claimed returns."""
    gst_agent = load_gst_agent()
    
    res = gst_agent.compute_itc_discrepancy(
        {"total_itc": 5000000},
        {"itc_claimed": 5800000}
    )
    assert abs(res["discrepancy_pct"] - 16.0) < 0.1
    assert res["itc_mismatch_flag"] is True

    res_clean = gst_agent.compute_itc_discrepancy(
        {"total_itc": 5000000},
        {"itc_claimed": 5100000}
    )
    assert res_clean["discrepancy_pct"] < 5.0
    assert res_clean["itc_mismatch_flag"] is False

def test_circular_trading_cycle_detection():
    """Tests cycle search logic to detect fraudulent round-trip shell networks."""
    gst_agent = load_gst_agent()
    
    # Simple circular cycle: A -> B -> C -> A
    transactions = [
        {"seller_gstin": "GSTIN_A", "buyer_gstin": "GSTIN_B", "amount": 500000},
        {"seller_gstin": "GSTIN_B", "buyer_gstin": "GSTIN_C", "amount": 500000},
        {"seller_gstin": "GSTIN_C", "buyer_gstin": "GSTIN_A", "amount": 500000},
    ]
    res = gst_agent.detect_circular_trading(transactions)
    
    assert res["total_edges"] == 3
    assert res["circular_trade_index"] > 0.0
    assert len(res["suspicious_cycles"]) > 0
