import os
import importlib.util
import pytest
from unittest.mock import MagicMock, patch

def load_model_selector_agent():
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    agents_dir = os.path.dirname(tests_dir)
    spec_path = os.path.join(agents_dir, "model-selector-agent", "main.py")
    spec = importlib.util.spec_from_file_location("model_selector_agent", spec_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

@pytest.fixture
def mock_agent(mocker):
    mocker.patch('shared.vectorai_client.VectorAIClient.search', return_value=[])
    mocker.patch('shared.vectorai_client.VectorAIClient.upsert')
    
    ms_mod = load_model_selector_agent()
    agent = ms_mod.ModelSelectorAgent()
    agent.ucso_client.patch_namespace = MagicMock()
    agent.mod = ms_mod
    return agent

def test_count_populated_features(mock_agent):
    features = {
        "dscr": 1.5,
        "revenue": 0.0, # should be ignored
        "margin": 0.2,
        "dscr_normalized": 1.0 # should be ignored
    }
    assert mock_agent.mod.count_populated_features(features) == 2

def test_has_mixed_data(mock_agent):
    # Only financials -> not mixed
    assert mock_agent.mod.has_mixed_data({"financials": {"revenue_annual": 1000}}) is False
    
    # Financials + Web -> mixed
    assert mock_agent.mod.has_mixed_data({
        "financials": {"revenue_annual": 1000},
        "web_intel": {"promoter_news": "Good"}
    }) is True

def test_process_model_selection(mock_agent, monkeypatch):
    ucso = {
        "derived_features": {"dscr": 1.5, "margin": 0.2}
    }
    
    mock_select = MagicMock(return_value=("XGBOOST", "v1.0", "mock_object"))
    monkeypatch.setattr(mock_agent.mod, 'select_model', mock_select)
    
    result = mock_agent.process("test_app_id", ucso)
    
    assert result["model_used"] == "XGBOOST"
    assert result["model_version"] == "v1.0"
    mock_select.assert_called_once()

def test_process_similar_profiles_override(mock_agent, monkeypatch, mocker):
    ucso = {"derived_features": {"dscr": 1.5}}
    
    mock_select = MagicMock(return_value=("LOGISTIC", "v1.0", "mock_object"))
    monkeypatch.setattr(mock_agent.mod, 'select_model', mock_select)
    
    mocker.patch('shared.vectorai_client.VectorAIClient.search', return_value=[
        {"metadata": {"model_used": "XGBOOST"}},
        {"metadata": {"model_used": "XGBOOST"}},
        {"metadata": {"model_used": "XGBOOST"}},
        {"metadata": {"model_used": "LGBM"}}
    ])
    
    result = mock_agent.process("test_app_id", ucso)
    
    assert result["model_used"] == "XGBOOST"
