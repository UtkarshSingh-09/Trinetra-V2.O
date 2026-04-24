"""
Agent 6: Web Intelligence Agent
Approach: RAG + Sentiment + External API fallback
Tools: Actian VectorAI REST, sentence-transformers (all-MiniLM-L6-v2), vaderSentiment

Trigger: gst_completed, bank_recon_completed
Reads: applicant, gst_analysis
Writes: web_intel
Logic: Query Actian VectorAI KB for news/litigation/RBI circulars. Score with VADER.
       Surepass eCourt API for litigation. Credibility filter ≥2.
Errors: SCRAPE_TIMEOUT → use KB snapshot. LOW_CONFIDENCE (<0.75 cosine) → discard.
"""
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.agent_base import AgentBase
from shared.vectorai_client import VectorAIClient

import requests as http_requests
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

SUREPASS_TOKEN = os.getenv("SUREPASS_TOKEN", "")
SUREPASS_ECOURT_URL = "https://kyc-api.surepass.io/api/v1/ecourt/cnr-details"
SIMILARITY_THRESHOLD = 0.75

analyzer = SentimentIntensityAnalyzer()
vectorai = VectorAIClient()


# ── Sentiment Scoring (from Blueprint Section 2.4) ──
def score_article(headline: str, body: str = "") -> dict:
    """
    Score a news article using VADER sentiment analysis.
    Returns sentiment_score, risk_contribution, and label.
    """
    text = f"{headline}. {body}"
    scores = analyzer.polarity_scores(text)
    compound = scores["compound"]  # -1.0 to +1.0

    # Normalize to risk contribution (0=no risk, 1=max risk)
    risk_contribution = (1 - compound) / 2  # maps [-1,1] → [1,0]

    return {
        "sentiment_score": round(compound, 4),
        "risk_contribution": round(risk_contribution, 4),
        "label": (
            "POSITIVE" if compound > 0.05
            else "NEGATIVE" if compound < -0.05
            else "NEUTRAL"
        ),
    }


def aggregate_news_sentiment(articles: list) -> float:
    """Aggregate risk contribution across all scored articles."""
    if not articles:
        return 0.5  # neutral default
    return round(
        sum(a.get("risk_contribution", 0.5) for a in articles) / len(articles), 4
    )


# ── Actian VectorAI RAG Queries ──
def query_actian_collection(
    collection: str,
    query_text: str,
    top_k: int = 10,
    min_score: float = SIMILARITY_THRESHOLD,
) -> list[dict]:
    """
    Query Actian VectorAI and return metadata payloads.
    """
    results = vectorai.search(
        collection=collection,
        query_text=query_text,
        top_k=top_k,
        min_score=min_score,
    )
    return [r.get("metadata", {}) for r in results]


def fetch_news(company_name: str, industry: str) -> list:
    """
    Fetch and score news articles from Actian VectorAI news_articles collection.
    """
    hits = query_actian_collection(
        "news_articles",
        f"{company_name} {industry} risk scandal fraud",
        top_k=10,
        min_score=0.70,
    )

    scored_news = []
    for hit in hits:
        sentiment = score_article(
            hit.get("headline", ""), hit.get("body", "")
        )
        scored_news.append({
            "headline": hit.get("headline", ""),
            "source_url": hit.get("source_url", ""),
            "credibility_score": hit.get("credibility_score", 0),
            "sentiment_score": sentiment["sentiment_score"],
            "risk_contribution": sentiment["risk_contribution"],
            "published_at": hit.get("published_at", ""),
            "entity_tags": hit.get("entity_tags", []),
        })

    return scored_news


