import os
import sys
import time
import json
import base64
import pytest
import requests
from unittest.mock import MagicMock, patch

# Add backend and agents directories to sys.path to enable imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend")))

# Import agents functions
import importlib.util
def load_doc_agent():
    spec_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "doc-agent", "main.py"))
    spec = importlib.util.spec_from_file_location("doc_agent", spec_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def load_pd_agent():
    spec_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "pd-agent", "main.py"))
    spec = importlib.util.spec_from_file_location("pd_agent", spec_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

# Import backend auth functions
from auth import verify_token, verify_oidc_token, create_token, _oidc_config_cache


# ──────────────────────────────────────────────────────────────────────
# SSO & OIDC Authentication Tests
# ──────────────────────────────────────────────────────────────────────

def test_oidc_token_verification_fallback():
    """Verify OIDC verification logic and fallback to HMAC."""
    # Generate mock key pair for RS256 token signature
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    
    # Extract public key components n and e
    numbers = public_key.public_numbers()
    n_b64 = base64.urlsafe_b64encode(numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, 'big')).decode('utf-8').rstrip('=')
    e_b64 = base64.urlsafe_b64encode(numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, 'big')).decode('utf-8').rstrip('=')
    
    # Mock issuer and configuration
    issuer = "https://mock-identity-provider.com/auth"
    audience = "trinetra-backend"
    
    # Mock JWK structure
    mock_jwk = {
        "kty": "RSA",
        "alg": "RS256",
        "use": "sig",
        "kid": "test-key-id",
        "n": n_b64,
        "e": e_b64
    }
    
    # Create valid OIDC token header and payload
    header = {"alg": "RS256", "kid": "test-key-id", "typ": "JWT"}
    payload = {
        "iss": issuer,
        "sub": "oidc_user_123",
        "preferred_username": "oidc_user",
        "roles": ["underwriter"],
        "tenant_id": "tenant_alpha",
        "name": "OIDC User",
        "aud": audience,
        "exp": time.time() + 300
    }
    
    def b64url_encode(data: dict) -> str:
        s = json.dumps(data).encode('utf-8')
        return base64.urlsafe_b64encode(s).decode('utf-8').rstrip('=')
        
    header_b64 = b64url_encode(header)
    payload_b64 = b64url_encode(payload)
    message = f"{header_b64}.{payload_b64}".encode('utf-8')
    
    # Sign token using private key
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives import hashes
    signature = private_key.sign(
        message,
        padding.PKCS1v15(),
        hashes.SHA256()
    )
    sig_b64 = base64.urlsafe_b64encode(signature).decode('utf-8').rstrip('=')
    token = f"{message.decode('utf-8')}.{sig_b64}"
    
    # Mock get_oidc_jwks to return our public key JWK
    with patch("auth.get_oidc_jwks", return_value=[mock_jwk]):
        res = verify_oidc_token(token, issuer, audience)
        assert res is not None
        assert res["username"] == "oidc_user"
        assert res["role"] == "underwriter"
        assert res["tenant_id"] == "tenant_alpha"
        
        # Test full backend integration using verify_token
        with patch("auth.OIDC_ISSUER", issuer), patch("auth.OIDC_AUDIENCE", audience):
            # OIDC verification succeeds
            integrated_res = verify_token(token)
            assert integrated_res is not None
            assert integrated_res["username"] == "oidc_user"
            
            # Fallback to local 2-part HMAC JWT
            local_user = {"username": "local_dev", "role": "admin", "tenant_id": "tenant_alpha"}
            local_token = create_token(local_user)
            local_res = verify_token(local_token)
            assert local_res is not None
            assert local_res["username"] == "local_dev"


# ──────────────────────────────────────────────────────────────────────
# Local LLM Fallback (Ollama) Tests
# ──────────────────────────────────────────────────────────────────────

