import os
import json
import uuid
import logging
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, JSON, ForeignKey, select, update, delete
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from storage.base import StorageClient
from storage.ucso_template import EMPTY_UCSO
from config import LOCAL_STORAGE_DIR, REDIS_URL

logger = logging.getLogger("trinetra-backend.postgres_adapter")

# Load PostgreSQL connection URI
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/trinetra"

import sqlite3
from sqlalchemy.event import listens_for
from sqlalchemy.pool import Pool

@listens_for(Pool, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    typename = type(dbapi_connection).__name__
    module = type(dbapi_connection).__module__
    if isinstance(dbapi_connection, sqlite3.Connection) or "sqlite" in module or "sqlite" in typename.lower():
        try:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()
        except Exception as e:
            logger.debug(f"Failed to set sqlite pragma: {e}")

Base = declarative_base()

class DBApplication(Base):
    __tablename__ = "applications"
    id = Column(String(50), primary_key=True)
    company_name = Column(String(255))
    pan = Column(String(50))
    gstin = Column(String(50))
    cin = Column(String(50))
    tenant_id = Column(String(50))
    status = Column(String(50))
    ucso_data = Column(JSON)
    created_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))


class DBEventLog(Base):
    __tablename__ = "event_logs"
    event_id = Column(String(50), primary_key=True)
    application_id = Column(String(50), ForeignKey("applications.id", ondelete="CASCADE"))
    event_name = Column(String(100))
    payload = Column(JSON)
    created_at = Column(DateTime(timezone=True))


class DBOutboxEvent(Base):
    __tablename__ = "outbox_events"
    id = Column(String(50), primary_key=True)
    topic = Column(String(100))
    payload = Column(JSON)
    status = Column(String(50), default="PENDING")
    created_at = Column(DateTime(timezone=True))
    processed_at = Column(DateTime(timezone=True), nullable=True)