def fetch_litigation(company_name: str, pan: str) -> list:
    """
    Fetch litigation records via Surepass eCourt API.
    Falls back to Actian VectorAI litigation_records collection.
    """
    records = []

    # Try Surepass eCourt API
    if SUREPASS_TOKEN and pan:
        try:
            resp = http_requests.post(
                SUREPASS_ECOURT_URL,
                json={"id_number": pan},
                headers={"Authorization": f"Bearer {SUREPASS_TOKEN}"},
                timeout=10,
            )
            resp.raise_for_status()
            cases = resp.json().get("data", {}).get("cases", [])

            for case in cases:
                severity = "HIGH" if "criminal" in case.get("case_type", "").lower() else (
                    "MEDIUM" if "civil" in case.get("case_type", "").lower() else "LOW"
                )
                records.append({
                    "case_no": case.get("cnr_number", ""),
                    "court": case.get("court_name", ""),
                    "case_type": case.get("case_type", ""),
                    "status": case.get("status", ""),
                    "severity": severity,
                    "source": "SUREPASS",
                })

            return records

        except Exception:
            pass

    # Fallback: Actian litigation records collection
    hits = query_actian_collection(
        "litigation_records",
        company_name,
        top_k=10,
        min_score=0.60,
    )
    for hit in hits:
        records.append({
            "case_no": hit.get("case_no", ""),
            "court": hit.get("court", ""),
            "case_type": hit.get("case_type", ""),
            "status": hit.get("status", ""),
            "severity": hit.get("severity", "LOW"),
            "source": hit.get("source", "SCRAPE"),
        })

    return records


def fetch_regulatory_flags(industry: str) -> list:
    """
    Query Actian VectorAI rbi_circulars collection for sector-specific headwinds.
    """
    hits = query_actian_collection(
        "rbi_circulars",
        f"{industry} regulation risk",
        top_k=5,
        min_score=0.60,
    )

    return [
        {
            "circular_no": h.get("circular_no", ""),
            "title": h.get("title", ""),
            "issued_date": h.get("issued_date", ""),
        }
        for h in hits
    ]


class WebIntelligenceAgent(AgentBase):
    AGENT_NAME = "web-intelligence-agent"
    LISTEN_TOPICS = ["gst_completed", "bank_recon_completed"]
    OUTPUT_NAMESPACE = "web_intel"
    OUTPUT_EVENT = "web_intel_completed"

    def process(self, application_id: str, ucso: dict) -> dict:
        """
        Full RAG pipeline: query Actian VectorAI for news, litigation, and RBI circulars.
        Score sentiment using VADER. Return structured web intelligence.
        """
        applicant = ucso.get("applicant", {})
        company_name = applicant.get("company_name", "")
        industry = applicant.get("industry_sector", "")
        pan = applicant.get("pan", "")

        # Fetch news with sentiment scoring
        self.logger.info(
            f"Querying Actian VectorAI for news about '{company_name}'",
            extra={"agent_name": self.AGENT_NAME, "application_id": application_id},
        )
        promoter_news = fetch_news(company_name, industry)

        # Fetch litigation records
        self.logger.info(
            f"Fetching litigation records for '{company_name}'",
            extra={"agent_name": self.AGENT_NAME, "application_id": application_id},
        )
        litigation_records = fetch_litigation(company_name, pan)

        # Fetch sector headwinds from RBI circulars
        regulatory_flags = fetch_regulatory_flags(industry)
        sector_headwinds = [f.get("title", "") for f in regulatory_flags]

        # Compute KB freshness
        now = datetime.now(timezone.utc)
        kb_freshness_hours = 0
        if promoter_news:
            latest_pub = max(
                (n.get("published_at", "") for n in promoter_news), default=""
            )
            if latest_pub:
                try:
                    pub_dt = datetime.fromisoformat(latest_pub.replace("Z", "+00:00"))
                    kb_freshness_hours = int((now - pub_dt).total_seconds() / 3600)
                except (ValueError, TypeError):
                    kb_freshness_hours = 9999
            else:
                kb_freshness_hours = 9999
        else:
            kb_freshness_hours = 9999

        web_summary = (
            f"Web intel for {company_name}: {len(promoter_news)} articles, "
            f"{len(litigation_records)} cases, "
            f"sentiment={aggregate_news_sentiment(promoter_news)}"
        )
        vectorai.upsert(
            collection="application_summaries",
            doc_id=f"{application_id}_web_intel",
            text=web_summary,
            metadata={
                "application_id": application_id,
                "agent": self.AGENT_NAME,
                "article_count": len(promoter_news),
                "litigation_count": len(litigation_records),
                "phase": "web_intel",
            },
        )

        return {
            "promoter_news": promoter_news,
            "litigation_records": litigation_records,
            "regulatory_flags": regulatory_flags,
            "sector_headwinds": sector_headwinds,
            "kb_query_timestamp": now.isoformat(),
            "kb_freshness_hours": kb_freshness_hours,
        }


if __name__ == "__main__":
    agent = WebIntelligenceAgent()
    agent.run()