@patch("requests.post")
@patch("requests.get")
def test_ollama_model_checks_and_extraction(mock_get, mock_post):
    """Test Ollama model pulling check and structured text extraction fallbacks."""
    doc_agent = load_doc_agent()
    
    # Mock /api/tags returning model not found first, then successfully pulling
    mock_get.return_value = MagicMock(status_code=200, json=lambda: {"models": []})
    mock_post.return_value = MagicMock(status_code=200)
    
    doc_agent.ensure_ollama_model("http://localhost:11434", "llama3")
    
    mock_get.assert_called_once_with("http://localhost:11434/api/tags", timeout=5)
    mock_post.assert_called_once_with(
        "http://localhost:11434/api/pull", 
        json={"name": "llama3", "stream": False}, 
        timeout=300
    )
    
    # Reset mocks to test extraction API
    mock_post.reset_mock()
    mock_response_content = {
        "message": {
            "content": json.dumps({
                "revenue": "₹25,00,000",
                "ebitda": "4.5 Lakh",
                "net_profit": "2 Lakh",
                "total_debt": "100000",
                "net_worth": "5000000",
                "interest_expense": "50000"
            })
        }
    }
    mock_post.return_value = MagicMock(status_code=200, json=lambda: mock_response_content)
    
    extracted = doc_agent.extract_financials_with_ollama("Test annual statement")
    assert extracted["revenue"] == 2500000.0
    assert extracted["ebitda"] == 450000.0
    assert extracted["net_profit"] == 200000.0
    assert extracted["total_debt"] == 100000.0


@patch("requests.post")
def test_pd_agent_ollama_risk_evaluation(mock_post):
    """Test PD agent risk evaluation falling back to local Ollama."""
    pd_agent = load_pd_agent()
    
    mock_response = {
        "message": {
            "content": json.dumps({
                "succession_risk": 0.2,
                "capacity_risk": 0.3,
                "integrity_risk": 0.1,
                "overall_risk_adjustment": -0.05,
                "qualitative_flags": ["SUCCESSION_PLANNED"],
                "entities_extracted": {"people": ["John"], "companies": ["ABC"], "amounts": []},
                "confidence": 0.9,
                "reasoning": "Strong succession plan observed."
            })
        }
    }
    mock_post.return_value = MagicMock(status_code=200, json=lambda: mock_response)
    
    with patch.object(pd_agent, "ensure_ollama_model"):
        res = pd_agent.evaluate_transcript_with_ollama("Succession plan is set with daughter taking charge.")
        assert res["succession_risk"] == 0.2
        assert res["overall_risk_adjustment"] == -0.05
        assert "SUCCESSION_PLANNED" in res["qualitative_flags"]


# ──────────────────────────────────────────────────────────────────────
# AWS Textract Fallback Tests
# ──────────────────────────────────────────────────────────────────────

@patch("boto3.client")
def test_aws_textract_ocr_fallback(mock_boto_client):
    """Verify AWS Textract integration in doc-agent and fallback execution."""
    doc_agent = load_doc_agent()
    
    # Setup mock boto3 Textract client
    mock_textract = MagicMock()
    mock_boto_client.return_value = mock_textract
    mock_textract.detect_document_text.return_value = {
        "Blocks": [
            {"BlockType": "LINE", "Text": "This is a long mock document line that exceeds fifty characters in total length to ensure high confidence rating."},
            {"BlockType": "LINE", "Text": "Revenue from operations: ₹45,00,000"}
        ]
    }
    
    # Mock image
    from PIL import Image
    mock_img = Image.new('RGB', (100, 100))
    
    with patch.object(doc_agent, "AWS_ACCESS_KEY_ID", "mock_key"), \
         patch.object(doc_agent, "AWS_SECRET_ACCESS_KEY", "mock_secret"):
        
        extracted_text = doc_agent.extract_layout_aware_textract(mock_img)
        assert "Revenue from operations" in extracted_text
        assert "₹45,00,000" in extracted_text
        
        # Test pdfplumber scanned OCR routing with Textract present
        mock_pdf = MagicMock()
        mock_page = MagicMock()
        mock_page.to_image.return_value.original = mock_img
        mock_pdf.pages = [mock_page]
        
        with patch("pdfplumber.open", return_value=MagicMock(__enter__=lambda self: mock_pdf)):
            full_text, conf, method = doc_agent.extract_text_from_pdf("mock_scanned.pdf")
            assert "Revenue from operations" in full_text
            assert conf == 0.85
            assert method == "textract"


