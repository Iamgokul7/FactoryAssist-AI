"""Password hashing and token helpers for document-management access control.

No third-party crypto dependency is added: PBKDF2-HMAC-SHA256 from the standard
library is a well-understood, salted, deliberately slow KDF, and the iteration
count is stored with each hash so it can be raised later without invalidating
existing passwords.

Plaintext passwords and raw session tokens are never written to the database,
the audit log or application logs.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import string

# OWASP's 2023 floor for PBKDF2-HMAC-SHA256 is 600,000 iterations. That is a
# deliberate choice for a low-traffic, on-premise plant application.
PBKDF2_ITERATIONS = 600_000
_SALT_BYTES = 16
_ALGORITHM = "pbkdf2_sha256"

MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 256


def hash_password(password: str, *, iterations: int = PBKDF2_ITERATIONS) -> str:
    """Return a salted, encoded PBKDF2 hash (never the password itself)."""
    if not password:
        raise ValueError("Password must not be empty")
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return "$".join(
        (
            _ALGORITHM,
            str(iterations),
            _b64(salt),
            _b64(digest),
        )
    )


def verify_password(password: str, stored: str) -> bool:
    """Constant-time check of ``password`` against an encoded hash."""
    if not password or not stored:
        return False
    try:
        algorithm, iterations_text, salt_text, digest_text = stored.split("$", 3)
        if algorithm != _ALGORITHM:
            return False
        iterations = int(iterations_text)
        salt = _unb64(salt_text)
        expected = _unb64(digest_text)
    except (ValueError, TypeError):
        return False

    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(candidate, expected)


def password_problem(password: str) -> str | None:
    """Return a user-facing problem with ``password``, or ``None`` if it is fine."""
    if len(password or "") < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters long."
    if len(password) > MAX_PASSWORD_LENGTH:
        return f"Password must be at most {MAX_PASSWORD_LENGTH} characters long."
    classes = sum(
        (
            any(char.islower() for char in password),
            any(char.isupper() for char in password),
            any(char.isdigit() for char in password),
            any(not char.isalnum() for char in password),
        )
    )
    if classes < 3:
        return (
            "Password must combine at least three of: lowercase letters, "
            "uppercase letters, digits and symbols."
        )
    return None


def new_session_token() -> str:
    """A high-entropy bearer token for one session cookie."""
    return secrets.token_urlsafe(32)


def new_csrf_token() -> str:
    """A per-session token echoed by the browser on mutating requests."""
    return secrets.token_urlsafe(24)


def token_fingerprint(token: str) -> str:
    """SHA-256 of a token, which is what the database stores."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_password(length: int = 20) -> str:
    """A random password for administrators who prefer not to invent one."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*-_=+"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _b64(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.b64decode(value.encode("ascii"), validate=True)
