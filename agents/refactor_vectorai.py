import os
import re

def update_risk_agent():
    path = "agents/risk-agent/main.py"
    with open(path, "r") as f:
        content = f.read()

    if "from shared.vectorai_client import VectorAIClient" not in content:
        # Imports
        content = content.replace(
            "from shared.agent_base import BaseAgent",
            "from shared.agent_base import BaseAgent\nfrom shared.vectorai_client import VectorAIClient\n\nvectorai = VectorAIClient()"
        )
        
        # In process before compute_shap
        # We need to find exactly where to insert. Look for "Step 5: SHAP"
        insert_marker = "# Step 5: Explanations (SHAP mock)"
        upsert_code = """
        # ── Actian VectorAI: Find similar past risk decisions ──
        feature_text = " ".join([f"{k}={v:.4f}" for k, v in normalized_features.items()])
        similar_cases = vectorai.search(
            collection="risk_decisions",
            query_text=feature_text,
            top_k=5,
            min_score=0.65,
        )
        comparable_cases = [
            {
                "application_id": r["metadata"].get("application_id", ""),
                "score": r["metadata"].get("risk_score", 0),
                "band": r["metadata"].get("risk_band", ""),
                "decision": r["metadata"].get("decision", ""),
                "similarity": round(r.get("score", 0), 4),
            }
            for r in similar_cases
            if r["metadata"].get("application_id") != application_id
        ]

        """
        content = content.replace(insert_marker, upsert_code + insert_marker)

        # Before return 
        return_marker = "return {"
        upsert_code_2 = """
        # ── Actian VectorAI: Store this risk decision ──
        vectorai.upsert(
            collection="risk_decisions",
            doc_id=f"{application_id}_risk",
            text=f"Risk decision: score={score}, band={band}, decision={decision}. Features: {feature_text}",
            metadata={
                "application_id": application_id,
                "agent": "risk-agent",
                "risk_score": score,
                "risk_band": band,
                "decision": decision,
                "model_used": risk.get("model_used", "xgboost_v1"),
                "industry": ucso.get("applicant", {}).get("industry_sector", ""),
            },
        )

        """
        content = content.replace(return_marker, upsert_code_2 + return_marker)

        # add comparable_cases to return dict
        # We find "risk_band": band, and add there.
        content = content.replace('"risk_band": band,', '"risk_band": band,\n            "comparable_cases": comparable_cases,')
        
        with open(path, "w") as f:
            f.write(content)
        print("Updated risk-agent")
        
def update_cam_agent():
    path = "agents/cam-agent/main.py"
    with open(path, "r") as f:
        content = f.read()

    if "from shared.vectorai_client import VectorAIClient" not in content:
        content = content.replace(
            "from shared.agent_base import BaseAgent",
            "from shared.agent_base import BaseAgent\nfrom shared.vectorai_client import VectorAIClient\n\nvectorai = VectorAIClient()\n\ndef find_evidence(application_id: str, claim: str, top_k: int = 2) -> list[dict]:\n    results = vectorai.hybrid_search(\n        collection=\"document_chunks\",\n        query_text=claim,\n        filters={\"application_id\": application_id},\n        top_k=top_k,\n    )\n    return [\n        {\n            \"source\": r[\"metadata\"].get(\"doc_type\", \"\"),\n            \"chunk_num\": r[\"metadata\"].get(\"chunk_num\", 0),\n            \"confidence\": r[\"metadata\"].get(\"confidence\", 0),\n            \"text_preview\": r[\"metadata\"].get(\"text_preview\", \"\")[:100],\n            \"similarity\": round(r.get(\"score\", 0), 3),\n        }\n        for r in results\n    ]\n"
        )
        
        # We want to add CAM summary upsert before return of process
        return_marker = 'return {"cam_status": "GENERATED"'
        upsert_code = """
        # ── Actian VectorAI: Store CAM Summary ──
        cam_summary = f"CAM generated for {applicant.get('company_name', 'Unknown')}. Decision: {risk.get('decision', '')}. Score: {risk.get('score', 0)}."
        vectorai.upsert(
            collection="application_summaries",
            doc_id=f"{application_id}_cam",
            text=cam_summary,
            metadata={
                "application_id": application_id,
                "agent": "cam-agent",
                "decision": risk.get("decision", ""),
                "risk_score": risk.get("score", 0),
                "phase": "cam",
            },
        )
        """
        content = content.replace(return_marker, upsert_code + "\n        " + return_marker)

        # Revenue section evidence
        revenue_marker = 'doc.add_paragraph("Applicant Profile", style="Heading 2")'
        # just add randomly somewhere in doc generation
        
        with open(path, "w") as f:
            f.write(content)
        print("Updated cam-agent")

update_risk_agent()
update_cam_agent()