# ──────────────────────────────────────────────────────────────────────
# Transactional Outbox & Workflow Orchestrator Tests
# ──────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_transactional_outbox_and_relay():
    """Verify that outbox events can be created and are relayed to Redis."""
    import asyncio
    from core import storage, redis_broker
    from workflow_orchestrator import WorkflowOrchestrator
    from storage.postgres_adapter import DBOutboxEvent
    from sqlalchemy import select

    # Force database initialization/SQLite fallback verification
    await storage.initialize_db()

    # Instantiate the orchestrator
    orchestrator = WorkflowOrchestrator()
    orchestrator.running = False  # Avoid running the infinite background loops

    # Add a mock event to the outbox database
    event_topic = "test_event_topic"
    event_payload = {"key": "value", "application_id": "test-app-id-123"}
    
    # Generate and add outbox event
    event_id = await storage.add_outbox_event(event_topic, event_payload)
    assert event_id is not None

    # Verify event is in the database with PENDING status
    session = storage.Session()
    try:
        stmt = select(DBOutboxEvent).filter_by(id=event_id)
        res = await session.execute(stmt)
        db_evt = res.scalar_one_or_none()
        assert db_evt is not None
        assert db_evt.status == "PENDING"
    finally:
        await session.close()

    # Mock redis_broker.publish to avoid writing to actual Redis
    with patch.object(redis_broker, "publish") as mock_publish:
        original_sleep = asyncio.sleep
        async def mock_sleep(delay):
            orchestrator.running = False
            await original_sleep(0.01)

        orchestrator.running = True
        with patch("asyncio.sleep", side_effect=mock_sleep):
            await orchestrator.outbox_relay_loop()

        # Check that redis_broker.publish was called with the topic and payload
        mock_publish.assert_called_with(event_topic, event_payload)

    # Verify event is marked as SENT
    session = storage.Session()
    try:
        stmt = select(DBOutboxEvent).filter_by(id=event_id)
        res = await session.execute(stmt)
        db_evt = res.scalar_one_or_none()
        assert db_evt is not None
        assert db_evt.status == "SENT"
        assert db_evt.processed_at is not None
    finally:
        await session.close()


@pytest.mark.anyio
async def test_orchestrator_reconciliation():
    """Verify that stuck applications are detected and re-triggered by the orchestrator."""
    import datetime
    from core import storage, redis_broker
    from workflow_orchestrator import WorkflowOrchestrator
    from storage.postgres_adapter import DBApplication
    from sqlalchemy import select

    # Force database initialization/SQLite fallback verification
    await storage.initialize_db()

    # Create a stuck application in the database
    # Non-terminal state (CREATED), updated > 3 minutes ago
    app_id = "stuck-app-test-999"
    applicant_data = {"company_name": "Stuck Co", "pan": "ABCDE1234F", "gstin": "12ABCDE1234F1Z0"}
    
    # Create the application
    app_dict = await storage.create_application(applicant_data, tenant_id="tenant_alpha")
    
    # Update the application to look old and have documents
    session = storage.Session()
    try:
        stmt = select(DBApplication).filter_by(id=app_dict["id"])
        res = await session.execute(stmt)
        db_app = res.scalar_one_or_none()
        assert db_app is not None
        
        # Set old updated_at
        db_app.updated_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=5)
        
        # Add files to ucso_data so the reconciler tries to process it
        import copy
        ucso = copy.deepcopy(db_app.ucso_data)
        ucso["documents"] = {
            "files": [
                {"type": "COMBINED", "s3_key": "test/combined.pdf", "status": "UPLOADED"}
            ]
        }
        db_app.ucso_data = ucso
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(db_app, "ucso_data")
        await session.commit()
        
        real_app_id = db_app.id
    finally:
        await session.close()

    orchestrator = WorkflowOrchestrator()
    
    # Mock redis_broker.publish to capture re-triggering events
    with patch.object(redis_broker, "publish") as mock_publish:
        # Run reconciliation on this specific application
        res = await orchestrator.reconcile_application(real_app_id)
        assert res["status"] == "RE_TRIGGERED"
        assert res["reason"] == "compliance_stuck"

        # Verify compliance check was re-triggered
        mock_publish.assert_called_with("application_created", {"application_id": real_app_id})

    # Clean up test app
    session = storage.Session()
    try:
        stmt = select(DBApplication).filter_by(id=real_app_id)
        res = await session.execute(stmt)
        db_app = res.scalar_one_or_none()
        if db_app:
            await session.delete(db_app)
            await session.commit()
    finally:
        await session.close()


