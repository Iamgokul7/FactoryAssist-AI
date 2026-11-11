"""SQLite-backed users, sessions and audit log for document governance.

Why SQLite: the application already deploys as a single local process with a
file-based vector store, so an embedded database adds no service to operate
while still giving real transactions, unique constraints and durable sessions.

Security properties:
* Passwords are stored only as salted PBKDF2 hashes (see ``core.security``).
* Session cookies carry a random token; the database stores only its SHA-256
  fingerprint, so a leaked database cannot be replayed as a session.
* Each session has its own CSRF token.
* Every management action and login attempt is written to the audit log, with
  no passwords, tokens or API keys in the recorded detail.
"""

from __future__ import annotations

import argparse
import getpass
import logging
import sqlite3
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from backend.core.config import settings
from backend.core.security import (
    hash_password,
    new_csrf_token,
    new_session_token,
    password_problem,
    token_fingerprint,
    verify_password,
)

logger = logging.getLogger(__name__)

ROLE_ADMIN = "admin"
ROLE_SOP_MANAGER = "sop_manager"
ROLE_EMPLOYEE = "employee"
ROLES: tuple[str, ...] = (ROLE_ADMIN, ROLE_SOP_MANAGER, ROLE_EMPLOYEE)
MANAGEMENT_ROLES: frozenset[str] = frozenset({ROLE_ADMIN, ROLE_SOP_MANAGER})

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE COLLATE NOCASE,
    full_name     TEXT NOT NULL DEFAULT '',
    role          TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL,
    last_login_at TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    csrf_token TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    ip         TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp    TEXT NOT NULL,
    username     TEXT,
    user_id      INTEGER,
    action       TEXT NOT NULL,
    document_key TEXT,
    revision     TEXT,
    result       TEXT NOT NULL,
    detail       TEXT,
    ip           TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_sessions_expiry ON sessions(expires_at);
"""


@dataclass(slots=True)
class User:
    """A stored account, without its password hash."""

    id: int
    username: str
    full_name: str
    role: str
    is_active: bool
    created_at: str
    last_login_at: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "username": self.username,
            "full_name": self.full_name,
            "role": self.role,
            "is_active": self.is_active,
            "created_at": self.created_at,
            "last_login_at": self.last_login_at,
        }


@dataclass(slots=True)
class SessionUser:
    """The authenticated caller behind a session cookie."""

    user_id: int
    username: str
    full_name: str
    role: str
    csrf_token: str
    expires_at: str

    @property
    def is_manager(self) -> bool:
        return self.role in MANAGEMENT_ROLES

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.user_id,
            "username": self.username,
            "full_name": self.full_name,
            "role": self.role,
            "can_manage_documents": self.is_manager,
            "can_manage_users": self.role == ROLE_ADMIN,
        }


class AuthError(RuntimeError):
    """Raised for an expected authentication or account-management failure."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(moment: datetime) -> str:
    return moment.isoformat(timespec="seconds")


