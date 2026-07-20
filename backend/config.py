"""
Trinetra FastAPI Backend — Configuration
Loads environment variables for Postgres/local storage, Redis, and CORS settings.
"""
import os
import logging
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

logger = logging.getLogger("trinetra-backend.config")

# Canonical version in agents/shared/vault.py
def load_vault_secrets(vault_dir="/vault/secrets"):
    if os.path.exists(vault_dir) and os.path.isdir(vault_dir):
        try:
            for entry in os.listdir(vault_dir):
                entry_path = os.path.join(vault_dir, entry)
                if os.path.isfile(entry_path):
                    if entry == "api-keys":
                        try:
                            with open(entry_path, "r") as f:
                                content = f.read().strip()
                            try:
                                import json
                                data = json.loads(content)
                                if isinstance(data, dict):
                                    for k, v in data.items():
                                        os.environ[k] = str(v).strip()
                            except Exception as e:
                                logger.debug(f"Failed to parse vault api-keys JSON: {e}. Trying key=value format.")
                                for line in content.splitlines():
                                    if "=" in line:
                                        k, v = line.split("=", 1)
                                        os.environ[k.strip()] = v.strip()
                        except Exception as e:
                            logger.warning(f"Failed to load vault api-keys file: {e}")
                    else:
                        try:
                            with open(entry_path, "r") as f:
                                os.environ[entry] = f.read().strip()
                        except Exception as e:
                            logger.warning(f"Failed to load vault secret file {entry}: {e}")
        except Exception as e:
            logger.warning(f"Failed to read vault directory {vault_dir}: {e}")

load_vault_secrets()

# ── Security / Auth ──
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
if not JWT_SECRET_KEY:
    import secrets as _sec
    JWT_SECRET_KEY = _sec.token_hex(32)
    print(f"⚠️  JWT_SECRET_KEY not set in .env — generated ephemeral key (sessions won't survive restart)")

OIDC_ISSUER = os.getenv("OIDC_ISSUER", "")
OIDC_AUDIENCE = os.getenv("OIDC_AUDIENCE", "")

# ── Local/Edge Storage Config (local-first, optional cloud sync) ──
STORAGE_MODE = os.getenv("STORAGE_MODE", os.getenv("ACTIAN_MODE", "edge")).lower()  # edge | cloud
LOCAL_STORAGE_DIR = os.getenv("LOCAL_STORAGE_DIR", os.getenv("ACTIAN_LOCAL_DIR", os.path.join(os.path.dirname(__file__), "local_storage")))
CLOUD_API_URL = os.getenv("CLOUD_API_URL", os.getenv("ACTIAN_CLOUD_API_URL", ""))
CLOUD_API_KEY = os.getenv("CLOUD_API_KEY", os.getenv("ACTIAN_API_KEY", ""))

# ── Qdrant Vector DB ──
VECTORAI_URL = os.getenv("QDRANT_URL", os.getenv("VECTORAI_URL", "http://localhost:6333"))

# ── Redis ──
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# ── CORS ──
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")

# ── Server ──
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# ── Optional service auth for agent namespace writes ──
AGENT_SERVICE_TOKEN = os.getenv("AGENT_SERVICE_TOKEN", "")
if not AGENT_SERVICE_TOKEN:
    import secrets as _sec2
    AGENT_SERVICE_TOKEN = _sec2.token_hex(24)
    print(f"⚠️  AGENT_SERVICE_TOKEN not set in .env — generated ephemeral token: {AGENT_SERVICE_TOKEN[:12]}...")