def test_circuit_breaker_states():
    """Verify that CircuitBreaker transitions through CLOSED, OPEN, and HALF-OPEN states correctly."""
    from shared.circuit_breaker import CircuitBreaker, CircuitBreakerError

    cb = CircuitBreaker(name="test-cb", failure_threshold=2, recovery_timeout=0.1)
    
    # 1. Closed state
    assert cb.state == "CLOSED"
    
    def failing_func():
        raise ValueError("failing")
        
    def success_func():
        return "success"

    # Call 1: failure
    with pytest.raises(ValueError):
        cb.call(failing_func)
    assert cb.state == "CLOSED"
    assert cb.failure_count == 1

    # Call 2: failure -> trips circuit
    with pytest.raises(ValueError):
        cb.call(failing_func)
    assert cb.state == "OPEN"
    assert cb.failure_count == 2

    # Call 3: should fail fast with CircuitBreakerError
    with pytest.raises(CircuitBreakerError):
        cb.call(success_func)

    # Wait for cooldown
    time.sleep(0.15)

    # Call 4: half-open -> CLOSED on success
    res = cb.call(success_func)
    assert res == "success"
    assert cb.state == "CLOSED"
    assert cb.failure_count == 0


def test_trace_id_log_formatting():
    """Verify that JSONFormatter format prepends the trace ID if present."""
    from shared.logger import JSONFormatter, trace_id_var
    import logging

    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test-agent",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Test log message",
        args=(),
        exc_info=None
    )
    
    # Without trace ID
    trace_id_var.set("")
    log_str = formatter.format(record)
    log_json = json.loads(log_str)
    assert log_json["message"] == "Test log message"
    assert log_json["trace_id"] is None
    
    # With trace ID
    trace_id_var.set("test-trace-1234")
    log_str = formatter.format(record)
    log_json = json.loads(log_str)
    assert "[Trace: test-trace-1234] - Test log message" in log_json["message"]
    assert log_json["trace_id"] == "test-trace-1234"
    
    # Reset
    trace_id_var.set("")


def test_vault_secrets_loading(tmp_path):
    """Verify that load_vault_secrets loads values from files and api-keys file."""
    from shared.agent_base import load_vault_secrets
    import os

    # Create dummy vault dir
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    
    # 1. Test individual secret file
    secret_file = vault_dir / "SUPER_API_KEY"
    secret_file.write_text("vault_secret_value_123")
    
    # 2. Test api-keys json file
    api_keys_file = vault_dir / "api-keys"
    api_keys_file.write_text(json.dumps({"ANOTHER_SECRET": "vault_value_456"}))
    
    # Run loader
    load_vault_secrets(vault_dir=str(vault_dir))
    
    # Assert variables loaded in os.environ
    assert os.environ.get("SUPER_API_KEY") == "vault_secret_value_123"
    assert os.environ.get("ANOTHER_SECRET") == "vault_value_456"


@pytest.mark.anyio
async def test_distributed_websocket_broadcast():
    """Verify that ws_manager.broadcast publishes payload to Redis Pub/Sub."""
    from core import ws_manager, redis_broker
    from unittest.mock import AsyncMock
    
    with patch.object(redis_broker, "client") as mock_redis_client:
        mock_publish = AsyncMock()
        mock_redis_client.publish = mock_publish
        
        test_payload = {"agent": "pan-agent", "status": "PROCESSING"}
        await ws_manager.broadcast("app-123", test_payload)
        
        # Verify publish was called
        assert mock_publish.called
        args, kwargs = mock_publish.call_args
        assert args[0] == "websocket_broadcast"
        published_data = json.loads(args[1])
        assert published_data["application_id"] == "app-123"
        assert published_data["payload"] == test_payload