class AuthStore:
    """Users, sessions and audit records in one SQLite file."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path or settings.auth_database_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialise()

    # --- plumbing ---

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=10.0)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA journal_mode = WAL")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialise(self) -> None:
        with self._connect() as connection:
            connection.executescript(_SCHEMA)

    # --- users ---

    def user_count(self) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS total FROM users").fetchone()
        return int(row["total"]) if row else 0

    def create_user(
        self,
        username: str,
        password: str,
        role: str,
        *,
        full_name: str = "",
    ) -> User:
        username = (username or "").strip()
        if not username or len(username) > 64:
            raise AuthError("Enter a username of 1-64 characters.")
        if role not in ROLES:
            raise AuthError(f"Role must be one of: {', '.join(ROLES)}.")
        problem = password_problem(password)
        if problem:
            raise AuthError(problem)

        try:
            with self._connect() as connection:
                cursor = connection.execute(
                    "INSERT INTO users (username, full_name, role, password_hash, "
                    "is_active, created_at) VALUES (?, ?, ?, ?, 1, ?)",
                    (username, (full_name or "").strip(), role, hash_password(password), iso(utc_now())),
                )
                user_id = int(cursor.lastrowid)
        except sqlite3.IntegrityError as exc:
            raise AuthError(f"The username '{username}' already exists.") from exc

        user = self.get_user(user_id)
        if user is None:  # pragma: no cover - defensive
            raise AuthError("The account could not be created.")
        return user

    def get_user(self, user_id: int) -> User | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return _user_from_row(row)

    def get_user_by_username(self, username: str) -> User | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE username = ? COLLATE NOCASE", (username.strip(),)
            ).fetchone()
        return _user_from_row(row)

    def list_users(self) -> list[User]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM users ORDER BY username").fetchall()
        return [user for user in (_user_from_row(row) for row in rows) if user]

    def update_user(
        self,
        user_id: int,
        *,
        role: str | None = None,
        is_active: bool | None = None,
        password: str | None = None,
        full_name: str | None = None,
    ) -> User:
        updates: list[str] = []
        values: list[Any] = []

        if role is not None:
            if role not in ROLES:
                raise AuthError(f"Role must be one of: {', '.join(ROLES)}.")
            updates.append("role = ?")
            values.append(role)
        if is_active is not None:
            updates.append("is_active = ?")
            values.append(1 if is_active else 0)
        if full_name is not None:
            updates.append("full_name = ?")
            values.append(full_name.strip())
        if password is not None:
            problem = password_problem(password)
            if problem:
                raise AuthError(problem)
            updates.append("password_hash = ?")
            values.append(hash_password(password))

        if not updates:
            user = self.get_user(user_id)
            if user is None:
                raise AuthError("Account not found.")
            return user

        values.append(user_id)
        with self._connect() as connection:
            cursor = connection.execute(
                f"UPDATE users SET {', '.join(updates)} WHERE id = ?",  # noqa: S608 - fixed column names
                values,
            )
            if cursor.rowcount == 0:
                raise AuthError("Account not found.")
            if password is not None or is_active is False:
                # Changing a password or disabling an account must not leave a
                # previously issued session usable.
                connection.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))

        updated = self.get_user(user_id)
        if updated is None:  # pragma: no cover - defensive
            raise AuthError("Account not found.")
        return updated

    def verify_credentials(self, username: str, password: str) -> User | None:
        """Return the active user when the password matches, else ``None``."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE username = ? COLLATE NOCASE", (username.strip(),)
            ).fetchone()
        if row is None:
            # Still run a hash comparison so a missing user is not obviously
            # faster than a wrong password.
            verify_password(password, hash_password("placeholder-password"))
            return None
        if not verify_password(password, str(row["password_hash"])):
            return None
        user = _user_from_row(row)
        if user is None or not user.is_active:
            return None
        return user

    def mark_login(self, user_id: int) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE users SET last_login_at = ? WHERE id = ?", (iso(utc_now()), user_id)
            )

    # --- sessions ---

    def create_session(
        self, user: User, *, ip: str | None = None, ttl_hours: int | None = None
    ) -> tuple[str, SessionUser]:
        token = new_session_token()
        csrf = new_csrf_token()
        created = utc_now()
        expires = created + timedelta(hours=ttl_hours or settings.session_ttl_hours)

        with self._connect() as connection:
            connection.execute("DELETE FROM sessions WHERE expires_at <= ?", (iso(created),))
            connection.execute(
                "INSERT INTO sessions (token_hash, user_id, csrf_token, created_at, "
                "expires_at, ip) VALUES (?, ?, ?, ?, ?, ?)",
                (token_fingerprint(token), user.id, csrf, iso(created), iso(expires), ip),
            )

        return token, SessionUser(
            user_id=user.id,
            username=user.username,
            full_name=user.full_name,
            role=user.role,
            csrf_token=csrf,
            expires_at=iso(expires),
        )

    def get_session(self, token: str) -> SessionUser | None:
        """Resolve a cookie token to a live session, or ``None``."""
        if not token:
            return None
        fingerprint = token_fingerprint(token)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT s.csrf_token, s.expires_at, u.id, u.username, u.full_name, u.role, "
                "u.is_active FROM sessions s JOIN users u ON u.id = s.user_id "
                "WHERE s.token_hash = ?",
                (fingerprint,),
            ).fetchone()
            if row is None:
                return None
            if str(row["expires_at"]) <= iso(utc_now()):
                connection.execute("DELETE FROM sessions WHERE token_hash = ?", (fingerprint,))
                return None
            if not int(row["is_active"]):
                connection.execute("DELETE FROM sessions WHERE token_hash = ?", (fingerprint,))
                return None

        return SessionUser(
            user_id=int(row["id"]),
            username=str(row["username"]),
            full_name=str(row["full_name"] or ""),
            role=str(row["role"]),
            csrf_token=str(row["csrf_token"]),
            expires_at=str(row["expires_at"]),
        )

    def delete_session(self, token: str) -> None:
        if not token:
            return
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM sessions WHERE token_hash = ?", (token_fingerprint(token),)
            )

    def delete_user_sessions(self, user_id: int) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))

    def purge_expired_sessions(self) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM sessions WHERE expires_at <= ?", (iso(utc_now()),)
            )
        return int(cursor.rowcount or 0)

    # --- audit ---

    def audit(
        self,
        action: str,
        *,
        result: str,
        username: str | None = None,
        user_id: int | None = None,
        document_key: str | None = None,
        revision: str | None = None,
        detail: str | None = None,
        ip: str | None = None,
    ) -> None:
        """Write one audit record. Never pass secrets in ``detail``."""
        safe_detail = (detail or "")[:500] or None
        try:
            with self._connect() as connection:
                connection.execute(
                    "INSERT INTO audit_log (timestamp, username, user_id, action, "
                    "document_key, revision, result, detail, ip) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        iso(utc_now()),
                        username,
                        user_id,
                        action,
                        document_key,
                        revision,
                        result,
                        safe_detail,
                        ip,
                    ),
                )
        except sqlite3.Error as exc:  # pragma: no cover - audit must not break a request
            logger.error("Could not write audit record %s: %s", action, type(exc).__name__)

    def list_audit(self, *, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 500))
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM audit_log ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, max(0, offset)),
            ).fetchall()
        return [dict(row) for row in rows]

    def recent_login_failures(
        self, *, username: str, ip: str | None = None, window_minutes: int | None = None
    ) -> int:
        """Failed sign-ins for this account inside the window.

        Scoped to the username so one person mistyping a password cannot lock
        out colleagues signing in from the same plant network. The separate
        :meth:`recent_ip_failures` counter catches spraying across accounts.
        """
        minutes = window_minutes or settings.login_window_minutes
        cutoff = iso(utc_now() - timedelta(minutes=max(1, minutes)))
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS total FROM audit_log WHERE action = 'login_failed' "
                "AND timestamp >= ? AND username = ? COLLATE NOCASE",
                (cutoff, username.strip()),
            ).fetchone()
        return int(row["total"]) if row else 0

    def recent_ip_failures(
        self, *, ip: str | None, window_minutes: int | None = None
    ) -> int:
        """Failed sign-ins from this address, across all account names."""
        if not ip:
            return 0
        minutes = window_minutes or settings.login_window_minutes
        cutoff = iso(utc_now() - timedelta(minutes=max(1, minutes)))
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS total FROM audit_log WHERE action = 'login_failed' "
                "AND timestamp >= ? AND ip = ?",
                (cutoff, ip),
            ).fetchone()
        return int(row["total"]) if row else 0


