import os
import importlib.util
import pytest
from unittest.mock import MagicMock, patch

def load_pd_agent():
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    agents_dir = os.path.dirname(tests_dir)
    spec_path = os.path.join(agents_dir, "pd-agent", "main.py")
    spec = importlib.util.spec_from_file_location("pd_agent", spec_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

@pytest.fixture
def mock_agent(mocker):
    mocker.patch('shared.vectorai_client.VectorAIClient.search', return_value=[])
    mocker.patch('shared.vectorai_client.VectorAIClient.upsert')
    
    pd_mod = load_pd_agent()
    agent = pd_mod.PDTranscriptAgent()
    agent.ucso_client.patch_namespace = MagicMock()
    agent.mod = pd_mod
    return agent

def test_process_no_notes(mock_agent):
    ucso = {"human_notes": {"notes": []}}
    result = mock_agent.process("test_app_id", ucso)
    
    assert result["transcript_text"] == ""
    assert "NO_PD_CONTENT" in result["qualitative_flags"]

def test_process_text_notes(mock_agent, monkeypatch):
    ucso = {
        "human_notes": {
            "notes": [{"type": "TEXT", "text": "Customer visited branch. Looks good."}]
        }
    }
    
    mock_eval = MagicMock(return_value={
        "overall_risk_adjustment": -0.05,
        "confidence": 0.8,
        "qualitative_flags": [],
        "entities_extracted": {"people": ["Customer"]}
    })
    monkeypatch.setattr(mock_agent.mod, 'evaluate_transcript', mock_eval)
    
    result = mock_agent.process("test_app_id", ucso)
    
    assert result["transcript_text"] == "Customer visited branch. Looks good."
    assert result["risk_adjustment"] == -0.05
    assert result["pd_confidence"] == 0.8
    assert result["source_type"] == "TEXT"

def test_risk_adjustment_clamping(mock_agent, monkeypatch):
    ucso = {
        "human_notes": {
            "notes": [{"type": "TEXT", "text": "Terrible interview."}]
        }
    }
    
    mock_eval = MagicMock(return_value={
        "overall_risk_adjustment": 0.50,
        "confidence": 0.9
    })
    monkeypatch.setattr(mock_agent.mod, 'evaluate_transcript', mock_eval)
    
    result = mock_agent.process("test_app_id", ucso)
    assert result["risk_adjustment"] == 0.15
    
    mock_eval = MagicMock(return_value={
        "overall_risk_adjustment": -0.50,
        "confidence": 0.9
    })
    monkeypatch.setattr(mock_agent.mod, 'evaluate_transcript', mock_eval)
    result2 = mock_agent.process("test_app_id", ucso)
    assert result2["risk_adjustment"] == -0.10
