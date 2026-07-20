import os
import importlib.util
import pytest
from unittest.mock import MagicMock, patch

def load_pan_agent():
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    agents_dir = os.path.dirname(tests_dir)
    spec_path = os.path.join(agents_dir, "pan-agent", "main.py")
    spec = importlib.util.spec_from_file_location("pan_agent", spec_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

@pytest.fixture
def mock_agent(mocker):
    mocker.patch('shared.vectorai_client.VectorAIClient.hybrid_search', return_value=[])
    mocker.patch('shared.vectorai_client.VectorAIClient.upsert')
    
    pan_mod = load_pan_agent()
    agent = pan_mod.PanVerificationAgent()
    agent.ucso_client.patch_namespace = MagicMock()
    agent.mod = pan_mod
    return agent

def test_process_empty_pan(mock_agent):
    ucso = {"applicant": {}}
    result = mock_agent.process("test_app_id", ucso)
    
    assert result["status"] == "FAIL"
    assert result["pan_status"] == "MISSING"

def test_process_setu_success(mock_agent, monkeypatch):
    ucso = {
        "applicant": {"pan": "ABCDE1234F"}
    }
    
    mock_setu = MagicMock(return_value={
        "full_name": "Tony Stark",
        "pan_status": "VALID",
        "category": "Individual",
        "aadhaar_linked": True,
        "confidence": 1.0,
        "source": "SETU_PRODUCTION_API"
    })
    monkeypatch.setattr(mock_agent.mod, 'verify_pan_setu', mock_setu)
    
    result = mock_agent.process("test_app_id", ucso)
    
    assert result["status"] == "PASS"
    assert result["pan_status"] == "VALID"
    assert result["full_name"] == "Tony Stark"
    assert result["extraction_method"] == "SETU_PRODUCTION_API"

def test_process_setu_fail_fallback_rag(mock_agent, monkeypatch):
    ucso = {
        "applicant": {"pan": "ABCDE1234F"}
    }
    
    mock_setu = MagicMock(return_value={"pan_status": "ERROR", "confidence": 0.0})
    monkeypatch.setattr(mock_agent.mod, 'verify_pan_setu', mock_setu)
    
    mock_search = MagicMock(return_value="Found PAN ABCDE1234F for Stark Industries")
    monkeypatch.setattr(mock_agent.mod, 'search_pan_public_data', mock_search)
    
    mock_llm = MagicMock(return_value={
        "full_name": "Stark Industries",
        "category": "Company",
        "pan_status": "VALID",
        "confidence": 0.9,
        "source": "WEB_RAG"
    })
    monkeypatch.setattr(mock_agent.mod, 'extract_pan_info_with_llm', mock_llm)
    
    result = mock_agent.process("test_app_id", ucso)
    
    assert result["status"] == "PASS"
    assert result["full_name"] == "Stark Industries"

def test_process_setu_fail_rag_fail_fallback_deterministic(mock_agent, monkeypatch):
    ucso = {
        "applicant": {"pan": "ABCDE1234C", "company_name": "Test Corp"}
    }
    
    mock_setu = MagicMock(return_value={"pan_status": "ERROR", "confidence": 0.0})
    monkeypatch.setattr(mock_agent.mod, 'verify_pan_setu', mock_setu)
    
    mock_search = MagicMock(return_value="")
    monkeypatch.setattr(mock_agent.mod, 'search_pan_public_data', mock_search)
    
    result = mock_agent.process("test_app_id", ucso)
    
    assert result["status"] == "FAIL"
    assert result["pan_status"] == "ERROR"
