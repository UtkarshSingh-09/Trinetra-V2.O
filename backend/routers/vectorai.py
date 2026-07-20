import logging
import os
from fastapi import APIRouter, HTTPException, Depends, Query
import functools
from anyio.to_thread import run_sync
from dependencies import get_current_user_or_agent
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue, MatchAny, Range

router = APIRouter(prefix="/api/vectorai", tags=["VectorAI"])
logger = logging.getLogger("trinetra-backend.vectorai")

_qdrant_client = None
_vectorai_model = None

# Support dynamic fallback to local persistent disk Qdrant
def _get_qdrant_client():
    global _qdrant_client
    if _qdrant_client is None:
        qdrant_url = os.getenv("QDRANT_URL") or os.getenv("VECTORAI_URL", "http://localhost:6333")
        use_local = False
        if "50051" in qdrant_url or ("vectorai" in qdrant_url.lower() and "http" not in qdrant_url.lower()):
            use_local = True

        if use_local:
            _qdrant_client = _init_local_qdrant()
        else:
            try:
                url = qdrant_url
                if not url.startswith("http://") and not url.startswith("https://"):
                    url = f"http://{url}"
                client = QdrantClient(url=url, timeout=5.0)
                client.get_collections()
                _qdrant_client = client
                logger.info(f"✅ Qdrant client connected successfully in backend at {url}.")
            except Exception as e:
                logger.warning(f"⚠️ Qdrant container connection failed in backend: {e}. Switching to Local Disk storage.")
                _qdrant_client = _init_local_qdrant()
    return _qdrant_client

def _init_local_qdrant():
    from config import LOCAL_STORAGE_DIR
    db_path = os.path.join(LOCAL_STORAGE_DIR, "qdrant_db")
    os.makedirs(db_path, exist_ok=True)
    try:
        client = QdrantClient(path=db_path)
        logger.info(f"💾 Qdrant initialized locally in backend persistent disk mode at: {db_path}")
        return client
    except Exception as e:
        logger.warning(f"⚠️ Qdrant backend disk lock failed ({e}). Falling back to in-memory mode for this instance.")
        return QdrantClient(":memory:")

def _get_vectorai_model():
    global _vectorai_model
    if _vectorai_model is None:
        _vectorai_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _vectorai_model

def _embed_query(text: str) -> list[float]:
    return _get_vectorai_model().encode(text).tolist()

def _normalize_search_result(result) -> dict:
    payload = getattr(result, "payload", {})
    return {
        "id": str(getattr(result, "id", None)),
        "score": getattr(result, "score", None),
        "metadata": payload or {},
    }

def _build_qdrant_filter(filters: dict | None) -> Filter | None:
    if not filters:
        return None

    must_conditions = []
    for key, value in filters.items():
        if value is None or value == "":
            continue

        if isinstance(value, dict):
            if "between" in value and isinstance(value["between"], (list, tuple)):
                low, high = value["between"][:2]
                must_conditions.append(
                    FieldCondition(key=key, range=Range(gte=float(low), lte=float(high)))
                )
            elif any(k in value for k in ("gte", "gt", "lte", "lt")):
                must_conditions.append(
                    FieldCondition(
                        key=key,
                        range=Range(
                            gte=float(value["gte"]) if value.get("gte") is not None else None,
                            gt=float(value["gt"]) if value.get("gt") is not None else None,
                            lte=float(value["lte"]) if value.get("lte") is not None else None,
                            lt=float(value["lt"]) if value.get("lt") is not None else None
                        )
                    )
                )
            elif "any_of" in value:
                must_conditions.append(
                    FieldCondition(key=key, match=MatchAny(any=list(value["any_of"])))
                )
        elif isinstance(value, (list, tuple, set)):
            must_conditions.append(
                FieldCondition(key=key, match=MatchAny(any=list(value)))
            )
        else:
            must_conditions.append(
                FieldCondition(key=key, match=MatchValue(value=value))
            )

    if not must_conditions:
        return None

    return Filter(must=must_conditions)

