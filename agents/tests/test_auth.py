import sys
import os
import time

# Add backend directory to sys.path to enable imports
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from auth import hash_password, verify_password, create_token, verify_token

def test_password_hashing():
    password = "super_secure_password_123"
    hashed, salt = hash_password(password)
    
    assert hashed != password
    assert len(salt) > 0
    assert verify_password(password, hashed, salt) is True
    assert verify_password("wrong_password", hashed, salt) is False

def test_token_creation_and_verification():
    user_data = {
        "username": "test_user",
        "role": "underwriter",
        "tenant_id": "tenant_alpha"
    }
    token = create_token(user_data, expires_in_minutes=5)
    
    assert token is not None
    assert isinstance(token, str)
    assert "." in token
    
    payload = verify_token(token)
    assert payload is not None
    assert payload["username"] == "test_user"
    assert payload["role"] == "underwriter"
    assert payload["tenant_id"] == "tenant_alpha"

def test_token_expiration():
    user_data = {"username": "expiring_user"}
    # Create an expired token by passing negative minutes
    token = create_token(user_data, expires_in_minutes=-1)
    
    payload = verify_token(token)
    assert payload is None

def test_invalid_token_signatures():
    user_data = {"username": "test_user"}
    token = create_token(user_data, expires_in_minutes=5)
    
    # Tamper with the signature portion
    parts = token.split(".")
    tampered_token = f"{parts[0]}.wrongsignature123"
    
    payload = verify_token(tampered_token)
    assert payload is None
    
    # Tamper with the payload portion
    tampered_payload = parts[0] + "xyz"
    tampered_token_2 = f"{tampered_payload}.{parts[1]}"
    payload_2 = verify_token(tampered_token_2)
    assert payload_2 is None
