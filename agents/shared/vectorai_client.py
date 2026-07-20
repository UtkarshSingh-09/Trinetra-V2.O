"""
Trinetra Shared Vector DB Client (Powered by Qdrant).
Maintains identical interface signatures (VectorAIClient) so that the 13 agents don't break,
but connects to Qdrant under the hood.
"""
import os
import uuid
import json
from datetime import datetime, timezone
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue, MatchAny, Range
from .logger import get_logger

logger = get_logger("vectorai-client")

# Namespace UUID for deterministic uuid5 generation from string doc_ids
_TRINETRA_NS = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")

def _to_uuid(doc_id: str) -> str:
    """Convert any string doc_id to a valid UUID string (deterministic)."""
    try:
        uuid.UUID(doc_id)
        return doc_id  # already a valid UUID
    except (ValueError, AttributeError):
        return str(uuid.uuid5(_TRINETRA_NS, doc_id))

# Support both environment variables
VECTORAI_URL = os.getenv("QDRANT_URL") or os.getenv("VECTORAI_URL", "http://localhost:6333")
VECTORAI_EMBEDDING_MODEL = os.getenv("VECTORAI_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
VECTORAI_EMBEDDING_DIM = int(os.getenv("VECTORAI_EMBEDDING_DIM", "384"))

_model = None

def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(VECTORAI_EMBEDDING_MODEL)
    return _model

def _normalize_result(result) -> dict:
    payload = getattr(result, "payload", {})
    return {
        "id": str(getattr(result, "id", None)),
        "score": getattr(result, "score", None),
        "metadata": payload or {},
    }

def _build_filter(filters: dict | None) -> Filter | None:
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
                    FieldCondition(
                        key=key,
                        range=Range(gte=float(low), lte=float(high))
                    )
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
                    FieldCondition(
                        key=key,
                        match=MatchAny(any=list(value["any_of"]))
                    )
                )
        elif isinstance(value, (list, tuple, set)):
            must_conditions.append(
                FieldCondition(
                    key=key,
                    match=MatchAny(any=list(value))
                )
            )
        else:
            must_conditions.append(
                FieldCondition(
                    key=key,
                    match=MatchValue(value=value)
                )
            )

    if not must_conditions:
        return None

    return Filter(must=must_conditions)


class VectorAIClient:
    def __init__(self):
        self.base_url = VECTORAI_URL
        self.mock_mode = False
        
        # Check if we should fall back to local disk storage
        # If the URL looks like legacy gRPC (50051) or starts with vectorai without http, Qdrant will fail.
        # So we check if we should run local SQLite-based Qdrant.
        use_local = False
        url = self.base_url
        if "50051" in url or ("vectorai" in url.lower() and "http" not in url.lower()):
            logger.warning(f"⚠️ Legacy Vector URL detected ({url}). Switching to Qdrant Local Disk storage.")
            use_local = True

        if use_local:
            self._init_local()
        else:
            try:
                # Ensure the url has http/https prefix
                if not url.startswith("http://") and not url.startswith("https://"):
                    url = f"http://{url}"
                # Qdrant client connection
                self._client = QdrantClient(url=url, timeout=5.0)
                # Quick health check test call
                self._client.get_collections()
                logger.info(f"✅ Qdrant client connected successfully to container at {url}.")
            except Exception as e:
                logger.warning(f"⚠️ Qdrant container connection failed ({e}). Switching to Qdrant Local Disk storage.")
                self._init_local()

    def _init_local(self):
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        db_dir = os.getenv("LOCAL_STORAGE_DIR") or os.path.join(root_dir, "local_storage")
        db_path = os.path.join(db_dir, "qdrant_db")
        os.makedirs(db_path, exist_ok=True)
        try:
            self._client = QdrantClient(path=db_path)
            logger.info(f"💾 Qdrant initialized locally in persistent disk mode at: {db_path}")
        except Exception as e:
            logger.warning(f"⚠️ Qdrant disk lock failed ({e}). Falling back to in-memory mode for this instance.")
            self._client = QdrantClient(":memory:")

    def embed(self, text: str) -> list[float]:
        try:
            return _get_model().encode(text).tolist()
        except Exception as e:
            logger.warning(f"Embedding failed: {e}. Returning zero vector.")
            return [0.0] * VECTORAI_EMBEDDING_DIM

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        try:
            return _get_model().encode(texts).tolist()
        except Exception as e:
            logger.warning(f"Batch embedding failed: {e}. Returning zero vectors.")
            return [[0.0] * VECTORAI_EMBEDDING_DIM for _ in texts]

    def create_collection(self, name: str, metadata_schema: dict | None = None) -> bool:
        try:
            if self._client.collection_exists(collection_name=name):
                return True
            self._client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(size=VECTORAI_EMBEDDING_DIM, distance=Distance.COSINE),
            )
            return True
        except Exception as e:
            logger.error(f"create_collection failed [{name}]: {e}")
            return False

    def upsert(self, collection: str, doc_id: str, text: str, metadata: dict | None = None) -> bool:
        embedding = self.embed(text)
        return self.upsert_raw(collection, doc_id, embedding, metadata or {})

    def upsert_raw(self, collection: str, doc_id: str, embedding: list[float], metadata: dict) -> bool:
        payload = {
            **metadata,
            "indexed_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            # Auto-create collection if missing
            self.create_collection(collection)
            self._client.upsert(
                collection_name=collection,
                points=[
                    PointStruct(
                        id=_to_uuid(doc_id),
                        vector=embedding,
                        payload=payload
                    )
                ]
            )
            return True
        except Exception as e:
            logger.error(f"upsert failed [{collection}/{doc_id}]: {e}")
            return False

    def upsert_batch(self, collection: str, documents: list[dict]) -> bool:
        if not documents:
            return True

        texts = [d.get("text", "") for d in documents]
        embeddings = self.embed_batch(texts)
        points = [
            PointStruct(
                id=_to_uuid(d.get("id", str(uuid.uuid4()))),
                vector=emb,
                payload={
                    **d.get("metadata", {}),
                    "indexed_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            for d, emb in zip(documents, embeddings)
        ]

        try:
            self.create_collection(collection)
            self._client.upsert(collection_name=collection, points=points)
            return True
        except Exception as e:
            logger.error(f"upsert_batch failed [{collection}]: {e}")
            return False

    def search(self, collection: str, query_text: str, top_k: int = 5, min_score: float = 0.0) -> list[dict]:
        query_embedding = self.embed(query_text)
        return self.search_raw(collection, query_embedding, top_k, min_score)

    def search_raw(
        self,
        collection: str,
        query_vector: list[float],
        top_k: int = 5,
        min_score: float = 0.0,
        filters: dict | None = None,
    ) -> list[dict]:
        try:
            filter_obj = _build_filter(filters) if filters else None
            if hasattr(self._client, "search"):
                results = self._client.search(
                    collection_name=collection,
                    query_vector=query_vector,
                    limit=top_k,
                    score_threshold=min_score if min_score > 0 else None,
                    query_filter=filter_obj
                )
            else:
                response = self._client.query_points(
                    collection_name=collection,
                    query=query_vector,
                    limit=top_k,
                    score_threshold=min_score if min_score > 0 else None,
                    query_filter=filter_obj
                )
                results = response.points
            return [_normalize_result(result) for result in results]
        except Exception as e:
            logger.error(f"search failed [{collection}]: {e}")
            return []

    def hybrid_search(self, collection: str, query_text: str, filters: dict, top_k: int = 5) -> list[dict]:
        query_embedding = self.embed(query_text)
        return self.search_raw(collection, query_embedding, top_k, 0.0, filters)