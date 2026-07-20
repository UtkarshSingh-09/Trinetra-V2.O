import hmac
import hashlib
import json
import base64
import secrets
import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("trinetra-backend.auth")

from config import JWT_SECRET_KEY as SECRET_KEY, OIDC_ISSUER, OIDC_AUDIENCE
import time
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes

def base64url_decode(payload: str) -> bytes:
    rem = len(payload) % 4
    if rem > 0:
        payload += "=" * (4 - rem)
    return base64.urlsafe_b64decode(payload.encode('utf-8'))

_oidc_config_cache = {}

def get_oidc_jwks(issuer: str):
    now = time.time()
    cache_entry = _oidc_config_cache.get(issuer)
    if cache_entry and (now - cache_entry["fetched_at"] < 3600):
        return cache_entry["keys"]
        
    try:
        import requests as r
        config_url = f"{issuer.rstrip('/')}/.well-known/openid-configuration"
        config_resp = r.get(config_url, timeout=10)
        config_resp.raise_for_status()
        jwks_uri = config_resp.json().get("jwks_uri")
        
        jwks_resp = r.get(jwks_uri, timeout=10)
        jwks_resp.raise_for_status()
        keys = jwks_resp.json().get("keys", [])
        
        _oidc_config_cache[issuer] = {
            "fetched_at": now,
            "keys": keys
        }
        return keys
    except Exception as e:
        print(f"⚠️ Failed to retrieve JWKs from OIDC issuer {issuer}: {e}")
        if cache_entry:
            return cache_entry["keys"]
        return []