def _user_from_row(row: sqlite3.Row | None) -> User | None:
    if row is None:
        return None
    return User(
        id=int(row["id"]),
        username=str(row["username"]),
        full_name=str(row["full_name"] or ""),
        role=str(row["role"]),
        is_active=bool(row["is_active"]),
        created_at=str(row["created_at"]),
        last_login_at=row["last_login_at"],
    )


# --- module-level shared instance -------------------------------------------

_store: AuthStore | None = None


def get_auth_store() -> AuthStore:
    """Return the process-wide store, reopening it if the path changed (tests)."""
    global _store
    if _store is None or _store.path != Path(settings.auth_database_path):
        _store = AuthStore()
    return _store


def reset_auth_store() -> None:
    """Forget the cached store (used by tests after changing settings)."""
    global _store
    _store = None


def ensure_initial_admin() -> str | None:
    """Create the first administrator from ``.env`` if no account exists yet.

    Returns the username that was created, or ``None`` when nothing was done.
    The password is never logged and never defaults to a hardcoded value.
    """
    store = get_auth_store()
    if store.user_count() > 0:
        return None

    username = settings.initial_admin_username.strip()
    password = settings.initial_admin_password

    if not username or not password:
        logger.warning(
            "No accounts exist yet. Set INITIAL_ADMIN_USERNAME and "
            "INITIAL_ADMIN_PASSWORD in .env, or run "
            "'python -m backend.services.auth_store create-admin'."
        )
        return None

    try:
        store.create_user(
            username,
            password,
            ROLE_ADMIN,
            full_name=settings.initial_admin_full_name,
        )
    except AuthError as exc:
        logger.error("Initial administrator was not created: %s", exc)
        store.audit(
            "admin_bootstrap",
            result="failed",
            username=username,
            detail=str(exc),
        )
        return None

    store.audit("admin_bootstrap", result="success", username=username, detail="initial administrator")
    logger.info("Initial administrator '%s' created from environment settings", username)
    return username


