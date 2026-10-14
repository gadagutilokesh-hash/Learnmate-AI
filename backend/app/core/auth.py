import os
import json
import hmac
import hashlib
import base64
import secrets
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, Depends
from app.core.config import settings
from app.db.storage import storage

logger = logging.getLogger(__name__)

# ==============================================================================
# Password Hashing with PBKDF2-HMAC-SHA256 (OWASP standard: 600,000 iterations)
# ==============================================================================
def hash_password(password: str) -> str:
    """Hashes a password with a cryptographically secure random salt using PBKDF2-HMAC-SHA256."""
    salt = secrets.token_hex(16)
    iterations = 600_000
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations
    )
    return f"pbkdf2_sha256${iterations}${salt}${derived.hex()}"

def verify_password(password: str, hashed_password: str) -> bool:
    """Verifies a plain password against the stored PBKDF2-HMAC-SHA256 hash."""
    try:
        parts = hashed_password.split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
            return False
        iterations = int(parts[1])
        salt = parts[2]
        expected_hex = parts[3]
        derived = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations
        )
        return hmac.compare_digest(derived.hex(), expected_hex)
    except Exception as e:
        logger.warning(f"Error during password verification: {e}")
        return False

# ==============================================================================
# Cryptographic Token Management (HMAC-SHA256 Signed JWT)
# ==============================================================================
def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")

def _b64url_decode(data_str: str) -> bytes:
    padding = "=" * ((4 - len(data_str) % 4) % 4)
    return base64.urlsafe_b64decode(data_str + padding)

def create_access_token(user_id: str, email: str, role: str = "user", expires_delta: Optional[timedelta] = None) -> str:
    """Generates a cryptographically signed HMAC-SHA256 access token."""
    now = datetime.now(timezone.utc)
    if expires_delta is None:
        expires_delta = timedelta(hours=settings.SESSION_EXPIRE_HOURS)
    exp = now + expires_delta

    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp())
    }

    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")

    signature = hmac.new(settings.AUTH_SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256).digest()
    sig_b64 = _b64url_encode(signature)

    return f"{header_b64}.{payload_b64}.{sig_b64}"

def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decodes and validates a signed access token. Returns payload dict or None if invalid/expired."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header_b64, payload_b64, sig_b64 = parts

        signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
        expected_sig = hmac.new(settings.AUTH_SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256).digest()
        provided_sig = _b64url_decode(sig_b64)

        if not hmac.compare_digest(expected_sig, provided_sig):
            return None

        payload_bytes = _b64url_decode(payload_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))

        now_ts = int(datetime.now(timezone.utc).timestamp())
        if payload.get("exp") and payload["exp"] < now_ts:
            return None

        return payload
    except Exception as e:
        logger.debug(f"Failed to decode access token: {e}")
        return None

# ==============================================================================
# FastAPI Auth Dependencies
# ==============================================================================
def extract_token_from_request(request: Request) -> Optional[str]:
    """Extracts bearer token from Authorization header or HttpOnly session cookie."""
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        if token:
            return token

    cookie_token = request.cookies.get("learnmate_session")
    if cookie_token and cookie_token.strip():
        return cookie_token.strip()

    return None

async def get_optional_user(request: Request) -> Optional[Dict[str, Any]]:
    """
    Returns the authenticated user dict if a valid token is provided.
    Returns None if the request is unauthenticated (e.g., visitor exploring shared demo).
    """
    token = extract_token_from_request(request)
    if not token:
        return None

    payload = decode_access_token(token)
    if not payload:
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    user = storage.get_user_by_id(user_id)
    return user

async def get_current_user(optional_user: Optional[Dict[str, Any]] = Depends(get_optional_user)) -> Dict[str, Any]:
    """
    Enforces authentication. Raises 401 Unauthorized if the user is not logged in.
    """
    if not optional_user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required to access this resource",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return optional_user

async def get_admin_user(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Enforces administrator authorization. Raises 403 Forbidden if user is not an admin.
    """
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=403,
            detail="Administrator privileges required for this action"
        )
    return current_user
