import os
import importlib.util
import pytest
from unittest.mock import MagicMock, patch

def load_mca_agent():
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    agents_dir = os.path.dirname(tests_dir)
    spec_path = os.path.join(agents_dir, "mca-agent", "main.py")
    spec = importlib.util.spec_from_file_location("mca_agent", spec_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

@pytest.fixture
def mock_agent(mocker):
    # Mock the VectorAIClient imported in main.py
    mocker.patch('shared.vectorai_client.VectorAIClient.search', return_value=[])
    mocker.patch('shared.vectorai_client.VectorAIClient.upsert')
    
    mca_mod = load_mca_agent()
    agent = mca_mod.MCAIntelligenceAgent()
    # Mock the ucso client push to prevent actual network calls
    agent.ucso_client.patch_namespace = MagicMock()
    # attach the module so we can patch its internal functions
    agent.mod = mca_mod 
    return agent

def test_process_empty_input(mock_agent):
    ucso = {"applicant": {}}
    result = mock_agent.process("test_app_id", ucso)
    
    assert result["company_status"] == "UNKNOWN"
    assert result["director_changes_last_2yr"] == []

def test_process_with_valid_cin(mock_agent, monkeypatch):
    ucso = {
        "applicant": {
            "cin": "L12345MH2000PLC123456",
            "company_name": "Test Company Ltd"
        }
    }
    
    mock_fetch = MagicMock(side_effect=Exception("Qdrant error"))
    monkeypatch.setattr(mock_agent.mod, 'fetch_from_qdrant', mock_fetch)
    
    mock_fetch_quicko = MagicMock(return_value={
        "company_status": "ACTIVE",
        "defaulter_flag": False,
        "director_changes_last_2yr": [],
        "charges_registered": [],
        "new_charge_flag": False,
        "director_din_list": ["00000001"],
        "last_agm_date": "2025-09-30"
    })
    monkeypatch.setattr(mock_agent.mod, 'fetch_mca_quicko', mock_fetch_quicko)
    
    result = mock_agent.process("test_app_id", ucso)
    
    assert result["company_status"] == "ACTIVE"
    assert "00000001" in result["director_din_list"]
    mock_fetch_quicko.assert_called_once_with("L12345MH2000PLC123456", "Test Company Ltd")

def test_process_with_qdrant_success(mock_agent, monkeypatch):
    ucso = {
        "applicant": {
            "cin": "L12345MH2000PLC123456",
            "company_name": "Test Company Ltd"
        }
    }
    
    mock_fetch_quicko = MagicMock(side_effect=Exception("Quicko API error"))
    monkeypatch.setattr(mock_agent.mod, 'fetch_mca_quicko', mock_fetch_quicko)
    
    mock_fetch = MagicMock(return_value={
        "company_status": "FLAGGED",
        "defaulter_flag": True,
        "director_changes_last_2yr": [],
        "charges_registered": [],
        "new_charge_flag": False,
        "director_din_list": [],
        "last_agm_date": ""
    })
    monkeypatch.setattr(mock_agent.mod, 'fetch_from_qdrant', mock_fetch)
    
    result = mock_agent.process("test_app_id", ucso)
    
    assert result["company_status"] == "FLAGGED"
    assert result["defaulter_flag"] is True