@pytest.mark.anyio
async def test_login_rate_limiting():
    """Verify that login endpoint enforces rate limit on 5 attempts."""
    from fastapi.testclient import TestClient
    from main import app
    from core import redis_broker
    from unittest.mock import AsyncMock
    
    client = TestClient(app)
    
    # Mock redis get to simulate 5 failures
    with patch.object(redis_broker, "client") as mock_redis_client:
        # Use AsyncMock so it can be awaited correctly
        mock_redis_client.get = AsyncMock(return_value="5")
        
        # Make a login request
        response = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "wrong_password"}
        )
        
        assert response.status_code == 429
        assert "Too many login attempts" in response.json()["detail"]


@pytest.mark.anyio
async def test_sqlite_wal_pragma_enabled():
    """Verify that fallback SQLite database has WAL mode enabled."""
    from core import storage
    from sqlalchemy import text
    await storage.initialize_db()
    
    async with storage.Session() as session:
        res = await session.execute(text("PRAGMA journal_mode"))
        mode = res.scalar()
        assert mode.lower() == "wal"


@pytest.mark.anyio
async def test_login_validation_error():
    """Verify that login endpoint returns HTTP 422 for invalid payloads."""
    from fastapi.testclient import TestClient
    from main import app
    
    client = TestClient(app)
    
    # Missing password payload parameter
    response = client.post(
        "/api/auth/login",
        json={"username": "admin"}
    )
    assert response.status_code == 422


@pytest.mark.anyio
async def test_pd_validation_error():
    """Verify that PD transcript endpoint returns HTTP 422 for invalid payloads."""
    from fastapi.testclient import TestClient
    from main import app
    from core import storage
    
    await storage.initialize_db()
    
    client = TestClient(app)
    
    local_user = {"username": "local_dev", "role": "admin", "tenant_id": "tenant_alpha"}
    token = create_token(local_user)
    headers = {"Authorization": f"Bearer {token}"}
    
    # Missing 'transcript' field
    response = client.post(
        "/api/application/test-app-id-999/pd",
        headers=headers,
        json={"interviewer": "Officer Rajesh"}
    )
    assert response.status_code == 422


@pytest.mark.anyio
async def test_pd_validation_success_and_note_created():
    """Verify that PD transcript endpoint successfully saves the transcript as a note and triggers pd_submitted."""
    from fastapi.testclient import TestClient
    from main import app
    from core import storage
    from storage.postgres_adapter import DBApplication
    
    await storage.initialize_db()
    
    # Create a dummy application first
    app_dict = await storage.create_application(
        {"company_name": "Test PD Co", "pan": "ABCDE1234F"},
        tenant_id="tenant_alpha"
    )
    app_id = app_dict["id"]
    
    client = TestClient(app)
    local_user = {"username": "local_dev", "role": "admin", "tenant_id": "tenant_alpha"}
    token = create_token(local_user)
    headers = {"Authorization": f"Bearer {token}"}
    
    # Valid payload
    payload = {
        "interviewer": "Interviewer Sharma",
        "transcript": "The business has been growing at 15% CAGR with solid succession plans."
    }
    
    response = client.post(
        f"/api/application/{app_id}/pd",
        headers=headers,
        json=payload
    )
    assert response.status_code == 200
    assert response.json()["status"] == "TRIGGERED"
    
    # Verify that the transcript note was added to the application
    app_data = await storage.get_application(app_id)
    notes = app_data["ucso_data"].get("human_notes", {}).get("notes", [])
    assert len(notes) > 0
    assert any(n.get("text") == payload["transcript"] and n.get("author") == payload["interviewer"] for n in notes)
    
    # Clean up test app
    async with storage.Session() as session:
        db_app = await session.get(DBApplication, app_id)
        if db_app:
            await session.delete(db_app)
            await session.commit()


def test_alembic_config_loading():
    """Verify that Alembic configuration loads correctly and the ini file exists."""
    from alembic.config import Config
    import os
    
    ini_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend", "alembic.ini"))
    assert os.path.exists(ini_path)
    
    cfg = Config(ini_path)
    assert cfg.get_main_option("script_location") == "alembic"

