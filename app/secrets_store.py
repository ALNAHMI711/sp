"""Encrypted, admin-managed integration credentials for the control panel."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from app.auth import DB as AUTH_DB

ALLOWED_SECRETS = {
    "GITHUB_WEBHOOK_SECRET",
    "GITHUB_APP_ID",
    "GITHUB_APP_PRIVATE_KEY",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_ALLOWED_USER_IDS",
    "AI_API_KEY",
}


def _paths() -> tuple[Path, Path]:
    db_path = Path(os.getenv("CONTROL_QUEUE_DB", AUTH_DB))
    return db_path, db_path.with_name("control-secrets.key")


def _connect() -> sqlite3.Connection:
    db_path, _ = _paths()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(db_path, timeout=10)
    db.execute(
        """CREATE TABLE IF NOT EXISTS integration_secrets (
            name TEXT PRIMARY KEY,
            encrypted_value BLOB NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    return db


def _fernet() -> Fernet:
    _, key_path = _paths()
    key_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        pass
    else:
        try:
            with os.fdopen(fd, "wb") as key_file:
                key_file.write(Fernet.generate_key())
                key_file.flush()
                os.fsync(key_file.fileno())
        except Exception:
            key_path.unlink(missing_ok=True)
            raise
    try:
        os.chmod(key_path, 0o600)
        key = key_path.read_bytes().strip()
        return Fernet(key)
    except (OSError, ValueError) as exc:
        raise RuntimeError("control-panel encryption key is unavailable") from exc


def get_secret(name: str, *, env_fallback: bool = True) -> str:
    if name not in ALLOWED_SECRETS:
        raise ValueError("unsupported integration secret")
    with _connect() as db:
        row = db.execute(
            "SELECT encrypted_value FROM integration_secrets WHERE name=?", (name,)
        ).fetchone()
    if row:
        try:
            return _fernet().decrypt(bytes(row[0])).decode("utf-8")
        except (InvalidToken, UnicodeDecodeError) as exc:
            raise RuntimeError("stored integration secret cannot be decrypted") from exc
    return os.getenv(name, "").strip() if env_fallback else ""


def set_secret(name: str, value: str) -> None:
    if name not in ALLOWED_SECRETS:
        raise ValueError("unsupported integration secret")
    if not isinstance(value, str) or not value.strip():
        raise ValueError("secret value must be a non-empty string")
    encrypted = _fernet().encrypt(value.strip().encode("utf-8"))
    with _connect() as db:
        db.execute(
            """INSERT INTO integration_secrets(name, encrypted_value, updated_at)
               VALUES (?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(name) DO UPDATE SET
                 encrypted_value=excluded.encrypted_value,
                 updated_at=CURRENT_TIMESTAMP""",
            (name, encrypted),
        )


def delete_secret(name: str) -> bool:
    if name not in ALLOWED_SECRETS:
        raise ValueError("unsupported integration secret")
    with _connect() as db:
        changed = db.execute(
            "DELETE FROM integration_secrets WHERE name=?", (name,)
        )
        return changed.rowcount == 1


def secret_status() -> dict[str, bool]:
    status = {}
    for name in sorted(ALLOWED_SECRETS):
        with _connect() as db:
            stored = db.execute(
                "SELECT 1 FROM integration_secrets WHERE name=?", (name,)
            ).fetchone()
        status[name] = bool(stored) or bool(os.getenv(name, "").strip())
    return status
