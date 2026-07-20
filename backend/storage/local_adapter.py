import json
import os
import uuid
import logging
from datetime import datetime, timezone

import requests
from config import LOCAL_STORAGE_DIR, VECTORAI_URL
from storage.base import StorageClient
from storage.ucso_template import EMPTY_UCSO

logger = logging.getLogger("trinetra-backend.local_adapter")


class LocalStorageAdapter(StorageClient):
    """
    Local-first Qdrant-compatible adapter.

    This adapter provides the same contract as the current storage client,
    so backend/agents remain storage-agnostic. Data is persisted locally
    as JSON + binary files to support edge/offline mode.
    """

    def __init__(self):
        self.root_dir = LOCAL_STORAGE_DIR
        self.app_dir = os.path.join(self.root_dir, "applications")
        self.file_dir = os.path.join(self.root_dir, "files")
        self.event_log_path = os.path.join(self.root_dir, "event_log.jsonl")

        os.makedirs(self.app_dir, exist_ok=True)
        os.makedirs(self.file_dir, exist_ok=True)
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
                    logger.debug(f"Failed to initialize local Qdrant Client at {db_path}: {e}. Falling back to :memory:")
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


    def _app_path(self, app_id: str) -> str:
        return os.path.join(self.app_dir, f"{app_id}.json")

    def _utc_now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _read(self, app_id: str) -> dict | None:
        path = self._app_path(app_id)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                import fcntl
                fcntl.flock(f, fcntl.LOCK_SH)
                try:
                    return json.load(f)
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)
        except Exception as e:
            logger.debug(f"flock read failed for {app_id}, falling back without lock: {e}")
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)

    def _write(self, app_id: str, payload: dict) -> None:
        path = self._app_path(app_id)
        try:
            with open(path, "a+", encoding="utf-8") as f:
                import fcntl
                fcntl.flock(f, fcntl.LOCK_EX)
                try:
                    f.seek(0)
                    f.truncate()
                    json.dump(payload, f, ensure_ascii=False)
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)
        except Exception as e:
            logger.debug(f"flock write failed for {app_id}, falling back without lock: {e}")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)


    def create_application(self, applicant_data: dict, tenant_id: str = "tenant_alpha") -> dict:
        app_id = str(uuid.uuid4())
        ucso = json.loads(json.dumps(EMPTY_UCSO))
        ucso["application_id"] = app_id
        ucso["applicant"] = applicant_data
        ucso["tenant_id"] = tenant_id
        row = {
            "id": app_id,
            "company_name": applicant_data.get("company_name", ""),
            "pan": applicant_data.get("pan", ""),
            "gstin": applicant_data.get("gstin", ""),
            "cin": applicant_data.get("cin", ""),
            "tenant_id": tenant_id,
            "ucso_data": ucso,
            "status": "CREATED",
            "created_at": self._utc_now(),
            "updated_at": self._utc_now(),
        }
        self._write(app_id, row)
        self.append_event(app_id, {"event": "application_created", "source": "backend", "timestamp": self._utc_now()})
        return row

    def get_application(self, app_id: str) -> dict | None:
        app = self._read(app_id)
        if app and "tenant_id" not in app:
            app["tenant_id"] = "tenant_alpha"
            if "ucso_data" in app and isinstance(app["ucso_data"], dict):
                app["ucso_data"]["tenant_id"] = "tenant_alpha"
        return app

    def get_ucso(self, app_id: str) -> dict | None:
        app = self.get_application(app_id)
        if not app:
            return None
        return app.get("ucso_data", {})

    def patch_namespace(self, app_id: str, namespace: str, data: dict, idempotency_key: str | None = None) -> dict:
        app = self.get_application(app_id)
        if not app:
            raise ValueError(f"Application {app_id} not found")

        ucso = app.get("ucso_data", {})

        # audit_log may be either a list (legacy) or a dict with "entries" (monitor-agent output).
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

        if idempotency_key and any(e.get("idempotency_key") == idempotency_key for e in audit_log):
            return app

        if namespace not in ucso:
            ucso[namespace] = {}

        if isinstance(ucso[namespace], dict):
            ucso[namespace].update(data)
        else:
            ucso[namespace] = data

        # Re-resolve audit log in case namespace patch replaced audit_log shape.
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
            "timestamp": self._utc_now(),
            "event": f"PATCH_{namespace}",
            "keys_updated": list(data.keys()),
            "idempotency_key": idempotency_key,
        })

        app["ucso_data"] = ucso
        app["updated_at"] = self._utc_now()
        self._write(app_id, app)
        self.append_event(app_id, {
            "event": f"PATCH_{namespace}",
            "namespace": namespace,
            "keys_updated": list(data.keys()),
            "idempotency_key": idempotency_key,
            "timestamp": self._utc_now(),
        })
        return app

    def add_note(self, app_id: str, note: str, author: str) -> dict:
        app = self.get_application(app_id)
        if not app:
            raise ValueError(f"Application {app_id} not found")

        ucso = app.get("ucso_data", {})
        ucso.setdefault("human_notes", {"notes": []})
        ucso["human_notes"]["notes"].append({
            "text": note,
            "author": author,
            "timestamp": self._utc_now(),
            "type": "TEXT",
        })

        app["ucso_data"] = ucso
        app["updated_at"] = self._utc_now()
        self._write(app_id, app)
        self.append_event(app_id, {"event": "note_added", "author": author, "timestamp": self._utc_now()})
        return ucso

    def upload_file(self, app_id: str, file_bytes: bytes, filename: str, doc_type: str) -> dict:
        app = self.get_application(app_id)
        if not app:
            raise ValueError(f"Application {app_id} not found")

        storage_path = f"{app_id}/{doc_type}/{filename}"
        local_path = os.path.join(self.file_dir, storage_path)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, "wb") as f:
            f.write(file_bytes)

        ucso = app.get("ucso_data", {})
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
            "uploaded_at": self._utc_now(),
        })

        app["ucso_data"] = ucso
        app["updated_at"] = self._utc_now()
        self._write(app_id, app)
        self.append_event(app_id, {"event": "file_uploaded", "storage_path": storage_path, "timestamp": self._utc_now()})

        return {"storage_path": storage_path, "file_url": f"local://{storage_path}"}

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

    def append_event(self, app_id: str, event: dict) -> None:
        record = {
            "application_id": app_id,
            "event_id": str(uuid.uuid4()),
            "synced": False,
            **event,
        }
        try:
            with open(self.event_log_path, "a", encoding="utf-8") as f:
                import fcntl
                fcntl.flock(f, fcntl.LOCK_EX)
                try:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)
        except Exception as e:
            logger.debug(f"flock append_event failed for {app_id}, falling back without lock: {e}")
            with open(self.event_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
