import os
import importlib.util
import pytest

def load_doc_agent():
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    agents_dir = os.path.dirname(tests_dir)
    spec_path = os.path.join(agents_dir, "doc-agent", "main.py")
    spec = importlib.util.spec_from_file_location("doc_agent", spec_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def test_indian_number_normalization():
    """Tests that doc-agent correctly normalizes Indian currency strings into floats."""
    doc_agent = load_doc_agent()
    
    assert doc_agent.normalize_indian_number("₹12,50,000") == 1250000.0
    assert doc_agent.normalize_indian_number("5.2 Cr") == 52000000.0
    assert doc_agent.normalize_indian_number("3.5 Lakh") == 350000.0
    assert doc_agent.normalize_indian_number("1,00,000") == 100000.0
    assert doc_agent.normalize_indian_number("invalid") == 0.0
