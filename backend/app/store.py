from __future__ import annotations

import binascii
import hashlib
import hmac
import json
import os
from pathlib import Path
import sqlite3
from uuid import uuid4

from app.models import (
    BusinessContext,
    ContextSummary,
    ConversationDetail,
    ConversationMessage,
    ConversationSummary,
    StoredBusinessContext,
    UserRecord,
)


def _hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return binascii.hexlify(digest).decode(), binascii.hexlify(salt).decode()


def verify_password(password: str, password_hash: str, salt_hex: str) -> bool:
    salt = binascii.unhexlify(salt_hex)
    digest, _ = _hash_password(password, salt)
    return hmac.compare_digest(digest, password_hash)


class EmailAlreadyExists(Exception):
    pass


class ContextStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialise()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialise(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS business_contexts (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL CHECK (status IN ('draft', 'approved')),
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL DEFAULT 'New conversation',
                    is_ready_to_save INTEGER NOT NULL DEFAULT 0,
                    readiness_reason TEXT NOT NULL DEFAULT 'Start describing the product or service to build its Business Context.',
                    portfolio_context_id TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS conversation_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_conversation_messages_conversation ON conversation_messages(conversation_id, id)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('admin', 'product_owner', 'sales')),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            try:
                connection.execute(
                    "ALTER TABLE conversations ADD COLUMN language TEXT NOT NULL DEFAULT 'en'"
                )
            except sqlite3.OperationalError:
                pass  # column already exists on databases created before this change

    def list(self) -> list[ContextSummary]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM business_contexts ORDER BY updated_at DESC"
            ).fetchall()

        summaries = []
        for row in rows:
            content = json.loads(row["content"])
            summaries.append(
                ContextSummary(
                    id=row["id"],
                    status=row["status"],
                    updated_at=row["updated_at"],
                    name=content.get("name") or content.get("solution_name") or "Untitled",
                    offering_type=content.get("offering_type", "product"),
                    short_summary=content.get("short_summary", ""),
                    relevant_industries=content.get("relevant_industries", []),
                    geographic_focus=content.get("geographic_focus", []),
                )
            )
        return summaries

    def get(self, context_id: str) -> StoredBusinessContext | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM business_contexts WHERE id = ?", (context_id,)
            ).fetchone()

        return self._to_context(row) if row else None

    def create(self, context: BusinessContext, status: str) -> StoredBusinessContext:
        context_id = str(uuid4())
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO business_contexts (id, status, content) VALUES (?, ?, ?)",
                (context_id, status, context.model_dump_json()),
            )
        return self.get(context_id)  # type: ignore[return-value]

    def update(
        self, context_id: str, context: BusinessContext, status: str
    ) -> StoredBusinessContext | None:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE business_contexts
                SET status = ?, content = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, context.model_dump_json(), context_id),
            )
        return self.get(context_id) if cursor.rowcount else None

    def delete_context(self, context_id: str) -> bool:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE conversations
                SET portfolio_context_id = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE portfolio_context_id = ?
                """,
                (context_id,),
            )
            cursor = connection.execute(
                "DELETE FROM business_contexts WHERE id = ?", (context_id,)
            )
        return bool(cursor.rowcount)

    def create_conversation(self, language: str = "en") -> ConversationDetail:
        conversation_id = str(uuid4())
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO conversations (id, language) VALUES (?, ?)",
                (conversation_id, language),
            )
        return self.get_conversation(conversation_id)  # type: ignore[return-value]

    def delete_conversation(self, conversation_id: str) -> bool:
        with self._connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM conversations WHERE id = ?", (conversation_id,)
            ).fetchone()
            if exists is None:
                return False
            connection.execute(
                "DELETE FROM conversation_messages WHERE conversation_id = ?",
                (conversation_id,),
            )
            connection.execute(
                "DELETE FROM conversations WHERE id = ?", (conversation_id,)
            )
        return True

    def list_conversations(self) -> list[ConversationSummary]:
        with self._connect() as connection:
            rows = connection.execute(self._conversation_query()).fetchall()
        return [self._to_conversation_summary(row) for row in rows]

    def get_conversation(self, conversation_id: str) -> ConversationDetail | None:
        with self._connect() as connection:
            row = connection.execute(
                self._conversation_query("WHERE c.id = ?"), (conversation_id,)
            ).fetchone()
            if row is None:
                return None
            message_rows = connection.execute(
                """
                SELECT id, role, content, created_at
                FROM conversation_messages
                WHERE conversation_id = ?
                ORDER BY id
                """,
                (conversation_id,),
            ).fetchall()

        summary = self._to_conversation_summary(row)
        return ConversationDetail(
            **summary.model_dump(),
            messages=[ConversationMessage(**dict(message)) for message in message_rows],
        )

    def add_conversation_turn(
        self,
        conversation_id: str,
        user_message: str,
        assistant_message: str,
        is_ready_to_save: bool,
        readiness_reason: str,
    ) -> ConversationDetail | None:
        title = self._conversation_title(user_message)
        with self._connect() as connection:
            exists = connection.execute(
                "SELECT title FROM conversations WHERE id = ?", (conversation_id,)
            ).fetchone()
            if exists is None:
                return None
            connection.execute(
                """
                INSERT INTO conversation_messages (conversation_id, role, content)
                VALUES (?, 'user', ?)
                """,
                (conversation_id, user_message),
            )
            connection.execute(
                """
                INSERT INTO conversation_messages (conversation_id, role, content)
                VALUES (?, 'assistant', ?)
                """,
                (conversation_id, assistant_message),
            )
            connection.execute(
                """
                UPDATE conversations
                SET title = CASE WHEN title = 'New conversation' THEN ? ELSE title END,
                    is_ready_to_save = ?,
                    readiness_reason = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    title,
                    int(is_ready_to_save),
                    readiness_reason,
                    conversation_id,
                ),
            )
        return self.get_conversation(conversation_id)

    def link_conversation_to_context(
        self, conversation_id: str, context_id: str
    ) -> ConversationDetail | None:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE conversations
                SET portfolio_context_id = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (context_id, conversation_id),
            )
        return self.get_conversation(conversation_id) if cursor.rowcount else None

    @staticmethod
    def _to_context(row: sqlite3.Row) -> StoredBusinessContext:
        content = json.loads(row["content"])
        # Backfill fields introduced after a context may have been saved,
        # so older rows keep loading instead of failing validation.
        content.setdefault("name", content.pop("solution_name", "Untitled"))
        content.setdefault("offering_type", "product")
        content.setdefault("people", [])
        return StoredBusinessContext(
            **content,
            id=row["id"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _conversation_query(where_clause: str = "") -> str:
        return f"""
            SELECT
                c.*,
                COUNT(m.id) AS message_count,
                COALESCE(
                    (SELECT content FROM conversation_messages
                     WHERE conversation_id = c.id ORDER BY id DESC LIMIT 1),
                    ''
                ) AS preview
            FROM conversations c
            LEFT JOIN conversation_messages m ON m.conversation_id = c.id
            {where_clause}
            GROUP BY c.id
            ORDER BY c.updated_at DESC
        """

    @staticmethod
    def _to_conversation_summary(row: sqlite3.Row) -> ConversationSummary:
        return ConversationSummary(
            id=row["id"],
            title=row["title"],
            preview=row["preview"],
            language=row["language"] if row["language"] in ("en", "nl", "de") else "en",
            is_ready_to_save=bool(row["is_ready_to_save"]),
            readiness_reason=row["readiness_reason"],
            portfolio_context_id=row["portfolio_context_id"],
            message_count=row["message_count"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _conversation_title(message: str) -> str:
        first_line = " ".join(message.split()).strip()
        return first_line if len(first_line) <= 64 else f"{first_line[:61]}…"

    def list_users(self) -> list[UserRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM users ORDER BY created_at ASC"
            ).fetchall()
        return [self._to_user_record(row) for row in rows]

    def get_user_by_email(self, email: str) -> sqlite3.Row | None:
        with self._connect() as connection:
            return connection.execute(
                "SELECT * FROM users WHERE email = ?", (email.casefold(),)
            ).fetchone()

    def create_user(self, email: str, password: str, role: str) -> UserRecord:
        user_id = str(uuid4())
        password_hash, salt = _hash_password(password)
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO users (id, email, password_hash, salt, role)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (user_id, email.strip().casefold(), password_hash, salt, role),
                )
        except sqlite3.IntegrityError as exc:
            raise EmailAlreadyExists(email) from exc
        return self._to_user_record(self.get_user_by_email(email))  # type: ignore[arg-type]

    def update_user(
        self, user_id: str, role: str | None = None, password: str | None = None
    ) -> UserRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            if row is None:
                return None
            new_role = role or row["role"]
            if password:
                password_hash, salt = _hash_password(password)
            else:
                password_hash, salt = row["password_hash"], row["salt"]
            connection.execute(
                """
                UPDATE users
                SET role = ?, password_hash = ?, salt = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (new_role, password_hash, salt, user_id),
            )
            updated = connection.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        return self._to_user_record(updated)

    def delete_user(self, user_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM users WHERE id = ?", (user_id,))
        return bool(cursor.rowcount)

    @staticmethod
    def _to_user_record(row: sqlite3.Row) -> UserRecord:
        return UserRecord(
            id=row["id"],
            email=row["email"],
            role=row["role"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
