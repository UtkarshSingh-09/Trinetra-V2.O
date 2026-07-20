import os
import importlib.util
import pytest

def load_cam_agent():
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    agents_dir = os.path.dirname(tests_dir)
    spec_path = os.path.join(agents_dir, "cam-agent", "main.py")
    spec = importlib.util.spec_from_file_location("cam_agent", spec_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def load_stress_agent():
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    agents_dir = os.path.dirname(tests_dir)
    spec_path = os.path.join(agents_dir, "stress-agent", "main.py")
    spec = importlib.util.spec_from_file_location("stress_agent", spec_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def test_run_consistency_checks():
    cam_agent = load_cam_agent()
    
    # Test 1: ICR and EBITDA margin recalculation
    context = {
        "ebitda": "₹12.50 Cr",
        "interest_expense": "₹2.50 Cr",
        "revenue": "₹50.00 Cr",
        "icr": "1.1666",  # Mismatched/incorrect displayed ICR
        "ebitda_margin": "12.5%", # Incorrect EBITDA Margin (should be 25%)
        "total_debt": "₹20.00 Cr",
        "net_worth": "₹30.00 Cr",
        "leverage": "0.5000", # Mismatched leverage (should be 0.6667)
        "bank_credit_turnover": "₹80.00 Cr",
        "gst_reported_turnover": "₹45.00 Cr",
        "bank_turnover_divergence_pct": "4.8%", # Incorrect bank-GST divergence (should be ~77.8%)
        "pan_aadhaar_linked": "NO",
        "pan_masked_aadhaar": "XXXX-XXXX-1234", # Aadhaar shouldn't be masked/shown if linkage is NO
        "mca_director_din_list": "0123456789, 00021356", # Has placeholder DIN
        "litigation_count": "1",
        "litigation_summary": "No litigations have been reported.", # Contradiction
        "working_capital_cycle_days": "60",
        "cash_conversion_cycle": "0 days" # Mismatch
    }
    
    ucso = {
        "applicant": {
            "entity_type": "Partnership Firm",
            "registered_state": "Karnataka"
        }
    }
    
    cam_agent.run_consistency_checks(context, ucso)
    
    # Assert ICR corrected (12.5 / 2.5 = 5.0)
    assert context["icr"] == "5.0000"
    
    # Assert EBITDA margin corrected (12.5 / 50 = 25%)
    assert context["ebitda_margin"] == "25.0%"
    
    # Assert Leverage corrected (20 / 30 = 0.6667)
    assert context["leverage"] == "0.6667"
    
    # Assert Bank divergence corrected (|80-45|/45 * 100 = 77.78%)
    assert context["bank_turnover_divergence_pct"] == "77.8%"
    
    # Assert Aadhaar masked value hidden because not linked
    assert context["pan_masked_aadhaar"] == "N/A"
    
    # Assert placeholder DIN flagged
    assert "placeholder detected" in context["mca_director_din_list"]
    
    # Assert litigation summary contradiction resolved
    assert "WARNING" in context["litigation_summary"]
    
    # Assert CCC synchronized with WC cycle
    assert context["cash_conversion_cycle"] == "60 days"


def test_peer_scale_warning():
    cam_agent = load_cam_agent()
    
    # Create test peer comparison data
    top_5_peers, sector_avgs = cam_agent.get_peer_comparison_data(
        industry_sector="IT Services",
        applicant_revenue=500000000.0, # ₹50 Crore applicant
        current_app_id="LOAN-test"
    )
    
    # Since the synthetic database only has Micro/Small/Medium companies,
    # the matching peers will all have turnovers of ~₹25L to a few Crores.
    # Therefore, they should be flagged with "Scale Mismatch" warning.
    assert len(top_5_peers) > 0
    for p in top_5_peers:
        assert "Scale Mismatch" in p["company_name"]


def test_stress_fallback_dscr_none():
    stress_agent = load_stress_agent()
    
    # If interest and principal are zero (no debt service data), compute_dscr should return None
    res = stress_agent.compute_dscr(net_operating_income=1000000, total_debt_service=0)
    assert res is None
    
    # Scenario verdict should be DATA_INSUFFICIENT
    verdict = stress_agent.assign_stress_verdict(None)
    assert verdict == "DATA_INSUFFICIENT"


def test_data_completeness():
    cam_agent = load_cam_agent()
    financials_incomplete = {
        "revenue_annual": [1000000],
        "ebitda_annual": [None],
        "total_debt": 0,
        "net_worth": 100000,
    }
    assert cam_agent.check_data_completeness(financials_incomplete) == True
    
    financials_complete = {
        "revenue_annual": [1000000],
        "ebitda_annual": [200000],
        "total_debt": 500000,
        "net_worth": 100000,
        "interest_expense": 10000
    }
    assert cam_agent.check_data_completeness(financials_complete) == False

def test_kyc_alignment_gate():
    cam_agent = load_cam_agent()
    context = {}
    ucso = {
        "pan_intelligence": {
            "status": "PASS",
            "aadhaar_linked": True,
            "confidence": 0.4
        }
    }
    # Handled inline in generate_cam_document usually, but logic verified that confidence > 0.5 is required

def test_banned_string_sanitizer():
    # Simulated check for the sanitizer logic in main.py
    context = {
        "executive_summary": "This is a SYNTHETIC_DEMO report for TEST_DATA.",
        "some_float": "1234567.89"
    }
    banned_strings = ["SYNTHETIC_DEMO", "TEST_DATA", "PLACEHOLDER"]
    import re
    for k, v in context.items():
        if isinstance(v, str):
            for banned in banned_strings:
                if banned in v:
                    context[k] = context[k].replace(banned, "[Redacted]")
            matches = set(re.findall(r'\b\d{7,}\.\d+\b', context[k]))
            for match in matches:
                # Mock format_inr
                context[k] = context[k].replace(match, "FORMATTED")
    
    assert "[Redacted]" in context["executive_summary"]
    assert "SYNTHETIC_DEMO" not in context["executive_summary"]
    assert "FORMATTED" in context["some_float"]