def verify_oidc_token(token: str, issuer: str, audience: str = None) -> dict | None:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
            
        header_b64, payload_b64, signature_b64 = parts
        
        header_json = base64url_decode(header_b64).decode('utf-8')
        header = json.loads(header_json)
        
        kid = header.get("kid")
        alg = header.get("alg")
        if alg != "RS256" or not kid:
            return None
            
        jwks = get_oidc_jwks(issuer)
        matching_key = None
        for key in jwks:
            if key.get("kid") == kid:
                matching_key = key
                break
                
        if not matching_key:
            return None
            
        n_bytes = base64url_decode(matching_key["n"])
        e_bytes = base64url_decode(matching_key["e"])
        n = int.from_bytes(n_bytes, 'big')
        e = int.from_bytes(e_bytes, 'big')
        
        public_numbers = RSAPublicNumbers(e, n)
        public_key = public_numbers.public_key()
        
        message = f"{header_b64}.{payload_b64}".encode('utf-8')
        sig = base64url_decode(signature_b64)
        
        public_key.verify(
            sig,
            message,
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        
        payload_json = base64url_decode(payload_b64).decode('utf-8')
        payload = json.loads(payload_json)
        
        exp = payload.get("exp", 0)
        if time.time() > exp:
            return None
            
        iss = payload.get("iss", "")
        if iss.rstrip('/') != issuer.rstrip('/'):
            return None
            
        if audience:
            aud = payload.get("aud", "")
            if isinstance(aud, list):
                if audience not in aud:
                    return None
            elif aud != audience:
                return None
                
        username = payload.get("preferred_username") or payload.get("sub") or payload.get("email")
        role = "underwriter"
        if "roles" in payload:
            roles = payload["roles"]
            if isinstance(roles, list) and roles:
                role = roles[0]
            elif isinstance(roles, str):
                role = roles
        elif "resource_access" in payload:
            for app_client in payload["resource_access"].values():
                app_roles = app_client.get("roles", [])
                if app_roles:
                    role = app_roles[0]
                    break
        
        return {
            "username": username,
            "role": role,
            "tenant_id": payload.get("tenant_id", "tenant_alpha"),
            "name": payload.get("name") or payload.get("preferred_username") or username
        }
    except Exception as e:
        print(f"⚠️ OIDC token verification error: {e}")
        return None

def hash_password(password: str, salt: str = None) -> tuple[str, str]:
    if not salt:
        salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac(
        'sha256', 
        password.encode('utf-8'), 
        salt.encode('utf-8'), 
        100000
    ).hex()
    return hashed, salt

def verify_password(password: str, hashed: str, salt: str) -> bool:
    new_hashed, _ = hash_password(password, salt)
    return secrets.compare_digest(new_hashed, hashed)

def create_token(user_data: dict, expires_in_minutes: int = 120) -> str:
    payload = {
        **user_data,
        "exp": (datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes)).timestamp()
    }
    payload_json = json.dumps(payload)
    payload_b64 = base64.urlsafe_b64encode(payload_json.encode('utf-8')).decode('utf-8')
    
    signature = hmac.new(
        SECRET_KEY.encode('utf-8'),
        payload_b64.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return f"{payload_b64}.{signature}"

def verify_token(token: str) -> dict | None:
    try:
        parts = token.split(".")
        if len(parts) == 3:
            if OIDC_ISSUER:
                res = verify_oidc_token(token, OIDC_ISSUER, OIDC_AUDIENCE)
                if res:
                    return res
            return None
            
        if len(parts) != 2:
            return None
        payload_b64, signature = parts
        
        expected_signature = hmac.new(
            SECRET_KEY.encode('utf-8'),
            payload_b64.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(expected_signature, signature):
            return None
            
        payload_json = base64.urlsafe_b64decode(payload_b64.encode('utf-8')).decode('utf-8')
        payload = json.loads(payload_json)
        
        if datetime.now(timezone.utc).timestamp() > payload.get("exp", 0):
            return None
            
        return payload
    except Exception as e:
        logger.debug(f"Failed to verify signature token: {e}")
        return None

def init_user_db(path: str):
    import os
    os.makedirs(os.path.dirname(path), exist_ok=True)
    
    users = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                users = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read user database file {path}: {e}. Initializing empty.")
            
    admin_pw = os.getenv("ADMIN_PASSWORD", "")
    underwriter_pw = os.getenv("UNDERWRITER_PASSWORD", "")
    
    is_ephemeral_admin = False
    is_ephemeral_underwriter = False
    
    if not admin_pw:
        admin_pw = secrets.token_hex(8)
        is_ephemeral_admin = True
        
    if not underwriter_pw:
        underwriter_pw = secrets.token_hex(8)
        is_ephemeral_underwriter = True

    defaults = [
        {"username": "alpha_underwriter", "password": underwriter_pw, "tenant_id": "tenant_alpha", "role": "underwriter", "name": "Alpha Underwriter"},
        {"username": "beta_underwriter", "password": underwriter_pw, "tenant_id": "tenant_beta", "role": "underwriter", "name": "Beta Underwriter"},
        {"username": "admin", "password": admin_pw, "tenant_id": "tenant_admin", "role": "admin", "name": "Super Admin"}
    ]
    
    updated = False
    for user_def in defaults:
        username = user_def["username"]
        if username not in users:
            hashed, salt = hash_password(user_def["password"])
            users[username] = {
                "username": username,
                "password_hash": hashed,
                "salt": salt,
                "tenant_id": user_def["tenant_id"],
                "role": user_def["role"],
                "name": user_def["name"]
            }
            if username == "admin" and is_ephemeral_admin:
                print("\n" + "!"*60)
                print(f"🔑 SECURITY ALERT: Generated ephemeral Super Admin password: {admin_pw}")
                print("Configure ADMIN_PASSWORD in your backend/.env to override this fallback.")
                print("!"*60 + "\n")
            elif username.endswith("_underwriter") and is_ephemeral_underwriter:
                print("\n" + "!"*60)
                print(f"🔑 SECURITY ALERT: Generated ephemeral Underwriter password: {underwriter_pw}")
                print("Configure UNDERWRITER_PASSWORD in your backend/.env to override this fallback.")
                print("!"*60 + "\n")
            updated = True
            
    if updated or not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=2, ensure_ascii=False)


