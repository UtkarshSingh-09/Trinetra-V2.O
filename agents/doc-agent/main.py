"""
Agent 2: Document Intelligence Agent
Approach: OCR (Optical Character Recognition) + Pattern Matching
Tools: pdfplumber (digital text), pytesseract (scanned), re (Indian number parsing)

Trigger: docs_uploaded, compliance_passed
Reads: documents (S3 keys)
Writes: documents, financials
Errors: PARSE_LOW_CONF (<0.6) → flag for human review. PARSE_FAIL → retry alternate parser.
"""
import sys
import os
import re
import json
import tempfile
import uuid as uuid_mod

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.agent_base import AgentBase
from shared.vectorai_client import VectorAIClient

import pdfplumber
import pytesseract
from PIL import Image
import requests as http_requests


vectorai = VectorAIClient()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


# ── Indian Number Normalizer ──
def normalize_indian_number(text: str) -> float:
    """
    Convert Indian formatted numbers to float.
    Handles: ₹, commas (lakh/crore style), 'Cr', 'Lakh', etc.

    Examples:
        '₹45,00,000'    -> 4500000.0
        '₹6.5 Cr'       -> 65000000.0
        '28 Lakh'        -> 2800000.0
        '1,23,45,678.90' -> 12345678.90
    """
    if not text:
        return 0.0

    text = text.strip().replace("₹", "").replace(",", "").strip()

    # Handle 'Cr' / 'Crore' multiplier
    cr_match = re.search(r"([\d.]+)\s*(cr|crore)", text, re.IGNORECASE)
    if cr_match:
        return float(cr_match.group(1)) * 1e7

    # Handle 'Lakh' / 'L' multiplier
    lakh_match = re.search(r"([\d.]+)\s*(lakh|lac|l)\b", text, re.IGNORECASE)
    if lakh_match:
        return float(lakh_match.group(1)) * 1e5

    # Plain number
    try:
        return float(text)
    except ValueError:
        return 0.0


# ── Financial Field Extraction Patterns ──
FINANCIAL_PATTERNS = {
    "revenue": [
        r"(?:total\s+)?revenue\s*(?:from\s+operations)?\s*[:\-]?\s*([\d₹,.]+\s*(?:cr|crore|lakh|lac)?)",
        r"turnover\s*[:\-]?\s*([\d₹,.]+\s*(?:cr|crore|lakh|lac)?)",
        r"net\s+sales\s*[:\-]?\s*([\d₹,.]+\s*(?:cr|crore|lakh|lac)?)",
    ],
    "ebitda": [
        r"ebitda\s*[:\-]?\s*([\d₹,.]+\s*(?:cr|crore|lakh|lac)?)",
        r"operating\s+profit\s*[:\-]?\s*([\d₹,.]+\s*(?:cr|crore|lakh|lac)?)",
    ],
    "net_profit": [
        r"(?:net\s+)?profit\s+(?:after\s+tax|for\s+the\s+year)\s*[:\-]?\s*([\d₹,.]+\s*(?:cr|crore|lakh|lac)?)",
        r"pat\s*[:\-]?\s*([\d₹,.]+\s*(?:cr|crore|lakh|lac)?)",
    ],
    "total_debt": [
        r"total\s+(?:borrowings?|debt)\s*[:\-]?\s*([\d₹,.]+\s*(?:cr|crore|lakh|lac)?)",
        r"long\s+term\s+borrowings?\s*[:\-]?\s*([\d₹,.]+\s*(?:cr|crore|lakh|lac)?)",
    ],
    "net_worth": [
        r"net\s+worth\s*[:\-]?\s*([\d₹,.]+\s*(?:cr|crore|lakh|lac)?)",
        r"shareholders?\s*(?:\'s)?\s+funds?\s*[:\-]?\s*([\d₹,.]+\s*(?:cr|crore|lakh|lac)?)",
    ],
    "interest_expense": [
        r"(?:interest|finance)\s+(?:expense|cost)\s*[:\-]?\s*([\d₹,.]+\s*(?:cr|crore|lakh|lac)?)",
    ],
    "taxable_income": [
        r"taxable\s+income\s*[:\-]?\s*([\d₹,.]+\s*(?:cr|crore|lakh|lac)?)",
    ],
    "cibil_score": [
        r"cibil\s*(?:score)?\s*[:\-]?\s*(\d{3})",
        r"credit\s+score\s*[:\-]?\s*(\d{3})",
    ],
}


