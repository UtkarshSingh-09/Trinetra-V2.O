"""
Trinetra x Actian VectorAI client (beta SDK).
Shared across agents for embedding + upsert + semantic/hybrid search.
"""
import os
import uuid
from datetime import datetime, timezone

from actian_vectorai import (
    Distance,
    Field,
    FilterBuilder,
    PointStruct,
    VectorAIClient as ActianVectorAIClient,
    VectorParams,
)
from sentence_transformers import SentenceTransformer

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

VECTORAI_URL = os.getenv("VECTORAI_URL", "localhost:50051")
VECTORAI_EMBEDDING_MODEL = os.getenv("VECTORAI_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
VECTORAI_EMBEDDING_DIM = int(os.getenv("VECTORAI_EMBEDDING_DIM", "384"))

_model = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(VECTORAI_EMBEDDING_MODEL)
    return _model


def _normalize_result(result) -> dict:
    payload = getattr(result, "payload", None)
    if payload is None:
        payload = getattr(result, "metadata", None)
    if payload is None and isinstance(result, dict):
        payload = result.get("payload") or result.get("metadata") or {}
    return {
        "id": getattr(result, "id", None) if not isinstance(result, dict) else result.get("id"),
        "score": getattr(result, "score", None) if not isinstance(result, dict) else result.get("score"),
        "metadata": payload or {},
    }


def _build_filter(filters: dict | None):
    if not filters:
        return None

    builder = FilterBuilder()
    for key, value in filters.items():
        if value is None or value == "":
            continue

        condition = None
        field = Field(key)

        if isinstance(value, dict):
            if "between" in value and isinstance(value["between"], (list, tuple)):
                lower, upper = value["between"][:2]
                condition = field.between(lower, upper)
            elif any(k in value for k in ("gte", "gt", "lte", "lt")):
                condition = field.range(
                    gte=value.get("gte"),
                    gt=value.get("gt"),
                    lte=value.get("lte"),
                    lt=value.get("lt"),
                )
            elif "any_of" in value:
                condition = field.any_of(list(value["any_of"]))
            elif "except_of" in value:
                condition = field.except_of(list(value["except_of"]))
            else:
                for nested_key, nested_value in value.items():
                    builder.must(Field(f"{key}.{nested_key}").eq(nested_value))
                continue
        elif isinstance(value, (list, tuple, set)):
            condition = field.any_of(list(value))
        else:
            condition = field.eq(value)

        if condition is not None:
            builder.must(condition)

    return builder.build()


class VectorAIClient:
    def __init__(self):
        self.base_url = VECTORAI_URL
        self._client = ActianVectorAIClient(self.base_url)
        self._client.connect()

    def embed(self, text: str) -> list[float]:
        return _get_model().encode(text).tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return _get_model().encode(texts).tolist()

    def create_collection(self, name: str, metadata_schema: dict | None = None) -> bool:
        try:
            if self._client.collections.exists(name):
                return True
            self._client.collections.create(
                name,
                vectors_config=VectorParams(size=VECTORAI_EMBEDDING_DIM, distance=Distance.Cosine),
                metadata_schema=metadata_schema or {},
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
            self._client.points.upsert(
                collection,
                [PointStruct(id=_to_uuid(doc_id), vector=embedding, payload=payload)],
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
            self._client.points.upsert(collection, points)
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
    ) -> list[dict]:
        try:
            results = self._client.points.search(
                collection,
                vector=query_vector,
                limit=top_k,
                score_threshold=min_score,
            )
            return [_normalize_result(result) for result in results]
        except Exception as e:
            logger.error(f"search failed [{collection}]: {e}")
            return []

    def hybrid_search(self, collection: str, query_text: str, filters: dict, top_k: int = 5) -> list[dict]:
        query_embedding = self.embed(query_text)
        filter_obj = _build_filter(filters)
        try:
            results = self._client.points.search(
                collection,
                vector=query_embedding,
                limit=top_k,
                score_threshold=0.0,
                filter=filter_obj,
            )
            return [_normalize_result(result) for result in results]
        except Exception as e:
            logger.error(f"hybrid_search failed [{collection}]: {e}")
            return []