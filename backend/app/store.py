from __future__ import annotations

import binascii
import hashlib
import hmac
import json
import os
from pathlib import Path
import sqlite3
from types import SimpleNamespace
from uuid import uuid4

from app.leads import RETENTION_DAYS, LeadBrief, LeadRow
from app.models import (
    BusinessContext,
    ContextSummary,
    ConversationDetail,
    ConversationMessage,
    ConversationSummary,
    StoredBusinessContext,
    StoryDraftContent,
    UploadRecord,
    UserRecord,
)

CONVERSATION_KINDS = ("context", "knowledge", "product_owner", "lead")
# Statuses in which the user (or the model) may still change a story proposal.
EDITABLE_STORY_STATUSES = ("draft", "failed")


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
            for statement in (
                "ALTER TABLE business_contexts ADD COLUMN owner_id TEXT",
                "ALTER TABLE conversations ADD COLUMN owner_id TEXT",
                "ALTER TABLE conversations ADD COLUMN kind TEXT NOT NULL DEFAULT 'context'",
            ):
                try:
                    connection.execute(statement)
                except sqlite3.OperationalError:
                    pass
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_business_contexts_owner_status ON business_contexts(owner_id, status)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_conversations_owner_kind ON conversations(owner_id, kind, updated_at)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS uploads (
                    id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    kind TEXT NOT NULL CHECK (kind IN ('context_evidence', 'workspace')),
                    filename TEXT NOT NULL,
                    media_type TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    storage_path TEXT NOT NULL,
                    page_count INTEGER,
                    visibility TEXT NOT NULL DEFAULT 'private' CHECK (visibility IN ('org', 'private')),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS upload_links (
                    upload_id TEXT PRIMARY KEY,
                    conversation_id TEXT,
                    context_id TEXT,
                    FOREIGN KEY (upload_id) REFERENCES uploads(id)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_uploads_owner_kind ON uploads(owner_id, kind, created_at)"
            )
            # Product Owner story proposals. A row is versioned: every change by the
            # model or the user raises the version and clears any approval, so a
            # confirmation only ever covers the exact version the user saw.
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS story_drafts (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    owner_id TEXT NOT NULL,
                    language TEXT NOT NULL DEFAULT 'en',
                    version INTEGER NOT NULL DEFAULT 1,
                    status TEXT NOT NULL DEFAULT 'draft'
                        CHECK (status IN ('draft', 'creating', 'created', 'failed', 'uncertain')),
                    content TEXT NOT NULL,
                    approved_version INTEGER,
                    approved_content TEXT,
                    approved_by TEXT,
                    approved_at TEXT,
                    confirmation_id TEXT UNIQUE,
                    devops_id INTEGER,
                    devops_url TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_story_drafts_conversation ON story_drafts(conversation_id, created_at)"
            )
            # What SIP read from Azure DevOps for a question, so it comes back after a reload.
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS work_item_results (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    owner_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            # Proposed changes to existing stories: versioned like story_drafts, plus the
            # revision the change was planned against and the before/after list shown.
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS work_item_changes (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    owner_id TEXT NOT NULL,
                    work_item_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    status TEXT NOT NULL DEFAULT 'draft'
                        CHECK (status IN ('draft', 'applying', 'applied', 'failed', 'uncertain')),
                    content TEXT NOT NULL,
                    ops TEXT NOT NULL,
                    changes TEXT NOT NULL,
                    base_rev INTEGER NOT NULL,
                    approved_version INTEGER,
                    approved_by TEXT,
                    approved_at TEXT,
                    confirmation_id TEXT UNIQUE,
                    error TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_work_item_changes_conversation ON work_item_changes(conversation_id, created_at)"
            )
            try:
                # Expand only: rows from before this column count as user stories.
                connection.execute(
                    "ALTER TABLE work_item_changes ADD COLUMN work_item_type TEXT NOT NULL DEFAULT 'User Story'"
                )
            except sqlite3.OperationalError:
                pass  # column already exists
            # Lead finder. A list and its rows expire together (RETENTION_DAYS); see
            # purge_expired_leads. Rows hold organisation facts only (app/leads.py).
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS lead_lists (
                    id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    conversation_id TEXT,
                    context_id TEXT NOT NULL,
                    context_name TEXT NOT NULL,
                    brief TEXT NOT NULL,
                    language TEXT NOT NULL DEFAULT 'nl',
                    status TEXT NOT NULL DEFAULT 'running'
                        CHECK (status IN ('running', 'done', 'failed', 'interrupted')),
                    error TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    expires_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS lead_rows (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    list_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (list_id) REFERENCES lead_lists(id)
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_lead_rows_list ON lead_rows(list_id, id)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_lead_lists_expires ON lead_lists(expires_at)")
            try:
                # The search brief the intake conversation has agreed so far.
                connection.execute("ALTER TABLE conversations ADD COLUMN lead_brief TEXT")
            except sqlite3.OperationalError:
                pass
            # Every saved state of a Business Context: who, when, how. A context and its
            # versions are deleted together (delete_context).
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS business_context_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    context_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    content TEXT NOT NULL,
                    changed_by TEXT,
                    source TEXT NOT NULL,
                    restored_from INTEGER,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (context_id, version)
                )
                """
            )
            # Contexts saved before versions existed start at version 1 as they are now.
            connection.execute(
                """
                INSERT INTO business_context_versions (context_id, version, status, content, source, created_at)
                SELECT c.id, 1, c.status, c.content, 'existing', c.updated_at FROM business_contexts c
                WHERE NOT EXISTS (SELECT 1 FROM business_context_versions v WHERE v.context_id = c.id)
                """
            )
            try:
                # A context conversation that updates an existing Business Context.
                connection.execute("ALTER TABLE conversations ADD COLUMN updates_context_id TEXT")
            except sqlite3.OperationalError:
                pass
            try:
                # Who started a lead list, shown to the sales team that shares the lists.
                connection.execute("ALTER TABLE lead_lists ADD COLUMN created_by TEXT")
            except sqlite3.OperationalError:
                pass

    def backfill_owner(self, owner_id: str) -> None:
        """Claim legacy rows for the bootstrap account; NULL must never mean public."""
        with self._connect() as connection:
            connection.execute(
                "UPDATE business_contexts SET owner_id = ? WHERE owner_id IS NULL", (owner_id,)
            )
            connection.execute(
                "UPDATE conversations SET owner_id = ? WHERE owner_id IS NULL", (owner_id,)
            )

    def list(self, owner_id: str, is_admin: bool = False, approved_only: bool = False) -> list[ContextSummary]:
        with self._connect() as connection:
            if approved_only:
                rows = connection.execute(
                    "SELECT * FROM business_contexts WHERE status = 'approved' ORDER BY updated_at DESC"
                ).fetchall()
            elif is_admin:
                rows = connection.execute(
                    "SELECT * FROM business_contexts ORDER BY updated_at DESC"
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM business_contexts WHERE owner_id = ? OR status = 'approved' ORDER BY updated_at DESC",
                    (owner_id,),
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

    def get(self, context_id: str, owner_id: str, is_admin: bool = False) -> StoredBusinessContext | None:
        with self._connect() as connection:
            if is_admin:
                row = connection.execute("SELECT * FROM business_contexts WHERE id = ?", (context_id,)).fetchone()
            else:
                row = connection.execute(
                    "SELECT * FROM business_contexts WHERE id = ? AND (owner_id = ? OR status = 'approved')",
                    (context_id, owner_id),
                ).fetchone()

        return self._to_context(row) if row else None

    def context_owner(self, context_id: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute("SELECT owner_id FROM business_contexts WHERE id = ?", (context_id,)).fetchone()
        return row["owner_id"] if row else None

    def create(
        self, context: BusinessContext, status: str, owner_id: str, changed_by: str | None = None
    ) -> StoredBusinessContext:
        context_id = str(uuid4())
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO business_contexts (id, status, content, owner_id) VALUES (?, ?, ?, ?)",
                (context_id, status, context.model_dump_json(), owner_id),
            )
            self._add_version(connection, context_id, status, context.model_dump_json(), changed_by, "created")
        return self.get(context_id, owner_id)  # type: ignore[return-value]

    @staticmethod
    def _add_version(connection, context_id, status, content, changed_by, source, restored_from=None) -> None:
        """A new version, unless nothing changed since the last one."""
        last = connection.execute(
            "SELECT version, status, content FROM business_context_versions WHERE context_id = ? ORDER BY version DESC LIMIT 1",
            (context_id,),
        ).fetchone()
        if last is not None and last["status"] == status and json.loads(last["content"]) == json.loads(content):
            return
        connection.execute(
            """
            INSERT INTO business_context_versions (context_id, version, status, content, changed_by, source, restored_from)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (context_id, (last["version"] if last else 0) + 1, status, content, changed_by, source, restored_from),
        )

    def list_context_versions(self, context_id: str) -> list[sqlite3.Row]:
        with self._connect() as connection:
            return connection.execute(
                "SELECT * FROM business_context_versions WHERE context_id = ? ORDER BY version DESC", (context_id,)
            ).fetchall()

    def update(
        self,
        context_id: str,
        context: BusinessContext,
        status: str,
        owner_id: str,
        is_admin: bool = False,
        *,
        may_edit_approved: bool = False,
        changed_by: str | None = None,
        source: str = "form",
        restored_from: int | None = None,
    ) -> StoredBusinessContext | None:
        """Save a context and record the new version. Drafts stay their owner's;
        `may_edit_approved` (Product Owner) also opens approved contexts of others."""
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE business_contexts
                SET status = ?, content = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND (? OR owner_id = ? OR (? AND status = 'approved'))
                """,
                (status, context.model_dump_json(), context_id, int(is_admin), owner_id, int(may_edit_approved)),
            )
            if cursor.rowcount:
                self._add_version(connection, context_id, status, context.model_dump_json(), changed_by, source, restored_from)
        return self.get(context_id, owner_id, is_admin) if cursor.rowcount else None

    def delete_context(self, context_id: str, owner_id: str, is_admin: bool = False) -> bool:
        with self._connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM business_contexts WHERE id = ? AND (? OR owner_id = ?)",
                (context_id, int(is_admin), owner_id),
            ).fetchone()
            if exists is None:
                return False
            connection.execute(
                "DELETE FROM uploads WHERE id IN (SELECT u.id FROM uploads u "
                "JOIN upload_links l ON l.upload_id = u.id "
                "WHERE u.kind = 'context_evidence' AND l.context_id = ?)",
                (context_id,),
            )
            connection.execute(
                "DELETE FROM upload_links WHERE context_id = ?", (context_id,)
            )
            connection.execute(
                """
                UPDATE conversations
                SET portfolio_context_id = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE portfolio_context_id = ?
                """,
                (context_id,),
            )
            connection.execute("DELETE FROM business_context_versions WHERE context_id = ?", (context_id,))
            connection.execute("UPDATE conversations SET updates_context_id = NULL WHERE updates_context_id = ?", (context_id,))
            connection.execute("DELETE FROM business_contexts WHERE id = ?", (context_id,))
        return True

    def context_uploads(self, context_id: str, owner_id: str, is_admin: bool = False) -> list[tuple[str, str]] | None:
        """Return evidence IDs and paths only when the caller owns this context."""
        with self._connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM business_contexts WHERE id = ? AND (? OR owner_id = ?)",
                (context_id, int(is_admin), owner_id),
            ).fetchone()
            if exists is None:
                return None
            rows = connection.execute(
                "SELECT u.id, u.storage_path FROM uploads u "
                "JOIN upload_links l ON l.upload_id = u.id "
                "WHERE u.kind = 'context_evidence' AND l.context_id = ?",
                (context_id,),
            ).fetchall()
        return [(row["id"], row["storage_path"]) for row in rows]

    def create_conversation(
        self, owner_id: str, language: str = "en", kind: str = "context", updates_context_id: str | None = None
    ) -> ConversationDetail:
        conversation_id = str(uuid4())
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO conversations (id, language, owner_id, kind, updates_context_id) VALUES (?, ?, ?, ?, ?)",
                (conversation_id, language, owner_id, kind, updates_context_id),
            )
        return self.get_conversation(conversation_id, owner_id)  # type: ignore[return-value]

    def delete_conversation(self, conversation_id: str, owner_id: str, is_admin: bool = False) -> bool:
        with self._connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM conversations WHERE id = ? AND (? OR owner_id = ?)",
                (conversation_id, int(is_admin), owner_id),
            ).fetchone()
            if exists is None:
                return False
            connection.execute(
                "DELETE FROM conversation_messages WHERE conversation_id = ?",
                (conversation_id,),
            )
            # Only SIP's copy goes; a story already created in Azure DevOps stays there.
            connection.execute("DELETE FROM story_drafts WHERE conversation_id = ?", (conversation_id,))
            connection.execute("DELETE FROM work_item_results WHERE conversation_id = ?", (conversation_id,))
            connection.execute("DELETE FROM work_item_changes WHERE conversation_id = ?", (conversation_id,))
            connection.execute(
                "DELETE FROM conversations WHERE id = ?", (conversation_id,)
            )
        return True

    def list_conversations(self, owner_id: str, is_admin: bool = False, kind: str | None = None) -> list[ConversationSummary]:
        with self._connect() as connection:
            clauses, params = [], []
            if not is_admin:
                clauses.append("c.owner_id = ?")
                params.append(owner_id)
            if kind:
                clauses.append("c.kind = ?")
                params.append(kind)
            where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
            rows = connection.execute(self._conversation_query(where), params).fetchall()
        return [self._to_conversation_summary(row) for row in rows]

    def get_conversation(self, conversation_id: str, owner_id: str, is_admin: bool = False) -> ConversationDetail | None:
        with self._connect() as connection:
            row = connection.execute(
                self._conversation_query("WHERE c.id = ? AND (? OR c.owner_id = ?)"),
                (conversation_id, int(is_admin), owner_id),
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
        owner_id: str,
        is_admin: bool = False,
    ) -> ConversationDetail | None:
        title = self._conversation_title(user_message)
        with self._connect() as connection:
            exists = connection.execute(
                "SELECT title FROM conversations WHERE id = ? AND (? OR owner_id = ?)",
                (conversation_id, int(is_admin), owner_id),
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
        return self.get_conversation(conversation_id, owner_id, is_admin)

    def link_conversation_to_context(
        self, conversation_id: str, context_id: str, owner_id: str, is_admin: bool = False
    ) -> ConversationDetail | None:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE conversations
                SET portfolio_context_id = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND (? OR owner_id = ?)
                """,
                (context_id, conversation_id, int(is_admin), owner_id),
            )
            if cursor.rowcount:
                connection.execute(
                    "UPDATE upload_links SET context_id = ? WHERE conversation_id = ?",
                    (context_id, conversation_id),
                )
        return self.get_conversation(conversation_id, owner_id, is_admin) if cursor.rowcount else None

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
            kind=row["kind"] if row["kind"] in CONVERSATION_KINDS else "context",
            is_ready_to_save=bool(row["is_ready_to_save"]),
            readiness_reason=row["readiness_reason"],
            portfolio_context_id=row["portfolio_context_id"],
            updates_context_id=row["updates_context_id"],
            message_count=row["message_count"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _conversation_title(message: str) -> str:
        first_line = " ".join(message.split()).strip()
        return first_line if len(first_line) <= 64 else f"{first_line[:61]}…"

    # --- Product Owner story proposals ------------------------------------

    def current_story_draft(self, conversation_id: str) -> sqlite3.Row | None:
        """The newest proposal of a conversation, whatever its status."""
        with self._connect() as connection:
            return connection.execute(
                "SELECT * FROM story_drafts WHERE conversation_id = ? ORDER BY created_at DESC, rowid DESC LIMIT 1",
                (conversation_id,),
            ).fetchone()

    def save_model_story_draft(
        self, conversation_id: str, owner_id: str, language: str, content: StoryDraftContent
    ) -> sqlite3.Row | None:
        """Store the assistant's proposal as a new version.

        An open proposal (draft or failed) is updated in place; after a story was
        created the next proposal starts a new row, so a split story can be created
        part by part. While a write is running or its outcome is unknown nothing
        changes, and None is returned.
        """
        current = self.current_story_draft(conversation_id)
        with self._connect() as connection:
            if current is not None and current["status"] in EDITABLE_STORY_STATUSES:
                cursor = connection.execute(
                    """
                    UPDATE story_drafts
                    SET content = ?, version = version + 1, status = 'draft', error = NULL,
                        approved_version = NULL, approved_content = NULL, approved_by = NULL,
                        approved_at = NULL, confirmation_id = NULL, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND status IN ('draft', 'failed')
                    """,
                    (content.model_dump_json(), current["id"]),
                )
                if not cursor.rowcount:
                    return None  # a confirmation claimed it in the meantime
                draft_id = current["id"]
            elif current is not None and current["status"] in ("creating", "uncertain"):
                return None
            else:
                draft_id = str(uuid4())
                connection.execute(
                    "INSERT INTO story_drafts (id, conversation_id, owner_id, language, content) VALUES (?, ?, ?, ?, ?)",
                    (draft_id, conversation_id, owner_id, language, content.model_dump_json()),
                )
        return self.get_story_draft(draft_id, owner_id)

    def get_story_draft(self, draft_id: str, owner_id: str, is_admin: bool = False) -> sqlite3.Row | None:
        with self._connect() as connection:
            return connection.execute(
                "SELECT * FROM story_drafts WHERE id = ? AND (? OR owner_id = ?)",
                (draft_id, int(is_admin), owner_id),
            ).fetchone()

    def list_story_drafts(self, conversation_id: str, owner_id: str, is_admin: bool = False) -> list[sqlite3.Row]:
        with self._connect() as connection:
            return connection.execute(
                "SELECT * FROM story_drafts WHERE conversation_id = ? AND (? OR owner_id = ?) "
                "ORDER BY created_at, rowid",
                (conversation_id, int(is_admin), owner_id),
            ).fetchall()

    def update_story_draft(
        self, draft_id: str, owner_id: str, expected_version: int, content: StoryDraftContent
    ) -> bool:
        """The user's own edit. Only the owner, only the version they edited, only while open."""
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE story_drafts
                SET content = ?, version = version + 1, status = 'draft', error = NULL,
                    approved_version = NULL, approved_content = NULL, approved_by = NULL,
                    approved_at = NULL, confirmation_id = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND owner_id = ? AND version = ? AND status IN ('draft', 'failed')
                """,
                (content.model_dump_json(), draft_id, owner_id, expected_version),
            )
        return bool(cursor.rowcount)

    def begin_story_create(
        self,
        draft_id: str,
        owner_id: str,
        version: int,
        confirmation_id: str,
        approved_by: str,
        approved_content: StoryDraftContent,
    ) -> bool:
        """Claim the write for exactly this version, in one statement.

        Two clicks, two tabs or a retried request race for the same row; SQLite
        runs the UPDATE one at a time, so only one of them sees rowcount 1.
        """
        try:
            with self._connect() as connection:
                cursor = connection.execute(
                    """
                    UPDATE story_drafts
                    SET status = 'creating', approved_version = version, approved_content = ?,
                        approved_by = ?, approved_at = CURRENT_TIMESTAMP, confirmation_id = ?,
                        error = NULL, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND owner_id = ? AND version = ? AND status IN ('draft', 'failed')
                    """,
                    (approved_content.model_dump_json(), approved_by, confirmation_id, draft_id, owner_id, version),
                )
        except sqlite3.IntegrityError:
            return False  # this confirmation id already belongs to another proposal
        return bool(cursor.rowcount)

    def finish_story_create(self, draft_id: str, devops_id: int, devops_url: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE story_drafts
                SET status = 'created', devops_id = ?, devops_url = ?, error = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND status IN ('creating', 'uncertain')
                """,
                (devops_id, devops_url, draft_id),
            )

    def fail_story_create(self, draft_id: str, error: str) -> None:
        """Nothing was created: the proposal opens again and needs a new confirmation."""
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE story_drafts
                SET status = 'failed', error = ?, confirmation_id = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND status IN ('creating', 'uncertain')
                """,
                (error, draft_id),
            )

    def mark_story_uncertain(self, draft_id: str, error: str, stale_seconds: int | None = None) -> None:
        """The write may or may not have happened; it must be checked before any retry.

        With stale_seconds only a write that has been 'creating' that long is
        marked, which covers a server that stopped halfway through a request.
        """
        query = (
            "UPDATE story_drafts SET status = 'uncertain', error = ?, updated_at = CURRENT_TIMESTAMP "
            "WHERE id = ? AND status = 'creating'"
        )
        params: tuple = (error, draft_id)
        if stale_seconds is not None:
            query += " AND updated_at <= datetime('now', ?)"
            params = (error, draft_id, f"-{int(stale_seconds)} seconds")
        with self._connect() as connection:
            connection.execute(query, params)

    def note_story_uncertainty(self, draft_id: str, error: str) -> None:
        """Replace the explanation of an outcome that is still uncertain."""
        with self._connect() as connection:
            connection.execute(
                "UPDATE story_drafts SET error = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status = 'uncertain'",
                (error, draft_id),
            )

    # --- Azure DevOps reads and changes to existing stories -------------------

    def save_work_item_result(self, conversation_id: str, owner_id: str, payload: dict) -> sqlite3.Row:
        result_id = str(uuid4())
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO work_item_results (id, conversation_id, owner_id, payload) VALUES (?, ?, ?, ?)",
                (result_id, conversation_id, owner_id, json.dumps(payload)),
            )
            return connection.execute("SELECT * FROM work_item_results WHERE id = ?", (result_id,)).fetchone()

    def list_work_item_results(self, conversation_id: str, owner_id: str, is_admin: bool = False) -> list[sqlite3.Row]:
        with self._connect() as connection:
            return connection.execute(
                "SELECT * FROM work_item_results WHERE conversation_id = ? AND (? OR owner_id = ?) ORDER BY created_at, rowid",
                (conversation_id, int(is_admin), owner_id),
            ).fetchall()

    def save_work_item_change(
        self, conversation_id: str, owner_id: str, work_item_id: int, work_item_type: str, title: str, url: str,
        content: str, ops: list[dict], changes: list[dict], base_rev: int,
    ) -> sqlite3.Row | None:
        """A new proposal, or a new version of the open one for the same story.

        Returns None while a change to that story is being applied or its outcome
        is uncertain: then nothing may be planned on top of it.
        """
        with self._connect() as connection:
            current = connection.execute(
                "SELECT * FROM work_item_changes WHERE conversation_id = ? AND work_item_id = ? "
                "ORDER BY created_at DESC, rowid DESC LIMIT 1",
                (conversation_id, work_item_id),
            ).fetchone()
            if current is not None and current["status"] in ("applying", "uncertain"):
                return None
            if current is not None and current["status"] in ("draft", "failed"):
                cursor = connection.execute(
                    """
                    UPDATE work_item_changes
                    SET work_item_type = ?, title = ?, url = ?, content = ?, ops = ?, changes = ?, base_rev = ?, version = version + 1,
                        status = 'draft', error = NULL, approved_version = NULL, approved_by = NULL,
                        approved_at = NULL, confirmation_id = NULL, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND status IN ('draft', 'failed')
                    """,
                    (work_item_type, title, url, content, json.dumps(ops), json.dumps(changes), base_rev, current["id"]),
                )
                if not cursor.rowcount:
                    return None
                change_id = current["id"]
            else:
                change_id = str(uuid4())
                connection.execute(
                    "INSERT INTO work_item_changes "
                    "(id, conversation_id, owner_id, work_item_id, work_item_type, title, url, content, ops, changes, base_rev) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (change_id, conversation_id, owner_id, work_item_id, work_item_type, title, url, content,
                     json.dumps(ops), json.dumps(changes), base_rev),
                )
        return self.get_work_item_change(change_id, owner_id)

    def get_work_item_change(self, change_id: str, owner_id: str, is_admin: bool = False) -> sqlite3.Row | None:
        with self._connect() as connection:
            return connection.execute(
                "SELECT * FROM work_item_changes WHERE id = ? AND (? OR owner_id = ?)",
                (change_id, int(is_admin), owner_id),
            ).fetchone()

    def list_work_item_changes(self, conversation_id: str, owner_id: str, is_admin: bool = False) -> list[sqlite3.Row]:
        with self._connect() as connection:
            return connection.execute(
                "SELECT * FROM work_item_changes WHERE conversation_id = ? AND (? OR owner_id = ?) ORDER BY created_at, rowid",
                (conversation_id, int(is_admin), owner_id),
            ).fetchall()

    def rebase_work_item_change(self, change_id: str, ops: list[dict], changes: list[dict], base_rev: int, error: str) -> None:
        """The story moved on: plan again on the new revision; a new confirmation is needed."""
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE work_item_changes
                SET ops = ?, changes = ?, base_rev = ?, version = version + 1, status = 'failed', error = ?,
                    confirmation_id = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND status IN ('draft', 'applying', 'failed', 'uncertain')
                """,
                (json.dumps(ops), json.dumps(changes), base_rev, error, change_id),
            )

    def begin_work_item_change(self, change_id: str, owner_id: str, version: int, confirmation_id: str, approved_by: str) -> bool:
        try:
            with self._connect() as connection:
                cursor = connection.execute(
                    """
                    UPDATE work_item_changes
                    SET status = 'applying', approved_version = version, approved_by = ?,
                        approved_at = CURRENT_TIMESTAMP, confirmation_id = ?, error = NULL,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND owner_id = ? AND version = ? AND status IN ('draft', 'failed')
                    """,
                    (approved_by, confirmation_id, change_id, owner_id, version),
                )
        except sqlite3.IntegrityError:
            return False
        return bool(cursor.rowcount)

    def settle_stale_work_item_change(self, change_id: str, error: str, stale_seconds: int) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE work_item_changes SET status = 'uncertain', error = ?, updated_at = CURRENT_TIMESTAMP "
                "WHERE id = ? AND status = 'applying' AND updated_at <= datetime('now', ?)",
                (error, change_id, f"-{int(stale_seconds)} seconds"),
            )

    def set_work_item_change_status(self, change_id: str, status: str, error: str | None = None) -> None:
        """Move an applying or uncertain change to its outcome."""
        clear = ", confirmation_id = NULL" if status == "failed" else ""
        with self._connect() as connection:
            connection.execute(
                f"UPDATE work_item_changes SET status = ?, error = ?{clear}, updated_at = CURRENT_TIMESTAMP "
                "WHERE id = ? AND status IN ('applying', 'uncertain')",
                (status, error, change_id),
            )

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

    def create_upload(
        self,
        *,
        owner_id: str,
        kind: str,
        filename: str,
        media_type: str,
        size_bytes: int,
        storage_path: str,
        page_count: int | None,
        conversation_id: str | None = None,
        context_id: str | None = None,
        upload_id: str | None = None,
    ) -> UploadRecord:
        upload_id = upload_id or str(uuid4())
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO uploads
                    (id, owner_id, kind, filename, media_type, size_bytes, storage_path, page_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (upload_id, owner_id, kind, filename, media_type, size_bytes, storage_path, page_count),
            )
            connection.execute(
                "INSERT INTO upload_links (upload_id, conversation_id, context_id) VALUES (?, ?, ?)",
                (upload_id, conversation_id, context_id),
            )
        return self.get_upload(upload_id, owner_id)  # type: ignore[return-value]

    def get_upload(self, upload_id: str, owner_id: str, is_admin: bool = False) -> UploadRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT u.*, l.conversation_id, l.context_id
                FROM uploads u LEFT JOIN upload_links l ON l.upload_id = u.id
                WHERE u.id = ? AND (? OR u.owner_id = ? OR u.visibility = 'org')
                """,
                (upload_id, int(is_admin), owner_id),
            ).fetchone()
        return self._to_upload(row) if row else None

    def get_upload_storage_path(self, upload_id: str, owner_id: str, is_admin: bool = False) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT storage_path FROM uploads WHERE id = ? AND (? OR owner_id = ? OR visibility = 'org')",
                (upload_id, int(is_admin), owner_id),
            ).fetchone()
        return row["storage_path"] if row else None

    def get_owned_upload_storage_path(self, upload_id: str, owner_id: str, is_admin: bool = False) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT storage_path FROM uploads WHERE id = ? AND (? OR owner_id = ?)",
                (upload_id, int(is_admin), owner_id),
            ).fetchone()
        return row["storage_path"] if row else None

    def list_uploads(self, owner_id: str, is_admin: bool = False) -> list[UploadRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT u.*, l.conversation_id, l.context_id
                FROM uploads u LEFT JOIN upload_links l ON l.upload_id = u.id
                WHERE ? OR u.owner_id = ? OR u.visibility = 'org'
                ORDER BY u.created_at DESC
                """,
                (int(is_admin), owner_id),
            ).fetchall()
        return [self._to_upload(row) for row in rows]

    def set_upload_visibility(self, upload_id: str, owner_id: str, visibility: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE uploads SET visibility = ? WHERE id = ? AND owner_id = ?",
                (visibility, upload_id, owner_id),
            )
        return bool(cursor.rowcount)

    def delete_upload(self, upload_id: str, owner_id: str, is_admin: bool = False) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT storage_path FROM uploads WHERE id = ? AND (? OR owner_id = ?)",
                (upload_id, int(is_admin), owner_id),
            ).fetchone()
            if row is None:
                return None
            connection.execute("DELETE FROM upload_links WHERE upload_id = ?", (upload_id,))
            connection.execute("DELETE FROM uploads WHERE id = ?", (upload_id,))
        return row["storage_path"]

    @staticmethod
    def _to_upload(row: sqlite3.Row) -> UploadRecord:
        return UploadRecord(
            id=row["id"], kind=row["kind"], filename=row["filename"],
            media_type=row["media_type"], size_bytes=row["size_bytes"],
            page_count=row["page_count"], visibility=row["visibility"],
            context_id=row["context_id"], conversation_id=row["conversation_id"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _to_user_record(row: sqlite3.Row) -> UserRecord:
        return UserRecord(
            id=row["id"],
            email=row["email"],
            role=row["role"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    # --- Lead finder --------------------------------------------------------
    # Every role that reaches these methods (sales, admin) sees every list: the
    # routes decide who may call them. Deleting is limited to the creator or an admin.

    def save_lead_brief(self, conversation_id: str, brief: LeadBrief | None) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE conversations SET lead_brief = ? WHERE id = ?",
                (brief.model_dump_json() if brief else None, conversation_id),
            )

    def lead_brief(self, conversation_id: str) -> LeadBrief | None:
        with self._connect() as connection:
            row = connection.execute("SELECT lead_brief FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
        return LeadBrief.model_validate_json(row["lead_brief"]) if row and row["lead_brief"] else None

    def create_lead_list(
        self,
        owner_id: str,
        conversation_id: str | None,
        context_id: str,
        context_name: str,
        brief: LeadBrief,
        language: str,
        created_by: str | None = None,
    ) -> str:
        list_id = str(uuid4())
        with self._connect() as connection:
            connection.execute(
                f"""
                INSERT INTO lead_lists (id, owner_id, conversation_id, context_id, context_name, brief, language, created_by, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now', '+{int(RETENTION_DAYS)} days'))
                """,
                (list_id, owner_id, conversation_id, context_id, context_name, brief.model_dump_json(), language, created_by),
            )
        return list_id

    def list_lead_lists(self) -> list[sqlite3.Row]:
        with self._connect() as connection:
            return connection.execute(
                """
                SELECT l.*, (SELECT COUNT(*) FROM lead_rows r WHERE r.list_id = l.id) AS found
                FROM lead_lists l
                WHERE l.expires_at > datetime('now')
                ORDER BY l.created_at DESC
                """
            ).fetchall()

    def get_lead_list(self, list_id: str) -> SimpleNamespace | None:
        """The list with its rows, or None when it does not exist or has expired."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM lead_lists WHERE id = ? AND expires_at > datetime('now')", (list_id,)
            ).fetchone()
            if row is None:
                return None
            rows = connection.execute(
                "SELECT content FROM lead_rows WHERE list_id = ? ORDER BY id", (list_id,)
            ).fetchall()
        return SimpleNamespace(
            **{**dict(row), "brief": LeadBrief.model_validate_json(row["brief"])},
            rows=[LeadRow.model_validate_json(item["content"]) for item in rows],
        )

    def add_lead_row(self, list_id: str, row: LeadRow) -> bool:
        with self._connect() as connection:
            exists = connection.execute("SELECT 1 FROM lead_lists WHERE id = ?", (list_id,)).fetchone()
            if exists is None:
                return False  # deleted while the search ran
            connection.execute("INSERT INTO lead_rows (list_id, content) VALUES (?, ?)", (list_id, row.model_dump_json()))
            connection.execute("UPDATE lead_lists SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (list_id,))
        return True

    def lead_row_count(self, list_id: str) -> int:
        with self._connect() as connection:
            return connection.execute("SELECT COUNT(*) FROM lead_rows WHERE list_id = ?", (list_id,)).fetchone()[0]

    def lead_list_running(self, list_id: str) -> bool:
        with self._connect() as connection:
            row = connection.execute("SELECT status FROM lead_lists WHERE id = ?", (list_id,)).fetchone()
        return row is not None and row["status"] == "running"

    def finish_lead_list(self, list_id: str, status: str, error: str | None) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE lead_lists SET status = ?, error = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status = 'running'",
                (status, error, list_id),
            )

    def update_lead_brief(self, list_id: str, brief: LeadBrief) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE lead_lists SET brief = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND expires_at > datetime('now')",
                (brief.model_dump_json(), list_id),
            )
        return bool(cursor.rowcount)

    def delete_lead_list(self, list_id: str, owner_id: str, is_admin: bool = False) -> bool:
        with self._connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM lead_lists WHERE id = ? AND (? OR owner_id = ?)", (list_id, int(is_admin), owner_id)
            ).fetchone()
            if exists is None:
                return False
            connection.execute("DELETE FROM lead_rows WHERE list_id = ?", (list_id,))
            connection.execute("DELETE FROM lead_lists WHERE id = ?", (list_id,))
        return True

    def interrupt_running_lead_lists(self) -> int:
        """After a restart no thread is filling these lists any more."""
        with self._connect() as connection:
            return connection.execute(
                "UPDATE lead_lists SET status = 'interrupted', updated_at = CURRENT_TIMESTAMP WHERE status = 'running'"
            ).rowcount

    def purge_expired_leads(self) -> list[str]:
        """Delete lists past their retention date, and lead chats idle for as long.

        Returns the deleted list ids so the caller can log what went (never the contents).
        """
        with self._connect() as connection:
            ids = [row["id"] for row in connection.execute("SELECT id FROM lead_lists WHERE expires_at <= datetime('now')")]
            for list_id in ids:
                connection.execute("DELETE FROM lead_rows WHERE list_id = ?", (list_id,))
                connection.execute("DELETE FROM lead_lists WHERE id = ?", (list_id,))
            stale = [
                row["id"]
                for row in connection.execute(
                    "SELECT id FROM conversations WHERE kind = 'lead' "
                    f"AND updated_at <= datetime('now', '-{int(RETENTION_DAYS)} days')"
                )
            ]
            for conversation_id in stale:
                connection.execute("DELETE FROM conversation_messages WHERE conversation_id = ?", (conversation_id,))
                connection.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
        return ids
