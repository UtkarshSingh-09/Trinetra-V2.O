import os
import importlib.util
import pytest

def load_stress_agent():
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    agents_dir = os.path.dirname(tests_dir)
    spec_path = os.path.join(agents_dir, "stress-agent", "main.py")
    spec = importlib.util.spec_from_file_location("stress_agent", spec_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def test_stressed_dscr_calculation():
    """Tests ebitda adjustments and dscr recomputation under shocks."""
    stress_agent = load_stress_agent()
    
    revenue = 75000000
    operating_expenses = 50000000
    interest = 2500000
    principal = 5000000
    
    # Test base case
    base_dscr = (revenue - operating_expenses) / (interest + principal)
    assert abs(base_dscr - 3.333) < 0.01

    # Stressed under revenue drop (-20% shock, vacancy_factor=0.0)
    dscr_rev = stress_agent.compute_stressed_dscr(
        revenue, operating_expenses, interest, principal, revenue_shock=-0.20, vacancy_factor=0.0
    )
    # Stressed NOI = 75M * 0.8 - 50M = 10M
    # Stressed DSCR = 10M / 7.5M = 1.333
    assert abs(dscr_rev - 1.333) < 0.01

    # Stressed under interest rate spike (+2% shock / 200 bps)
    dscr_rate = stress_agent.compute_stressed_dscr(
        revenue, operating_expenses, interest, principal, rate_shock_bps=200, vacancy_factor=0.0
    )
    # Stressed Interest = 2.5M * (1 + 0.02/0.10) = 2.5M * 1.2 = 3.0M
    # Stressed DSCR = 25M / (3.0M + 5.0M) = 3.125
    assert abs(dscr_rate - 3.125) < 0.01
