import os
import sys
import pytest
from unittest.mock import patch

# Mock VectorAIClient globally to prevent Qdrant sqlite locks or network hangs during test loading
patcher = patch('shared.vectorai_client.VectorAIClient.__init__', return_value=None)
patcher.start()

@pytest.fixture
def sample_ucso():
    """Returns a copy of the default, high-fidelity sample UCSO data."""
    return {
        "application_id": "TEST-APP-001",
        "ucso_version": 1,
        "applicant": {
            "company_name": "Trinetra Industries Pvt Ltd",
            "pan": "AABCT1234A",
            "gstin": "07AABCT1234A1Z5",
            "cin": "U72200DL2020PTC123456",
            "promoter_name": "Utkarsh Singh",
            "sector": "fintech",
            "incorporation_date": "2020-01-15",
            "years_in_business": 5,
            "loan_amount_requested": 15000000
        },
        "compliance": {},
        "documents": {
            "files": [
                {"type": "ANNUAL_REPORT", "s3_key": "test/annual_report.pdf", "status": "UPLOADED"},
                {"type": "BANK_STMT", "s3_key": "test/bank_stmt.pdf", "status": "UPLOADED"},
                {"type": "GST_RETURN", "s3_key": "test/gst_return.pdf", "status": "UPLOADED"},
                {"type": "ITR", "s3_key": "test/itr.pdf", "status": "UPLOADED"},
            ]
        },
        "financials": {
            "revenue_annual": [50000000, 60000000, 75000000],
            "ebitda_annual": [8000000, 10000000, 13000000],
            "total_debt": 20000000,
            "net_worth": 30000000,
            "interest_expense": 2500000,
            "principal_repayment": 3000000,
            "promoter_holding_pct": 65.0,
            "pledged_shares_pct": 5.0,
            "cibil_score": 750,
            "current_assets": 40000000,
            "current_liabilities": 25000000,
            "bounce_rate": 2.0,
            "bank_divergence_pct": 4.0,
            "gst_discrepancy_pct": 16.0,
            "web_sentiment_avg": 0.65,
            "years_in_business": 5,
            "ltv_ratio": 0.67
        },
        "gst_analysis": {
            "gstr_2b_itc": 5000000,
            "gstr_3b_itc_claimed": 5800000,
            "gstr2b_vs_3b_discrepancy_pct": 16.0,
            "reconciliation_status": "DISCREPANCY",
            "circular_trade_index": 0.0,
            "suspicious_cycles": [],
            "supplier_gstin_list": ["07AABCT1234A1Z5", "27BBBFT5678B1Z3"],
        },
        "bank_reconciliation": {
            "annual_credit_turnover": 72000000,
            "gst_turnover": 75000000,
            "itr_income": 73000000,
            "turnover_divergence_pct": 4.0,
            "revenue_inflation_flag": False,
            "round_trip_count": 0,
            "bounce_rate": 2.0,
            "reconciliation_verdict": "PASS",
        },
        "mca_intelligence": {
            "company_status": "ACTIVE",
            "director_changes_last_2yr": [],
            "new_charge_flag": False,
            "defaulter_flag": False,
        },
        "web_intel": {
            "promoter_news": [
                {"headline": "Trinetra raises Series A funding", "sentiment_score": 0.8, "source": "Economic Times"},
                {"headline": "Fintech sector sees growth", "sentiment_score": 0.5, "source": "Mint"},
            ],
            "litigation_records": [],
            "sector_headwinds": [],
            "kb_freshness_hours": 24,
            "news_sentiment_avg": 0.65
        },
        "pd_intelligence": {
            "transcript_text": "The borrower has a clear succession plan...",
            "risk_adjustment": -0.05,
            "key_findings": {"succession_plan": True, "capacity_concern": False},
        },
        "derived_features": {
            "dscr": 1.8,
            "icr": 5.2,
            "leverage": 0.67,
            "current_ratio": 1.6,
            "revenue_growth_yoy": 0.25,
            "ebitda_margin": 0.173,
            "cibil_score": 750,
            "promoter_holding_pct": 65.0,
            "gst_discrepancy_pct": 16.0,
            "bank_divergence_pct": 4.0,
            "web_sentiment_avg": 0.65,
            "years_in_business": 5,
            "ltv_ratio": 0.67
        },
        "risk": {
            "model_used": "TRI_LENS",
            "score": 0.35,
            "band": "LOW",
            "decision": "APPROVED",
            "recommended_limit": 15000000,
            "recommended_rate_bps": 950,
            "top_risk_factors": [
                {"feature": "gst_discrepancy_pct", "shap_value": 0.12},
                {"feature": "leverage", "shap_value": 0.08},
                {"feature": "revenue_growth_yoy", "shap_value": -0.05},
            ],
            "rejection_reasons": [],
            "corrective_actions": [],
        },
        "bias_checks": {
            "counterfactual_tested": False,
            "flip_features": [],
        },
        "stress_results": {
            "scenarios": [],
            "worst_case_dscr": 0,
            "survival_verdict": "",
        },
        "cam_output": {},
        "decision_confidence": {"score": 0.82, "formula": "0.4*model + 0.3*doc + 0.2*recon + 0.1*web"},
        "human_notes": {"raw_text": "Borrower seems confident. Revenue projections look solid."},
        "audit_log": [],
        "ews_monitoring": {"risk_drift": 0.0},
    }