def extract_text_from_pdf(file_path: str) -> tuple:
    """
    Extract text from a PDF using pdfplumber (digital) with Tesseract OCR fallback.

    Returns:
        (full_text: str, confidence: float, method: str)
    """
    full_text = ""
    confidence = 0.0

    # Try digital extraction first
    try:
        with pdfplumber.open(file_path) as pdf:
            pages_text = []
            for page in pdf.pages:
                text = page.extract_text() or ""
                pages_text.append(text)
            full_text = "\n".join(pages_text)

        if len(full_text.strip()) > 100:
            # Good digital extraction
            confidence = 0.95
            return full_text, confidence, "pdfplumber"
    except Exception:
        pass

    # Fallback to OCR (scanned PDFs)
    try:
        with pdfplumber.open(file_path) as pdf:
            pages_text = []
            for page in pdf.pages:
                img = page.to_image(resolution=300).original
                ocr_text = pytesseract.image_to_string(img, lang="eng")
                pages_text.append(ocr_text)
            full_text = "\n".join(pages_text)

        if len(full_text.strip()) > 50:
            confidence = 0.70
            return full_text, confidence, "tesseract"
        else:
            confidence = 0.30
            return full_text, confidence, "tesseract_low"
    except Exception as e:
        return f"PARSE_FAIL: {str(e)}", 0.0, "failed"


def extract_financials(text: str) -> dict:
    """
    Extract financial fields from text using regex patterns.
    Returns a dict of field_name -> normalized float value.
    """
    results = {}
    for field, patterns in FINANCIAL_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                raw_value = match.group(1)
                results[field] = normalize_indian_number(raw_value)
                break
    return results


def _to_float(value) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return normalize_indian_number(value)
    return 0.0


def extract_financials_with_llm(text: str) -> dict:
    """Use Groq LLM to extract financial data from document text."""
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY missing")

    prompt = (
        "Extract the EXACT financial values from the document text. "
        "Do NOT make up or estimate values. "
        "Return only valid JSON with these keys: "
        "revenue, ebitda, net_profit, total_debt, net_worth, interest_expense, "
        "principal_repayment, operating_expenses, cibil_score, promoter_holding_pct, "
        "pledged_shares_pct, working_capital_cycle_days. "
        "Use null when unavailable. Values may include units like Cr/Lakh if present."
    )

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": (text or "")[:6000]},
        ],
        "temperature": 0.0,
        "response_format": {"type": "json_object"},
    }

    response = http_requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=35)
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    data = json.loads(content)

    fields = [
        "revenue",
        "ebitda",
        "net_profit",
        "total_debt",
        "net_worth",
        "interest_expense",
        "principal_repayment",
        "operating_expenses",
        "cibil_score",
        "promoter_holding_pct",
        "pledged_shares_pct",
        "working_capital_cycle_days",
    ]

    cleaned = {}
    for key in fields:
        cleaned[key] = _to_float(data.get(key))
    return cleaned


