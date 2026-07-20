import os
import json
import time
from collections import defaultdict
from fastapi import APIRouter, HTTPException, Depends, Request
from auth import verify_password, create_token
from dependencies import get_current_user_or_agent

from core import redis_broker

from pydantic import BaseModel

class LoginRequest(BaseModel):
    username: str
    password: str

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

# In-memory rate limiting: ip_address -> list of timestamps
login_attempts = defaultdict(list)

@router.post("/login")
async def login(payload: LoginRequest, request: Request):
    username = payload.username
    password = payload.password
    
    client_ip = request.client.host if request.client else "unknown"
    current_time = time.time()
    
    # 1. Distributed Rate Limiting via Redis
    rate_key = f"rate_limit:login:{client_ip}"
    redis_success = False
    try:
        if not redis_broker.client:
            await redis_broker.connect()
        attempts = await redis_broker.client.get(rate_key)
        attempts_count = int(attempts) if attempts else 0
        if attempts_count >= 5:
            raise HTTPException(
                status_code=429,
                detail="Too many login attempts. Please try again after 60 seconds."
            )
        redis_success = True
    except HTTPException:
        raise
    except Exception:
        # Fallback to local dict in case Redis is down
        login_attempts[client_ip] = [t for t in login_attempts[client_ip] if current_time - t < 60]
        if len(login_attempts[client_ip]) >= 5:
            raise HTTPException(
                status_code=429,
                detail="Too many login attempts. Please try again after 60 seconds."
            )
    
    from config import LOCAL_STORAGE_DIR
    users_path = os.path.join(LOCAL_STORAGE_DIR, "users.json")
    if not os.path.exists(users_path):
        raise HTTPException(status_code=500, detail="User database not initialized")
        
    try:
        with open(users_path, "r", encoding="utf-8") as f:
            users = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load user database: {str(e)}")
        
    user = users.get(username)
    if not user or not verify_password(password, user["password_hash"], user["salt"]):
        # Increment attempt counter (Redis or local dict fallback)
        if redis_success:
            try:
                pipe = redis_broker.client.pipeline()
                await pipe.incr(rate_key)
                await pipe.expire(rate_key, 60)
                await pipe.execute()
            except Exception:
                login_attempts[client_ip].append(current_time)
        else:
            login_attempts[client_ip].append(current_time)
        raise HTTPException(status_code=401, detail="Invalid username or password")
        
    # Reset attempts on success
    if redis_success:
        try:
            await redis_broker.client.delete(rate_key)
        except Exception:
            pass
    if client_ip in login_attempts:
        del login_attempts[client_ip]
        
    token_payload = {
        "username": user["username"],
        "role": user["role"],
        "tenant_id": user["tenant_id"],
        "name": user["name"]
    }
    token = create_token(token_payload)
    return {
        "token": token,
        "user": token_payload
    }

@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user_or_agent)):
    return current_user
