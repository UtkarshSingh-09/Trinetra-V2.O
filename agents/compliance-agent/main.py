"""
Agent 1: Compliance Agent
Approach: Deterministic Rule-Engine
Tools: Standard Python json and List Comprehensions

Trigger: application_created
Reads: applicant, documents
Writes: compliance
Logic: Checks if ANNUAL_REPORT, BANK_STMT, GST_RETURN, ITR are present.
Errors: DOCS_MISSING → emit checklist + notify frontend via WebSocket
"""
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.agent_base import AgentBase
from shared.vectorai_client import VectorAIClient


vectorai = VectorAIClient()


REQUIRED_DOC_TYPES = ["ANNUAL_REPORT", "BANK_STMT", "GST_RETURN", "ITR"]


class ComplianceAgent(AgentBase):
    AGENT_NAME = "compliance-agent"
    LISTEN_TOPICS = ["application_created"]
    OUTPUT_NAMESPACE = "compliance"
    OUTPUT_EVENT = ""  # Dynamically set based on pass/fail

    def process(self, application_id: str, ucso: dict) -> dict:
        """
        Check if all required documents are present in the UCSO.
        If any are missing, emit compliance_failed.
        If all are present, emit compliance_passed.
        """
        documents = ucso.get("documents", {}).get("files", [])
        
        # Get the actual type field (handles both 'type' and 'doc_type' variations)
        def get_type(doc):
            return doc.get("type", doc.get("doc_type"))

        # If exactly 1 document is uploaded, treat it as a combined master document
        if len(documents) == 1:
            master_doc = documents[0]
            self.logger.info(
                "Only 1 document found. Expanding it to cover all 4 required types.",
                extra={"agent_name": self.AGENT_NAME, "application_id": application_id},
            )
            
            new_docs = []
            for req_type in REQUIRED_DOC_TYPES:
                doc_copy = master_doc.copy()
                doc_copy["type"] = req_type
                doc_copy["doc_type"] = req_type
                # Ensure it has a unique doc_id
                doc_copy["doc_id"] = f"{req_type}_{master_doc.get('doc_id', 'doc')}"
                new_docs.append(doc_copy)
                
            # Update the application's documents namespace with the 4 expanded files
            self.ucso_client.patch_namespace(application_id, "documents", {"files": new_docs})
            documents = new_docs # Use the expanded list for the check below

        uploaded_types = {
            get_type(doc) for doc in documents if doc.get("s3_key") or doc.get("local_path")
        }

        missing = [
            doc_type for doc_type in REQUIRED_DOC_TYPES
            if doc_type not in uploaded_types
        ]

        if missing:
            self.logger.warning(
                f"Missing documents for {application_id}: {missing}",
                extra={"agent_name": self.AGENT_NAME, "application_id": application_id},
            )
            self.publish_event("compliance_failed", application_id, {
                "missing_documents": missing,
            })
            self.publish_status(application_id, "COMPLETED", error_code="DOCS_MISSING")
            pan = ucso.get("applicant", {}).get("pan", "")
            company = ucso.get("applicant", {}).get("company_name", "")
            compliance_text = (
                f"Compliance check for {company} (PAN: {pan}). "
                f"Status: FAIL. Missing: {missing}"
            )
            vectorai.upsert(
                collection="application_summaries",
                doc_id=f"{application_id}_compliance",
                text=compliance_text,
                metadata={
                    "application_id": application_id,
                    "pan": pan,
                    "agent": self.AGENT_NAME,
                    "status": "FAIL",
                    "phase": "compliance",
                },
            )
            if pan:
                prior = vectorai.hybrid_search(
                    collection="application_summaries",
                    query_text=f"compliance check PAN {pan}",
                    filters={"pan": pan, "phase": "compliance"},
                    top_k=3,
                )
                prior_count = len(
                    [
                        r
                        for r in prior
                        if r.get("metadata", {}).get("application_id") != application_id
                    ]
                )
                if prior_count > 0:
                    self.logger.info(
                        f"Found {prior_count} prior applications from PAN {pan}",
                        extra={"agent_name": self.AGENT_NAME, "application_id": application_id},
                    )
            return {
                "status": "FAIL",
                "missing_documents": missing,
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }
        else:
            self.logger.info(
                f"All required documents present for {application_id}",
                extra={"agent_name": self.AGENT_NAME, "application_id": application_id},
            )
            self.publish_event("compliance_passed", application_id)
            pan = ucso.get("applicant", {}).get("pan", "")
            company = ucso.get("applicant", {}).get("company_name", "")
            compliance_text = (
                f"Compliance check for {company} (PAN: {pan}). "
                "Status: PASS. Missing: []"
            )
            vectorai.upsert(
                collection="application_summaries",
                doc_id=f"{application_id}_compliance",
                text=compliance_text,
                metadata={
                    "application_id": application_id,
                    "pan": pan,
                    "agent": self.AGENT_NAME,
                    "status": "PASS",
                    "phase": "compliance",
                },
            )
            if pan:
                prior = vectorai.hybrid_search(
                    collection="application_summaries",
                    query_text=f"compliance check PAN {pan}",
                    filters={"pan": pan, "phase": "compliance"},
                    top_k=3,
                )
                prior_count = len(
                    [
                        r
                        for r in prior
                        if r.get("metadata", {}).get("application_id") != application_id
                    ]
                )
                if prior_count > 0:
                    self.logger.info(
                        f"Found {prior_count} prior applications from PAN {pan}",
                        extra={"agent_name": self.AGENT_NAME, "application_id": application_id},
                    )
            return {
                "status": "PASS",
                "missing_documents": [],
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }


if __name__ == "__main__":
    agent = ComplianceAgent()
    agent.run()
