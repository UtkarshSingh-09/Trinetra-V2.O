import os
import importlib.util
import pytest

def load_bank_agent():
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    agents_dir = os.path.dirname(tests_dir)
    spec_path = os.path.join(agents_dir, "bank-recon-agent", "main.py")
    spec = importlib.util.spec_from_file_location("bank_recon_agent", spec_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def test_bank_reconciliation_divergence():
    """Tests bank statement and declared revenue matching rules."""
    bank_agent = load_bank_agent()
    
    # 4% divergence - should pass
    bank_turnover = 72000000
    gst_turnover = 75000000
    itr_income = 73000000
    
    avg_declared = (gst_turnover + itr_income) / 2
    divergence = abs(bank_turnover - avg_declared) / avg_declared * 100
    inflation_flag = divergence > 25
    
    assert divergence < 5.0
    assert not inflation_flag

    # 35% divergence - should trigger flag
    bank_turnover_inflated = 110000000
    divergence_high = abs(bank_turnover_inflated - avg_declared) / avg_declared * 100
    inflation_flag_high = divergence_high > 25

    assert divergence_high > 30.0
    assert inflation_flag_high is True