class PostgresStorageAdapter(StorageClient):
    """
    Enterprise Postgres Storage Client (Async).
    Uses PostgreSQL JSONB schema with SELECT FOR UPDATE transactions
    to handle multiple concurrent writes from the 13 agents.
    """

    def __init__(self):
        self.root_dir = LOCAL_STORAGE_DIR
        self.file_dir = os.path.join(self.root_dir, "files")
        os.makedirs(self.file_dir, exist_ok=True)

        global DATABASE_URL
        if DATABASE_URL.startswith("postgresql://"):
            DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

        logger.info(f"🔌 Initializing async storage client engine...")
        self.engine = create_async_engine(
            DATABASE_URL, 
            pool_size=10, 
            max_overflow=20,
            pool_pre_ping=True
        )
        self.Session = sessionmaker(bind=self.engine, class_=AsyncSession, expire_on_commit=False)
        self.initialize_collections()

    async def initialize_db(self):
        """Asynchronously creates SQL tables, falling back to local SQLite if Postgres is unavailable."""
        try:
            logger.info("🔌 Verifying PostgreSQL async connection...")
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("✅ PostgreSQL tables verified/created.")
        except Exception as e:
            logger.warning(f"⚠️ PostgreSQL connection failed ({e}). Falling back to Local SQLite database.")
            db_path = os.path.join(self.root_dir, "trinetra_local.db")
            sqlite_url = f"sqlite+aiosqlite:///{db_path}?timeout=5000"
            
            await self.engine.dispose()
            self.engine = create_async_engine(sqlite_url)
            self.Session = sessionmaker(bind=self.engine, class_=AsyncSession, expire_on_commit=False)
            
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info(f"💾 SQLite database initialized locally at: {db_path}")


        self.initialize_collections()


    def initialize_collections(self):
        """Pre-create all Qdrant collections on backend startup."""
        collections = [
            "document_chunks", "financial_profiles", "gst_patterns",
            "bank_recon_profiles", "news_articles", "litigation_records",
            "rbi_circulars", "mca_filings", "pan_profiles", "risk_decisions",
            "pd_transcripts", "stress_scenarios", "audit_events", "application_summaries",
        ]
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams
            import os

            qdrant_url = os.getenv("QDRANT_URL") or os.getenv("VECTORAI_URL", "http://localhost:6333")
            use_local = False
            if "50051" in qdrant_url or ("vectorai" in qdrant_url.lower() and "http" not in qdrant_url.lower()):
                use_local = True

            if use_local:
                db_path = os.path.join(self.root_dir, "qdrant_db")
                os.makedirs(db_path, exist_ok=True)
                try:
                    client = QdrantClient(path=db_path)
                except Exception as e:
                    logger.debug(f"Failed to initialize local Qdrant Client: {e}, falling back to :memory:")
                    client = QdrantClient(":memory:")
            else:
                url = qdrant_url
                if not url.startswith("http://") and not url.startswith("https://"):
                    url = f"http://{url}"
                client = QdrantClient(url=url, timeout=5.0)

            for name in collections:
                try:
                    if client.collection_exists(collection_name=name):
                        continue
                    client.create_collection(
                        collection_name=name,
                        vectors_config=VectorParams(size=384, distance=Distance.COSINE),
                    )
                except Exception as e:
                    logger.debug(f"Failed to check or create collection {name}: {e}")
        except Exception as e:
            logger.warning(f"Could not connect to Qdrant or initialize collections: {e}")

    def _utc_now(self) -> datetime:
        return datetime.now(timezone.utc)

    async def create_application(self, applicant_data: dict, tenant_id: str = "tenant_alpha") -> dict:
        app_id = str(uuid.uuid4())
        ucso = json.loads(json.dumps(EMPTY_UCSO))
        ucso["application_id"] = app_id
        ucso["applicant"] = applicant_data
        ucso["tenant_id"] = tenant_id

        async with self.Session() as session:
            try:
                db_app = DBApplication(
                    id=app_id,
                    company_name=applicant_data.get("company_name", ""),
                    pan=applicant_data.get("pan", ""),
                    gstin=applicant_data.get("gstin", ""),
                    cin=applicant_data.get("cin", ""),
                    tenant_id=tenant_id,
                    status="CREATED",
                    ucso_data=ucso,
                    created_at=self._utc_now(),
                    updated_at=self._utc_now()
                )
                session.add(db_app)
                await session.commit()
                
                # Log event
                await self.append_event_in_session(session, app_id, {
                    "event": "application_created",
                    "source": "backend",
                    "timestamp": self._utc_now().isoformat()
                })
                await session.commit()

                return {
                    "id": app_id,
                    "company_name": db_app.company_name,
                    "pan": db_app.pan,
                    "gstin": db_app.gstin,
                    "cin": db_app.cin,
                    "tenant_id": db_app.tenant_id,
                    "status": db_app.status,
                    "ucso_data": db_app.ucso_data,
                    "created_at": db_app.created_at.isoformat(),
                    "updated_at": db_app.updated_at.isoformat(),
                }
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to create application in DB: {e}")
                raise

    async def get_application(self, app_id: str) -> dict | None:
        async with self.Session() as session:
            db_app = await session.get(DBApplication, app_id)
            if not db_app:
                return None
            return {
                "id": db_app.id,
                "company_name": db_app.company_name,
                "pan": db_app.pan,
                "gstin": db_app.gstin,
                "cin": db_app.cin,
                "tenant_id": db_app.tenant_id,
                "status": db_app.status,
                "ucso_data": db_app.ucso_data,
                "created_at": db_app.created_at.isoformat() if db_app.created_at else None,
                "updated_at": db_app.updated_at.isoformat() if db_app.updated_at else None,
            }

    async def get_ucso(self, app_id: str) -> dict | None:
        async with self.Session() as session:
            db_app = await session.get(DBApplication, app_id)
            if not db_app:
                return None
            return db_app.ucso_data
    async def patch_namespace(self, app_id: str, namespace: str, data: dict, idempotency_key: str | None = None) -> dict:
        async with self.Session() as session:
            try:
                stmt = select(DBApplication).filter_by(id=app_id).with_for_update()
                res = await session.execute(stmt)
                db_app = res.scalar_one_or_none()
                if not db_app:
                    raise ValueError(f"Application {app_id} not found")

                ucso = db_app.ucso_data or {}
                
                # Resolve audit log structure
                audit_container = ucso.get("audit_log", [])
                if isinstance(audit_container, dict):
                    audit_log = audit_container.get("entries", [])
                    if not isinstance(audit_log, list):
                        audit_log = []
                    audit_container["entries"] = audit_log
                    ucso["audit_log"] = audit_container
                elif isinstance(audit_container, list):
                    audit_log = audit_container
                    ucso["audit_log"] = audit_log
                else:
                    audit_log = []
                    ucso["audit_log"] = audit_log

                # Idempotency check
                if idempotency_key and any(e.get("idempotency_key") == idempotency_key for e in audit_log):
                    return {
                        "id": db_app.id,
                        "company_name": db_app.company_name,
                        "tenant_id": db_app.tenant_id,
                        "status": db_app.status,
                        "ucso_data": ucso,
                    }

                if namespace not in ucso:
                    ucso[namespace] = {}

                if isinstance(ucso[namespace], dict):
                    ucso[namespace].update(data)
                else:
                    ucso[namespace] = data

                # Re-verify audit log
                current_audit = ucso.get("audit_log", [])
                if isinstance(current_audit, dict):
                    audit_log = current_audit.get("entries", [])
                    if not isinstance(audit_log, list):
                        audit_log = []
                    current_audit["entries"] = audit_log
                    ucso["audit_log"] = current_audit
                elif isinstance(current_audit, list):
                    audit_log = current_audit
                else:
                    audit_log = []
                    ucso["audit_log"] = audit_log

                audit_log.append({
                    "timestamp": self._utc_now().isoformat(),
                    "event": f"PATCH_{namespace}",
                    "keys_updated": list(data.keys()),
                    "idempotency_key": idempotency_key,
                })

                # Check if risk decision is written to update main status
                if namespace == "risk":
                    decision = data.get("decision")
                    if decision:
                        db_app.status = decision
                        ucso["status"] = decision

                db_app.ucso_data = ucso
                db_app.updated_at = self._utc_now()
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(db_app, "ucso_data")
                await session.commit()

                # Record event inside session
                await self.append_event_in_session(session, app_id, {
                    "event": f"PATCH_{namespace}",
                    "namespace": namespace,
                    "keys_updated": list(data.keys()),
                    "idempotency_key": idempotency_key,
                    "timestamp": self._utc_now().isoformat(),
                })
                await session.commit()

                return {
                    "id": db_app.id,
                    "company_name": db_app.company_name,
                    "tenant_id": db_app.tenant_id,
                    "status": db_app.status,
                    "ucso_data": ucso,
                }
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to patch namespace {namespace} on {app_id}: {e}")
                raise

    async def add_note(self, app_id: str, note: str, author: str) -> dict:
        async with self.Session() as session:
            try:
                stmt = select(DBApplication).filter_by(id=app_id).with_for_update()
                res = await session.execute(stmt)
                db_app = res.scalar_one_or_none()
                if not db_app:
                    raise ValueError(f"Application {app_id} not found")

                ucso = db_app.ucso_data or {}
                ucso.setdefault("human_notes", {"notes": []})
                ucso["human_notes"]["notes"].append({
                    "text": note,
                    "author": author,
                    "timestamp": self._utc_now().isoformat(),
                    "type": "TEXT",
                })

                db_app.ucso_data = ucso
                db_app.updated_at = self._utc_now()
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(db_app, "ucso_data")
                await session.commit()

                await self.append_event_in_session(session, app_id, {
                    "event": "note_added",
                    "author": author,
                    "timestamp": self._utc_now().isoformat()
                })
                await session.commit()

                return ucso
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to add note to {app_id}: {e}")
                raise

    async def upload_file(self, app_id: str, file_bytes: bytes, filename: str, doc_type: str) -> dict:
        storage_path = f"{app_id}/{doc_type}/{filename}"
        local_path = os.path.join(self.file_dir, storage_path)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        
        # Save local filesystem reference
        with open(local_path, "wb") as f:
            f.write(file_bytes)

        async with self.Session() as session:
            try:
                stmt = select(DBApplication).filter_by(id=app_id).with_for_update()
                res = await session.execute(stmt)
                db_app = res.scalar_one_or_none()
                if not db_app:
                    raise ValueError(f"Application {app_id} not found")

                ucso = db_app.ucso_data or {}
                ucso.setdefault("documents", {"files": []})
                ucso["documents"]["files"].append({
                    "doc_id": str(uuid.uuid4()),
                    "type": doc_type,
                    "storage_path": storage_path,
                    "file_url": f"local://{storage_path}",
                    "filename": filename,
                    "s3_key": storage_path,
                    "parsed": False,
                    "confidence": 0.0,
                    "uploaded_at": self._utc_now().isoformat(),
                })

                # Check if all files uploaded to trigger application_created in outbox
                if doc_type != "CAM":
                    files = ucso.get("documents", {}).get("files", [])
                    uploaded_types = {f.get("type") for f in files}
                    is_combined = "COMBINED" in uploaded_types
                    has_all_four = all(t in uploaded_types for t in ["ANNUAL_REPORT", "BANK_STMT", "GST_RETURN", "ITR"])
                    if is_combined or has_all_four:
                        await self.create_outbox_event(session, "application_created", {"application_id": app_id})

                db_app.ucso_data = ucso
                db_app.updated_at = self._utc_now()
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(db_app, "ucso_data")
                
                # Log event in same session transaction
                db_event = DBEventLog(
                    event_id=str(uuid.uuid4()),
                    application_id=app_id,
                    event_name="file_uploaded",
                    payload={"event": "file_uploaded", "storage_path": storage_path, "timestamp": self._utc_now().isoformat()},
                    created_at=self._utc_now()
                )
                session.add(db_event)
                
                await session.commit()
                return {"storage_path": storage_path, "file_url": f"local://{storage_path}"}
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to update files database record for {app_id}: {e}")
                raise

    def get_file(self, app_id: str, filename: str | None = None) -> tuple[bytes, str] | None:
        app_folder = os.path.join(self.file_dir, app_id)
        if not os.path.exists(app_folder):
            return None

        discovered_files = []
        for root, _, files in os.walk(app_folder):
            for file_name in files:
                discovered_files.append(os.path.join(root, file_name))

        if not discovered_files:
            return None

        selected = None
        if filename:
            for path in discovered_files:
                if os.path.basename(path) == filename:
                    selected = path
                    break
        else:
            pdf_files = [p for p in discovered_files if p.lower().endswith(".pdf")]
            selected = pdf_files[0] if pdf_files else discovered_files[0]

        if not selected:
            return None

        with open(selected, "rb") as f:
            return f.read(), os.path.basename(selected)

    def get_file_by_key(self, storage_path: str) -> tuple[bytes, str] | None:
        local_path = os.path.join(self.file_dir, storage_path)
        if not os.path.exists(local_path):
            return None
        with open(local_path, "rb") as f:
            return f.read(), os.path.basename(local_path)

    async def append_event_in_session(self, session, app_id: str, event: dict) -> None:
        """Helper to append an event inside an active session context manager."""
        db_event = DBEventLog(
            event_id=event.get("event_id") or str(uuid.uuid4()),
            application_id=app_id,
            event_name=event.get("event", "unknown"),
            payload=event,
            created_at=self._utc_now()
        )
        session.add(db_event)

    async def append_event(self, app_id: str, event: dict) -> None:
        async with self.Session() as session:
            try:
                await self.append_event_in_session(session, app_id, event)
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to append event to DB: {e}")

    async def create_outbox_event(self, session, topic: str, payload: dict) -> None:
        """Helper to insert a transactional outbox event using an active session."""
        try:
            from core import trace_id_var
            trace_id = trace_id_var.get()
            if trace_id and isinstance(payload, dict) and "trace_id" not in payload:
                payload["trace_id"] = trace_id
            db_event = DBOutboxEvent(
                id=str(uuid.uuid4()),
                topic=topic,
                payload=payload,
                status="PENDING",
                created_at=self._utc_now()
            )
            session.add(db_event)
        except Exception as e:
            logger.error(f"Failed to queue outbox event to session: {e}")
            raise

    async def add_outbox_event(self, topic: str, payload: dict) -> str:
        """Standalone helper to queue a non-transactional outbox event."""
        async with self.Session() as session:
            try:
                from core import trace_id_var
                trace_id = trace_id_var.get()
                if trace_id and isinstance(payload, dict) and "trace_id" not in payload:
                    payload["trace_id"] = trace_id
                event_id = str(uuid.uuid4())
                db_event = DBOutboxEvent(
                    id=event_id,
                    topic=topic,
                    payload=payload,
                    status="PENDING",
                    created_at=self._utc_now()
                )
                session.add(db_event)
                await session.commit()
                return event_id
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to add outbox event to DB: {e}")
                raise
