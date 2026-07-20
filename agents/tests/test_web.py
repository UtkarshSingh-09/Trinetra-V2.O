import os
import importlib.util
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

def load_web_agent():
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    agents_dir = os.path.dirname(tests_dir)
    spec_path = os.path.join(agents_dir, "web-agent", "main.py")
    spec = importlib.util.spec_from_file_location("web_agent", spec_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

@pytest.fixture
def mock_agent(mocker):
    mocker.patch('shared.vectorai_client.VectorAIClient.upsert')
    
    web_mod = load_web_agent()
    agent = web_mod.WebIntelligenceAgent()
    agent.ucso_client.patch_namespace = MagicMock()
    agent.mod = web_mod
    return agent

def test_score_article(mock_agent):
    # Test positive sentiment
    pos_result = mock_agent.mod.score_article("Company announces record profits", "Everything is great.")
    assert pos_result["label"] == "POSITIVE"
    assert pos_result["risk_contribution"] < 0.5
    
    # Test negative sentiment
    neg_result = mock_agent.mod.score_article("Company CEO arrested for massive fraud", "Bankruptcy imminent.")
    assert neg_result["label"] == "NEGATIVE"
    assert neg_result["risk_contribution"] > 0.5
    
def test_aggregate_news_sentiment(mock_agent):
    articles = [
        {"risk_contribution": 0.1}, # Very low risk
        {"risk_contribution": 0.3}  # Low risk
    ]
    assert mock_agent.mod.aggregate_news_sentiment(articles) == 0.2
    
    # Empty list should default to neutral 0.5
    assert mock_agent.mod.aggregate_news_sentiment([]) == 0.5

def test_process_web_agent(mock_agent, monkeypatch):
    ucso = {
        "applicant": {"company_name": "Stark Industries", "industry_sector": "Tech", "pan": "ABCDE1234F"}
    }
    
    mock_news = MagicMock(return_value=[
        {"headline": "Good news", "published_at": datetime.now(timezone.utc).isoformat()}
    ])
    monkeypatch.setattr(mock_agent.mod, 'fetch_news', mock_news)
    
    mock_lit = MagicMock(return_value=[
        {"case_no": "123", "severity": "LOW"}
    ])
    monkeypatch.setattr(mock_agent.mod, 'fetch_litigation', mock_lit)
    
    mock_flags = MagicMock(return_value=[
        {"title": "AI Regulation"}
    ])
    monkeypatch.setattr(mock_agent.mod, 'fetch_regulatory_flags', mock_flags)
    
    result = mock_agent.process("test_app_id", ucso)
    
    assert len(result["promoter_news"]) == 1
    assert len(result["litigation_records"]) == 1
    assert "AI Regulation" in result["sector_headwinds"]
    assert result["kb_freshness_hours"] == 0 # because we used datetime.now

def test_process_stale_data(mock_agent, monkeypatch):
    ucso = {
        "applicant": {"company_name": "Stark Industries", "industry_sector": "Tech", "pan": "ABCDE1234F"}
    }
    
    mock_news = MagicMock(return_value=[
        {"headline": "Old news", "published_at": "2020-01-01T00:00:00+00:00"}
    ])
    monkeypatch.setattr(mock_agent.mod, 'fetch_news', mock_news)
    
    mock_lit = MagicMock(return_value=[])
    monkeypatch.setattr(mock_agent.mod, 'fetch_litigation', mock_lit)
    
    mock_flags = MagicMock(return_value=[])
    monkeypatch.setattr(mock_agent.mod, 'fetch_regulatory_flags', mock_flags)
    
    result = mock_agent.process("test_app_id", ucso)
    
    # Assert kb freshness is very high (stale)
    assert result["kb_freshness_hours"] > 1000
