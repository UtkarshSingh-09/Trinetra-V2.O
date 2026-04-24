"""
Trinetra FastAPI Backend — Configuration
Loads environment variables for Actian storage, Redis, and CORS settings.
"""
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# ── Actian/Edge Storage Config (local-first, optional cloud sync) ──
ACTIAN_MODE = os.getenv("ACTIAN_MODE", "edge").lower()  # edge | cloud
ACTIAN_LOCAL_DIR = os.getenv("ACTIAN_LOCAL_DIR", os.path.join(os.path.dirname(__file__), "actian_local"))
ACTIAN_CLOUD_API_URL = os.getenv("ACTIAN_CLOUD_API_URL", "")
ACTIAN_API_KEY = os.getenv("ACTIAN_API_KEY", "")

# ── Actian VectorAI ──
VECTORAI_URL = os.getenv("VECTORAI_URL", "localhost:50051")

# ── Redis ──
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# ── CORS ──
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")

# ── Server ──
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))

# ── Optional service auth for agent namespace writes ──
AGENT_SERVICE_TOKEN = os.getenv("AGENT_SERVICE_TOKEN", "")