def compute_derived_features(financials: dict) -> dict:
    """Compute DSCR/ICR/Leverage/EBITDA margin/revenue growth from extracted financials."""
    revenue = _to_float(financials.get("revenue"))
    ebitda = _to_float(financials.get("ebitda"))
    total_debt = _to_float(financials.get("total_debt"))
    net_worth = _to_float(financials.get("net_worth"))
    interest_expense = _to_float(financials.get("interest_expense"))
    principal_repayment = _to_float(financials.get("principal_repayment"))
    operating_expenses = _to_float(financials.get("operating_expenses"))
    ccc = _to_float(financials.get("working_capital_cycle_days"))

    if operating_expenses <= 0 and revenue > 0 and ebitda > 0:
        operating_expenses = max(0.0, revenue - ebitda)

    noi = max(0.0, revenue - operating_expenses)
    total_debt_service = interest_expense + principal_repayment

    dscr = (noi / total_debt_service) if total_debt_service > 0 else 0.0
    icr = (ebitda / interest_expense) if interest_expense > 0 else 0.0
    leverage = (total_debt / net_worth) if net_worth > 0 else 0.0
    ebitda_margin = (ebitda / revenue) if revenue > 0 else 0.0

    return {
        "dscr": round(dscr, 4),
        "icr": round(icr, 4),
        "leverage": round(leverage, 4),
        "ebitda_margin": round(ebitda_margin, 4),
        "revenue_growth": 0.0,
        "ccc": round(ccc, 2),
    }


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 100) -> list[dict]:
    """Split text into overlapping chunks for vector indexing."""
    chunks = []
    start = 0
    chunk_num = 0
    step = max(1, chunk_size - overlap)
    while start < len(text):
        end = min(start + chunk_size, len(text))
        segment = text[start:end]
        if len(segment.strip()) > 50:
            chunks.append(
                {
                    "text": segment,
                    "chunk_num": chunk_num,
                    "start_char": start,
                    "end_char": end,
                }
            )
            chunk_num += 1
        start += step
    return chunks