VECTORAI_COLLECTIONS = [
    {"name": "document_chunks", "icon": "📄", "label": "Document Chunks", "owner": "doc-agent"},
    {"name": "financial_profiles", "icon": "💰", "label": "Financial Profiles", "owner": "doc-agent"},
    {"name": "gst_patterns", "icon": "📊", "label": "GST Patterns", "owner": "gst-agent"},
    {"name": "bank_recon_profiles", "icon": "🏦", "label": "Bank Reconciliation", "owner": "bank-recon-agent"},
    {"name": "news_articles", "icon": "📰", "label": "News Articles", "owner": "web-agent"},
    {"name": "litigation_records", "icon": "⚖️", "label": "Litigation Records", "owner": "web-agent"},
    {"name": "rbi_circulars", "icon": "🏛️", "label": "RBI Circulars", "owner": "web-agent"},
    {"name": "mca_filings", "icon": "🏢", "label": "MCA Filings", "owner": "mca-agent"},
    {"name": "pan_profiles", "icon": "🆔", "label": "PAN Profiles", "owner": "pan-agent"},
    {"name": "risk_decisions", "icon": "⚠️", "label": "Risk Decisions", "owner": "risk-agent"},
    {"name": "pd_transcripts", "icon": "🎤", "label": "PD Transcripts", "owner": "pd-agent"},
    {"name": "stress_scenarios", "icon": "📈", "label": "Stress Scenarios", "owner": "stress-agent"},
    {"name": "audit_events", "icon": "🔍", "label": "Audit Events", "owner": "monitor-agent"},
    {"name": "application_summaries", "icon": "📋", "label": "Application Summaries", "owner": "all-agents"},
]

@router.get("/collections")
async def vectorai_collections(current_user: dict = Depends(get_current_user_or_agent)):
    """Return metadata for all 14 vector database collections."""
    return {"collections": VECTORAI_COLLECTIONS, "count": len(VECTORAI_COLLECTIONS)}

@router.get("/search")
async def vectorai_search(
    q: str = Query(..., description="Semantic query text"),
    collection: str = Query("news_articles", description="Collection to search"),
    top_k: int = Query(5, ge=1, le=20),
    current_user: dict = Depends(get_current_user_or_agent),
):
    """Semantic search across any Qdrant collection."""
    try:
        client = _get_qdrant_client()
        query_vector = await run_sync(_embed_query, q)
        
        # Ensure collection exists
        exists = await run_sync(functools.partial(client.collection_exists, collection_name=collection))
        if not exists:
            await run_sync(
                functools.partial(
                    client.create_collection,
                    collection_name=collection,
                    vectors_config=VectorParams(size=384, distance=Distance.COSINE)
                )
            )

        response = await run_sync(
            functools.partial(
                client.query_points,
                collection_name=collection,
                query=query_vector,
                limit=top_k
            )
        )
        results = [_normalize_search_result(r) for r in response.points]
        return {"query": q, "collection": collection, "top_k": top_k, "results": results}
    except Exception as e:
        logger.error(f"Qdrant search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Qdrant search failed: {str(e)}")

@router.post("/hybrid-search")
async def vectorai_hybrid_search(body: dict, current_user: dict = Depends(get_current_user_or_agent)):
    """Hybrid search: vector similarity + metadata Qdrant filters."""
    try:
        client = _get_qdrant_client()
        query_text = body.get("query", "")
        collection = body.get("collection", "news_articles")
        top_k = body.get("top_k", 5)
        filter_obj = _build_qdrant_filter(body.get("filters", {}))

        # Ensure collection exists
        exists = await run_sync(functools.partial(client.collection_exists, collection_name=collection))
        if not exists:
            await run_sync(
                functools.partial(
                    client.create_collection,
                    collection_name=collection,
                    vectors_config=VectorParams(size=384, distance=Distance.COSINE)
                )
            )

        query_vector = await run_sync(_embed_query, query_text)
        response = await run_sync(
            functools.partial(
                client.query_points,
                collection_name=collection,
                query=query_vector,
                limit=top_k,
                query_filter=filter_obj
            )
        )
        results = [_normalize_search_result(r) for r in response.points]
        return {"results": results, "filters": body.get("filters", {})}
    except Exception as e:
        logger.error(f"Qdrant hybrid search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Qdrant hybrid search failed: {str(e)}")
