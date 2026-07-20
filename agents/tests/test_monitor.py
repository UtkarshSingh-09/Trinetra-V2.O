import os
import importlib.util
import pytest
from unittest.mock import MagicMock

def load_monitor_agent():
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    agents_dir = os.path.dirname(tests_dir)
    spec_path = os.path.join(agents_dir, "monitor-agent", "main.py")
    spec = importlib.util.spec_from_file_location("monitor_agent", spec_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

@pytest.fixture
def mock_agent(mocker):
    mocker.patch('shared.vectorai_client.VectorAIClient.search', return_value=[])
    mocker.patch('shared.vectorai_client.VectorAIClient.upsert')
    
    monitor_mod = load_monitor_agent()
    agent = monitor_mod.MonitorAgent()
    agent.ucso_client.patch_namespace = MagicMock()
    return agent

def test_process_no_alerts(mock_agent):
    ucso = {
        "audit_log": [],
        "risk": {"score": 800},
        "ews_monitoring": {"risk_drift": 0.05}, # below threshold
        "web_intel": {"kb_freshness_hours": 24}, # below threshold
        "decision_confidence": {"score": 0.9}, # above threshold
        "documents": {"files": []}
    }
    
    result = mock_agent.process("test_app_id", ucso)
    
    assert result["alert_count"] == 0
    assert len(result["latest_check"]["alerts"]) == 0

def test_process_infinite_loop_alert(mock_agent):
    # Simulate an infinite loop with 3 repeated events
    ucso = {
        "audit_log": [
            {"application_id": "test_app_id", "event": "parsing_completed"},
            {"application_id": "test_app_id", "event": "parsing_completed"},
            {"application_id": "test_app_id", "event": "parsing_completed"}
        ]
    }
    
    result = mock_agent.process("test_app_id", ucso)
    
    alerts = result["latest_check"]["alerts"]
    assert any(a["type"] == "INFINITE_LOOP" for a in alerts)

def test_process_model_drift_alert(mock_agent):
    ucso = {
        "risk": {"score": 750},
        "ews_monitoring": {"risk_drift": 0.20} # Above 15% threshold
    }
    
    result = mock_agent.process("test_app_id", ucso)
    alerts = result["latest_check"]["alerts"]
    assert any(a["type"] == "MODEL_DRIFT" for a in alerts)

def test_process_kb_stale_alert(mock_agent):
    ucso = {
        "web_intel": {"kb_freshness_hours": 200} # Above 168h threshold
    }
    
    result = mock_agent.process("test_app_id", ucso)
    alerts = result["latest_check"]["alerts"]
    assert any(a["type"] == "KB_STALE" for a in alerts)

def test_process_low_confidence_alert(mock_agent):
    ucso = {
        "decision_confidence": {"score": 0.4} # Below 0.5 threshold
    }
    
    result = mock_agent.process("test_app_id", ucso)
    alerts = result["latest_check"]["alerts"]
    assert any(a["type"] == "LOW_CONFIDENCE" for a in alerts)

def test_process_parse_errors(mock_agent):
    ucso = {
        "documents": {
            "files": [
                {"parse_errors": ["Error 1", "Error 2"]}
            ]
        }
    }
    
    result = mock_agent.process("test_app_id", ucso)
    alerts = result["latest_check"]["alerts"]
    assert any(a["type"] == "PARSE_ERRORS" for a in alerts)

def test_process_agent_failure(mock_agent):
    ucso = {
        "audit_log": [
            {"status": "FAILED", "agent": "risk-agent", "error_code": "OOM"}
        ]
    }
    
    result = mock_agent.process("test_app_id", ucso)
    alerts = result["latest_check"]["alerts"]
    assert any(a["type"] == "AGENT_FAILURE" for a in alerts)
