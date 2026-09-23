"""
Auth module for Study-Life Orchestrator.

Uses:
- passlib[bcrypt] for password hashing (PBKDF2-SHA256)
- itsdangerous URLSafeTimedSerializer for session tokens
"""

import os
from pathlib import Path
from typing import Optional
from passlib.hash import pbkdf2_sha256
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

# --- Config ---
_DATA_DIR = Path(__file__).resolve().parent / "data"
_HASH_FILE = _DATA_DIR / "auth_hash.txt"

_DEFAULT_USERNAME = "constantingrandidier@gmail.com"
_DEFAULT_PASSWORD = "StudyLife2025!"
_SECRET_KEY = os.environ.get("SLO_SECRET_KEY", "slo-super-secret-key-change-in-prod")
_TOKEN_MAX_AGE = 60 * 60 * 24 * 7  # 7 days in seconds

_serializer = URLSafeTimedSerializer(_SECRET_KEY)


def _ensure_hash_file() -> str:
    """
    Return the stored password hash. If the hash file doesn't exist yet,
    generate it from the default password and persist it.
    """
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not _HASH_FILE.exists():
        hashed = pbkdf2_sha256.hash(_DEFAULT_PASSWORD)
        _HASH_FILE.write_text(hashed, encoding="utf-8")
        return hashed
    return _HASH_FILE.read_text(encoding="utf-8").strip()


# Initialise on module import (called once at startup)
_stored_hash: str = _ensure_hash_file()


def check_credentials(username: str, password: str) -> bool:
    """Return True if username and password match the stored credentials."""
    expected_username = os.environ.get("SLO_USERNAME", _DEFAULT_USERNAME)
    if username != expected_username:
        return False
    return pbkdf2_sha256.verify(password, _stored_hash)


def create_token(username: str) -> str:
    """Create a signed, time-limited session token for the given username."""
    return _serializer.dumps(username, salt="sl-session")


def verify_token(token: str) -> Optional[str]:
    """
    Verify the session token.

    Returns the username embedded in the token if valid,
    or None if the token is expired / invalid.
    """
    try:
        username = _serializer.loads(token, salt="sl-session", max_age=_TOKEN_MAX_AGE)
        return username
    except (BadSignature, SignatureExpired):
        return None
