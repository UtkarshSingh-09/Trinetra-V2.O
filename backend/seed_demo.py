"""
Run: python3 backend/seed_demo.py
Creates one pre-seeded demo application and patches key namespaces.
"""
from __future__ import annotations

import json
from pathlib import Path

import requests

BASE_URL = "http://localhost:8000"

SAMPLE_APPLICATION = {
    "company_name": "Shivam Textiles Private Limited",
    "pan": "ABCDE1234F",
    "gstin": "27ABCDE1234F1Z5",
    "cin": "U17120MH2015PTC123456",
    "loan_amount_requested": 12500000,
    "loan_purpose": "Working capital expansion and machinery modernization",
    "industry_sector": "Textile Manufacturing",
    "promoter_name": "Rahul Sharma",
    "promoter_din": "01234567",
    "years_in_business": 11,
    "annual_turnover": 52000000,
    "existing_bank_loans": 14500000,
    "collateral_offered": "Factory land and plant machinery",
    "contact_email": "finance@shivamtextiles.in",
}

NAMESPACE_PATCHES = {
    "compliance": {
        "status": "PASS",
        "score": 0.94,
        "missing_documents": [],
        "issues": [],
        "phase": "compliance",
    },
    "financials": {
        "revenue_annual": [42000000, 47000000, 52000000],
        "ebitda_annual": [5600000, 6500000, 7696000],
        "total_debt": 14500000,
        "net_worth": 31000000,
        "interest_expense": 1650000,
        "principal_repayment": 2850000,
        "promoter_holding_pct": 68.5,
        "pledged_shares_pct": 4.2,
        "cibil_score": 742,
        "revenue_trend": "stable_growth",
        "ebitda_margin_pct": 14.8,
        "debt_service_coverage_ratio": 1.65,
        "working_capital_cycle_days": 71,
        "phase": "analysis",
    },
    "pan_intelligence": {
        "status": "PASS",
        "pan": "ABCDE1234F",
        "full_name": "Shivam Textiles Private Limited",
        "category": "Company",
        "pan_status": "VALID",
        "aadhaar_seeding_status": "LINKED",
        "confidence": 0.94,
    },
    "mca_intelligence": {
        "company_status": "ACTIVE",
        "director_changes_last_2yr": [
            {
                "din": "01234567",
                "name": "Rahul Sharma",
                "change_type": "APPOINTMENT",
                "date": "2025-08-22",
            }
        ],
        "charges_registered": [
            {
                "description": "Term loan charge on plant and machinery",
                "filing_date": "2025-11-10",
            }
        ],
        "new_charge_flag": True,
        "director_din_list": ["01234567"],
        "last_agm_date": "2025-09-30",
        "defaulter_flag": False,
    },
    "risk": {
        "score": 0.31,
        "band": "LOW",
        "decision": "APPROVED",
        "rationale": "Strong historical cashflow coverage and low adverse media exposure.",
    },
    "stress_results": {
        "scenarios": [
            {"name": "Revenue-20%", "dscr": 1.8, "verdict": "SURVIVES"},
            {"name": "Rate+2%", "dscr": 1.7, "verdict": "SURVIVES"},
            {"name": "Combined", "dscr": 1.6, "verdict": "SURVIVES"},
        ],
        "worst_case_dscr": 1.6,
        "survival_verdict": "SURVIVES",
    },
    "decision_confidence": {
        "score": 0.78,
        "data_completeness": 1.0,
        "extraction_confidence": 0.82,
        "kb_freshness_score": 0.71,
        "model_stability_score": 0.75,
        "formula": "0.30×DC + 0.30×EC + 0.20×KF + 0.20×MS",
    },
    "cam_output": {
        "status": "GENERATED",
        "title": "Credit Appraisal Memo",
        "summary": "Recommend sanction with standard covenants and quarterly monitoring.",
    },
}

VECTORAI_COLLECTIONS = [
    "document_chunks", "financial_profiles", "gst_patterns",
    "bank_recon_profiles", "news_articles", "litigation_records",
    "rbi_circulars", "mca_filings", "pan_profiles", "risk_decisions",
    "pd_transcripts", "stress_scenarios", "audit_events", "application_summaries",
]


def _pick_sample_pdf() -> Path | None:
    candidates = [
        Path(__file__).resolve().parents[1] / "actian_local" / "files",
        Path(__file__).resolve().parent / "actian_local" / "files",
    ]
    for base in candidates:
        if not base.exists():
            continue
        pdfs = sorted(base.rglob("*.pdf"))
        if pdfs:
            return pdfs[0]
    return None


def create_application() -> str:
    response = requests.post(f"{BASE_URL}/api/application", json=SAMPLE_APPLICATION, timeout=30)
    response.raise_for_status()
    payload = response.json()
    app_id = payload.get("id")
    if not app_id:
        raise RuntimeError(f"Unexpected create application response: {json.dumps(payload)}")
    return app_id


def upload_sample_document(application_id: str) -> None:
    pdf_path = _pick_sample_pdf()
    if not pdf_path:
        print("No sample PDF found. Skipping upload step.")
        return

    with pdf_path.open("rb") as file_obj:
        files = {
            "file": (pdf_path.name, file_obj, "application/pdf"),
        }
        data = {
            "application_id": application_id,
            "type": "ANNUAL_REPORT",
        }
        response = requests.post(f"{BASE_URL}/api/files/upload", files=files, data=data, timeout=60)
        response.raise_for_status()


def patch_namespaces(application_id: str) -> None:
    for namespace, payload in NAMESPACE_PATCHES.items():
        response = requests.patch(
            f"{BASE_URL}/api/application/{application_id}/namespace/{namespace}",
            json=payload,
            timeout=30,
        )
        response.raise_for_status()


def warmup_vectorai(application_id: str) -> None:
    for collection in VECTORAI_COLLECTIONS:
        requests.get(
            f"{BASE_URL}/api/vectorai/search",
            params={"q": f"{application_id} risk profile", "collection": collection, "top_k": 3},
            timeout=60,
        )


def main() -> None:
    print("Creating demo application...")
    app_id = create_application()
    print(f"Application created: {app_id}")

    print("Uploading sample PDF...")
    upload_sample_document(app_id)

    print("Patching namespaces with realistic demo data...")
    patch_namespaces(app_id)

    print("Warming up all VectorAI collections...")
    warmup_vectorai(app_id)

    print("Demo seed complete.")
    print(f"Use this application ID in frontend: {app_id}")


if __name__ == "__main__":
    main()