class DocIntelligenceAgent(AgentBase):
    AGENT_NAME = "doc-intelligence-agent"
    LISTEN_TOPICS = ["docs_uploaded", "compliance_passed"]
    OUTPUT_NAMESPACE = "documents"
    OUTPUT_EVENT = "parsing_completed"

    def process(self, application_id: str, ucso: dict) -> dict:
        """
        Parse all uploaded PDFs. Extract financials with confidence + provenance.
        Normalize Indian numbers. PATCH documents + financials namespaces.
        """
        documents = ucso.get("documents", {}).get("files", [])
        aggregated_financials = {}
        updated_files = []

        for doc in documents:
            if doc.get("parsed"):
                updated_files.append(doc)
                continue

            # Determine how to get the file
            local_path = doc.get("local_path", "")
            s3_key = doc.get("s3_key", "")
            doc_id = doc.get("doc_id", doc.get("doc_type", "unknown"))

            if not s3_key and not local_path:
                updated_files.append(doc)
                continue

            try:
                tmp_path = None

                if local_path and os.path.exists(local_path):
                    # Local file (for testing)
                    tmp_path = local_path
                else:
                    # Download from backend API
                    file_url = f"{self.ucso_client.base_url}/api/files/{application_id}"
                    self.logger.info(
                        f"Downloading file from {file_url}",
                        extra={"agent_name": self.AGENT_NAME, "application_id": application_id},
                    )
                    resp = http_requests.get(file_url, timeout=60)
                    resp.raise_for_status()

                    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                        tmp.write(resp.content)
                        tmp_path = tmp.name

                # Extract text
                text, confidence, method = extract_text_from_pdf(tmp_path)

                # Extract financial fields via LLM. Fallback to regex only if LLM call fails.
                try:
                    extracted = extract_financials_with_llm(text)
                    method = f"{method}+groq"
                except Exception as llm_error:
                    self.logger.warning(
                        f"Groq extraction failed for doc {doc_id}, falling back to regex: {llm_error}",
                        extra={"agent_name": self.AGENT_NAME, "application_id": application_id},
                    )
                    extracted = extract_financials(text)

                # Update document record
                doc["parsed"] = True
                doc["confidence"] = confidence
                doc["extracted_fields"] = extracted
                doc["provenance"] = {
                    "page": 1,
                    "section": f"Extracted via {method}",
                }
                doc.setdefault("parse_errors", [])

                if confidence < 0.6:
                    doc["parse_errors"].append(
                        f"PARSE_LOW_CONF: confidence={confidence}, method={method}"
                    )
                    self.logger.warning(
                        f"Low confidence ({confidence}) for doc {doc_id}",
                        extra={"agent_name": self.AGENT_NAME, "application_id": application_id},
                    )

                # Merge into aggregated financials
                for k, v in extracted.items():
                    if k not in aggregated_financials or v > 0:
                        aggregated_financials[k] = v

                if text and confidence >= 0.5:
                    chunks = chunk_text(text)
                    batch_docs = []
                    for chunk in chunks:
                        batch_docs.append(
                            {
                                "id": (
                                    f"{application_id}_{doc_id}_"
                                    f"{uuid_mod.uuid4().hex[:8]}_chunk{chunk['chunk_num']}"
                                ),
                                "text": chunk["text"],
                                "metadata": {
                                    "application_id": application_id,
                                    "doc_id": doc_id,
                                    "doc_type": doc.get("type", doc.get("doc_type", "UNKNOWN")),
                                    "chunk_num": chunk["chunk_num"],
                                    "start_char": chunk["start_char"],
                                    "end_char": chunk["end_char"],
                                    "confidence": confidence,
                                    "method": method,
                                    "text_preview": chunk["text"][:160],
                                },
                            }
                        )
                    if batch_docs:
                        vectorai.upsert_batch("document_chunks", batch_docs)
                        self.logger.info(
                            f"Indexed {len(batch_docs)} chunks into Actian VectorAI for doc {doc_id}",
                            extra={"agent_name": self.AGENT_NAME, "application_id": application_id},
                        )

                # Clean up temp file (only if we downloaded it)
                if tmp_path != local_path and tmp_path:
                    os.unlink(tmp_path)

                self.logger.info(
                    f"Parsed {doc_id}: {len(extracted)} fields, confidence={confidence:.2f}, method={method}",
                    extra={"agent_name": self.AGENT_NAME, "application_id": application_id},
                )

            except Exception as e:
                self.logger.error(
                    f"Failed to parse doc {doc_id}: {e}",
                    extra={"agent_name": self.AGENT_NAME, "application_id": application_id},
                )
                doc.setdefault("parse_errors", [])
                doc["parse_errors"].append(f"PARSE_FAIL: {str(e)}")

            updated_files.append(doc)

        # PATCH financials namespace separately
        if aggregated_financials:
            financials_patch = {}
            field_map = {
                "revenue": "revenue_annual",
                "ebitda": "ebitda_annual",
                "net_profit": "net_profit_annual",
                "total_debt": "total_debt",
                "net_worth": "net_worth",
                "interest_expense": "interest_expense",
                "principal_repayment": "principal_repayment",
                "operating_expenses": "operating_expenses",
                "taxable_income": "itr_taxable_income",
                "cibil_score": "cibil_score",
                "promoter_holding_pct": "promoter_holding_pct",
                "pledged_shares_pct": "pledged_shares_pct",
                "working_capital_cycle_days": "ccc",
            }
            for src, dest in field_map.items():
                if src in aggregated_financials:
                    val = aggregated_financials[src]
                    if dest.endswith("_annual"):
                        financials_patch[dest] = [val]
                    else:
                        financials_patch[dest] = val

            self.ucso_client.patch_namespace(
                application_id, "financials", financials_patch
            )

            derived_patch = compute_derived_features(aggregated_financials)
            self.ucso_client.patch_namespace(
                application_id, "derived_features", derived_patch
            )

            fin_summary = " ".join([f"{k}={v}" for k, v in aggregated_financials.items()])
            vectorai.upsert(
                collection="financial_profiles",
                doc_id=f"{application_id}_financials",
                text=f"Financial profile: {fin_summary}",
                metadata={
                    "application_id": application_id,
                    "agent": self.AGENT_NAME,
                    **{k: float(v) for k, v in aggregated_financials.items()},
                },
            )

        return {"files": updated_files}


if __name__ == "__main__":
    agent = DocIntelligenceAgent()
    agent.run()
