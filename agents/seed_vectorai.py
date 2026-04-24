"""
Seed Actian VectorAI (official beta SDK) with demo intelligence data.
Run once after starting the VectorAI gRPC container:
    cd agents && python3 seed_vectorai.py
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

from actian_vectorai import Distance, PointStruct, VectorAIClient, VectorParams
from sentence_transformers import SentenceTransformer


VECTORAI_URL = os.getenv("VECTORAI_URL", "localhost:50051")
EMBEDDING_MODEL = os.getenv("VECTORAI_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
EMBEDDING_DIM = int(os.getenv("VECTORAI_EMBEDDING_DIM", "384"))

COLLECTIONS = [
    "document_chunks",
    "financial_profiles",
    "gst_patterns",
    "bank_recon_profiles",
    "news_articles",
    "litigation_records",
    "rbi_circulars",
    "mca_filings",
    "pan_profiles",
    "risk_decisions",
    "pd_transcripts",
    "stress_scenarios",
    "audit_events",
    "application_summaries",
]

MODEL = SentenceTransformer(EMBEDDING_MODEL)


def embed(text: str) -> list[float]:
    return MODEL.encode(text).tolist()


def ensure_collection(client: VectorAIClient, name: str) -> bool:
    try:
        if client.collections.exists(name):
            return True
        client.collections.create(
            name,
            vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.Cosine),
        )
        return True
    except Exception:
        return False


def upsert_docs(client: VectorAIClient, collection: str, docs: list[dict]) -> int:
    if not docs:
        return 0
    points = []
    ts = datetime.now(timezone.utc).isoformat()
    for d in docs:
        payload = dict(d.get("metadata", {}))
        payload["source_id"] = d["id"]
        payload["text"] = d["text"]
        payload["seeded_at"] = ts
        points.append(
            PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{collection}:{d['id']}")),
                vector=embed(d["text"]),
                payload=payload,
            )
        )
    client.points.upsert(collection, points)
    return len(points)


SEED_DATA: dict[str, list[dict]] = {
    "news_articles": [
        {
            "id": "news_001",
            "text": "SEBI investigates textile-linked circular trading and ITC inflation patterns.",
            "metadata": {
                "headline": "SEBI probes circular trading in textiles",
                "source_url": "https://example.com/sebi-textile",
                "credibility_score": 5,
                "published_at": "2026-04-01T00:00:00Z",
            },
        },
        {
            "id": "news_002",
            "text": "Textile exporters report improved margins due to demand recovery.",
            "metadata": {
                "headline": "Textile demand improves in Q1",
                "source_url": "https://example.com/textile-q1",
                "credibility_score": 4,
                "published_at": "2026-03-20T00:00:00Z",
            },
        },
    ],
    "litigation_records": [
        {
            "id": "lit_001",
            "text": "Criminal GST fraud case involving fabricated invoices in a textile chain.",
            "metadata": {
                "case_no": "WP/2025/1234",
                "court": "Delhi High Court",
                "case_type": "Criminal",
                "status": "Pending",
                "severity": "HIGH",
            },
        },
        {
            "id": "lit_002",
            "text": "Civil recovery case for delayed debt repayment by manufacturing borrower.",
            "metadata": {
                "case_no": "CS/2024/5678",
                "court": "Bombay High Court",
                "case_type": "Civil",
                "status": "Pending",
                "severity": "MEDIUM",
            },
        },
    ],
    "rbi_circulars": [
        {
            "id": "rbi_001",
            "text": "RBI stress testing guidance for credit portfolios and borrower resilience review.",
            "metadata": {
                "circular_no": "RBI/2025-26/22",
                "title": "Mandatory Stress Testing",
                "issued_date": "2025-12-15",
            },
        },
        {
            "id": "rbi_002",
            "text": "RBI prudential norms for NPA classification and provisioning.",
            "metadata": {
                "circular_no": "RBI/2025-26/01",
                "title": "Prudential Norms",
                "issued_date": "2025-07-01",
            },
        },
    ],
    "mca_filings": [
        {
            "id": "mca_001",
            "text": "Company is active with annual return filed on time and no default.",
            "metadata": {
                "cin": "U28100MH2010PLC123456",
                "company_name": "ABC Industries Limited",
                "filing_type": "ANNUAL",
                "risk_flag": False,
            },
        },
        {
            "id": "mca_002",
            "text": "New charge filed by lender against plant and machinery assets.",
            "metadata": {
                "cin": "U24230GJ2008PLC345678",
                "company_name": "GHI Pharmaceuticals Ltd",
                "filing_type": "CHARGE",
                "risk_flag": False,
            },
        },
    ],
    "gst_patterns": [
        {
            "id": "gst_001",
            "text": "High discrepancy between GSTR-2B and GSTR-3B with suspicious cycle evidence.",
            "metadata": {"status": "FLAG", "discrepancy_pct": 18.4},
        },
        {
            "id": "gst_002",
            "text": "Low discrepancy and no cycle risk; reconciliation status OK.",
            "metadata": {"status": "OK", "discrepancy_pct": 2.1},
        },
    ],
    "stress_scenarios": [
        {
            "id": "stress_001",
            "text": "Stress profile textile borrower: worst_dscr 1.62, survives moderate shocks.",
            "metadata": {"survival_verdict": "SURVIVES", "worst_dscr": 1.62},
        },
        {
            "id": "stress_002",
            "text": "Stress profile leveraged borrower: worst_dscr 1.08, vulnerable in combined shock.",
            "metadata": {"survival_verdict": "VULNERABLE", "worst_dscr": 1.08},
        },
    ],
    "pan_profiles": [
        {
            "id": "pan_001",
            "text": "PAN verified and linked profile with compliant filing behavior.",
            "metadata": {"pan": "ABCDE1234F", "status": "PASS", "category": "Company"},
        },
        {
            "id": "pan_002",
            "text": "PAN profile with low confidence due to inconsistent public records.",
            "metadata": {"pan": "ABCDE1234G", "status": "WARNING", "category": "Company"},
        },
    ],
    "document_chunks": [
        {
            "id": "chunk_001",
            "text": "Annual report snippet: revenue increased from 4.8 crore to 5.4 crore with EBITDA 72 lakh.",
            "metadata": {"doc_type": "ANNUAL_REPORT", "chunk_num": 1},
        },
    ],
    "financial_profiles": [
        {
            "id": "fin_001",
            "text": "Financial profile DSCR 1.67 leverage 0.62 revenue growth 11 percent.",
            "metadata": {"industry": "textile", "model_used": "XGBOOST"},
        },
    ],
    "bank_recon_profiles": [
        {
            "id": "bank_001",
            "text": "Bank reconciliation profile divergence 6.2 percent and no inflation flag.",
            "metadata": {"verdict": "OK", "turnover_divergence_pct": 6.2},
        },
    ],
    "risk_decisions": [
        {
            "id": "risk_001",
            "text": "Risk decision medium band approve with score 0.37 for textile manufacturer.",
            "metadata": {"decision": "APPROVE", "risk_band": "MEDIUM", "risk_score": 0.37},
        },
    ],
    "pd_transcripts": [
        {
            "id": "pd_001",
            "text": "Promoter reports stable operations and timely receivable collections in interview.",
            "metadata": {"source_type": "TEXT", "risk_adjustment": -0.02},
        },
    ],
    "audit_events": [
        {
            "id": "audit_001",
            "text": "Health check shows zero alerts and complete pipeline progression.",
            "metadata": {"alert_count": 0, "agent": "monitor-agent"},
        },
    ],
    "application_summaries": [
        {
            "id": "summary_001",
            "text": "Demo application approved with medium risk and stable stress resilience.",
            "metadata": {"phase": "cam", "decision": "APPROVE"},
        },
    ],
}


def main() -> None:
    client = VectorAIClient(VECTORAI_URL)
    client.connect()

    print(f"Connecting to Actian VectorAI at {VECTORAI_URL} ...")
    print("Creating all 14 collections...")
    for name in COLLECTIONS:
        ok = ensure_collection(client, name)
        print(f"  {'OK' if ok else 'FAIL'} {name}")

    total = 0
    print("\nSeeding data across collections...")
    for collection, docs in SEED_DATA.items():
        inserted = upsert_docs(client, collection, docs)
        total += inserted
        print(f"  inserted {inserted:>2} docs -> {collection}")

    print(f"\nSeeding complete. Inserted {total} demo vectors across 14 collections.")


if __name__ == "__main__":
    main()