# --- command line -----------------------------------------------------------


def _cli() -> int:
    parser = argparse.ArgumentParser(
        description="Manage FactoryAssist AI accounts (SQLite)."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create-admin", help="create an administrator account")
    create.add_argument("--username", required=True)
    create.add_argument("--full-name", default="Plant Administrator")
    create.add_argument("--password", help="omit to be prompted without echo")

    reset = sub.add_parser("reset-password", help="set a new password for an account")
    reset.add_argument("--username", required=True)
    reset.add_argument("--password", help="omit to be prompted without echo")

    role = sub.add_parser("set-role", help="change an account role")
    role.add_argument("--username", required=True)
    role.add_argument("--role", required=True, choices=ROLES)

    sub.add_parser("list-users", help="list accounts")

    args = parser.parse_args()
    store = get_auth_store()

    try:
        if args.command == "create-admin":
            password = args.password or _prompt_password()
            user = store.create_user(
                args.username, password, ROLE_ADMIN, full_name=args.full_name
            )
            store.audit("user_created", result="success", username=user.username, detail="cli admin")
            print(f"Created administrator '{user.username}'.")
            return 0

        if args.command == "reset-password":
            password = args.password or _prompt_password()
            user = store.get_user_by_username(args.username)
            if user is None:
                print(f"No account named '{args.username}'.", file=sys.stderr)
                return 1
            store.update_user(user.id, password=password)
            store.audit("password_reset", result="success", username=user.username, detail="cli")
            print(f"Password updated for '{user.username}'. Existing sessions were ended.")
            return 0

        if args.command == "set-role":
            user = store.get_user_by_username(args.username)
            if user is None:
                print(f"No account named '{args.username}'.", file=sys.stderr)
                return 1
            store.update_user(user.id, role=args.role)
            store.audit(
                "role_changed", result="success", username=user.username, detail=f"cli -> {args.role}"
            )
            print(f"'{user.username}' is now {args.role}.")
            return 0

        if args.command == "list-users":
            users = store.list_users()
            if not users:
                print("No accounts yet.")
                return 0
            for user in users:
                state = "active" if user.is_active else "disabled"
                print(f"{user.username:24s} {user.role:12s} {state:9s} {user.full_name}")
            return 0
    except AuthError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 1  # pragma: no cover - argparse rejects unknown commands


def _prompt_password() -> str:
    while True:
        password = getpass.getpass("Password: ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("Passwords did not match. Try again.", file=sys.stderr)
            continue
        problem = password_problem(password)
        if problem:
            print(problem, file=sys.stderr)
            continue
        return password


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    raise SystemExit(_cli())
