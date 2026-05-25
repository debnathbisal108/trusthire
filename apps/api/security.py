"""
TrustHire AI — Security utilities.
Handles AES encryption for PII, JWT decoding, and helper functions.
"""

import base64
import os
from datetime import datetime, timezone
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from jose import JWTError, jwt

from .config import settings


# ─────────────────────────────────────────────────────────────────────────────
# PII ENCRYPTION  (Fernet symmetric AES-128-CBC + HMAC)
# ─────────────────────────────────────────────────────────────────────────────

def _get_fernet() -> Fernet:
    key = settings.encryption_key
    if not key:
        # Generate ephemeral key for development — NOT for production
        return Fernet(Fernet.generate_key())
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_pii(value: str) -> str:
    """Encrypt a PII string before storing in the database."""
    if not value:
        return value
    f = _get_fernet()
    return f.encrypt(value.encode()).decode()


def decrypt_pii(value: str) -> str:
    """Decrypt a PII string retrieved from the database."""
    if not value:
        return value
    try:
        f = _get_fernet()
        return f.decrypt(value.encode()).decode()
    except (InvalidToken, Exception):
        return "[decryption_error]"


# ─────────────────────────────────────────────────────────────────────────────
# JWT VERIFICATION  (validates tokens issued by NextAuth)
# ─────────────────────────────────────────────────────────────────────────────

def decode_jwt(token: str) -> dict:
    """
    Decode and verify a JWT token signed by NextAuth.
    NextAuth uses HS256 with NEXTAUTH_SECRET as the key.
    """
    try:
        payload = jwt.decode(
            token,
            settings.nextauth_secret,
            algorithms=[settings.jwt_algorithm],
            options={"verify_aud": False},
        )
        return payload
    except JWTError as e:
        raise ValueError(f"Invalid token: {e}") from e


def create_internal_token(user_id: str, org_id: str, role: str) -> str:
    """
    Create an internal JWT for service-to-service communication.
    Not used for frontend auth — that goes through NextAuth.
    """
    from datetime import timedelta

    payload = {
        "userId": user_id,
        "organizationId": org_id,
        "role": role,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "iss": "trusthire-api",
    }
    return jwt.encode(payload, settings.nextauth_secret, algorithm=settings.jwt_algorithm)


# ─────────────────────────────────────────────────────────────────────────────
# MISC HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def generate_slug(name: str) -> str:
    """Generate a URL-safe slug from an organization name."""
    import re
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    # Add short random suffix to avoid collisions
    suffix = base64.urlsafe_b64encode(os.urandom(4)).decode().rstrip("=").lower()
    return f"{slug}-{suffix}"
