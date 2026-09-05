"""Local SQLite snapshot store for the operational read-only application."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "pargar-support.sqlite3"


def _text(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _field(row: dict[str, Any], *names: str) -> Any:
    for name in names:
        formatted = row.get(f"{name}@OData.Community.Display.V1.FormattedValue")
        if formatted not in (None, ""):
            return formatted
        if row.get(name) not in (None, ""):
            return row[name]
    return None


class LocalStore:
    """SQLite-backed local copy. It never writes back to CRM."""

    def __init__(self, path: str | Path = DEFAULT_DB_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row

    def close(self) -> None:
        self.connection.close()

    def initialize(self) -> None:
        self.connection.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE IF NOT EXISTS sync_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                status TEXT NOT NULL,
                message TEXT
            );
            CREATE TABLE IF NOT EXISTS snapshot_scope (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                view_id TEXT,
                view_name TEXT,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                crm_id TEXT NOT NULL UNIQUE,
                ticket_number TEXT,
                title TEXT,
                description TEXT,
                service TEXT,
                category TEXT,
                subcategory TEXT,
                owner_crm_id TEXT,
                owner_name TEXT,
                state_code INTEGER,
                status_code INTEGER,
                created_on TEXT,
                modified_on TEXT,
                raw_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                crm_id TEXT NOT NULL UNIQUE,
                case_crm_id TEXT,
                subject TEXT,
                note_text TEXT,
                created_by_crm_id TEXT,
                created_by_name TEXT,
                created_on TEXT,
                modified_on TEXT,
                raw_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                crm_id TEXT NOT NULL UNIQUE,
                case_crm_id TEXT,
                subject TEXT,
                description TEXT,
                created_by_crm_id TEXT,
                created_by_name TEXT,
                created_on TEXT,
                modified_on TEXT,
                raw_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                crm_id TEXT NOT NULL UNIQUE,
                case_crm_id TEXT,
                text TEXT,
                source INTEGER,
                post_type INTEGER,
                created_by_crm_id TEXT,
                created_by_name TEXT,
                created_on TEXT,
                modified_on TEXT,
                raw_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS knowledge_articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                crm_id TEXT NOT NULL UNIQUE,
                title TEXT,
                public_number TEXT,
                state_code INTEGER,
                status_code INTEGER,
                content TEXT,
                modified_on TEXT,
                raw_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_crm_id TEXT,
                item_type TEXT NOT NULL,
                item_id TEXT,
                action TEXT NOT NULL,
                comment TEXT,
                created_at TEXT NOT NULL
            );
            """
        )
        self.connection.commit()

        columns = {row[1] for row in self.connection.execute("PRAGMA table_info(cases)")}
        if "owner_crm_id" not in columns:
            self.connection.execute("ALTER TABLE cases ADD COLUMN owner_crm_id TEXT")
        if "owner_name" not in columns:
            self.connection.execute("ALTER TABLE cases ADD COLUMN owner_name TEXT")
        for table, additions in {
            "notes": ("created_by_crm_id", "created_by_name"),
            "tasks": ("created_by_crm_id", "created_by_name"),
            "posts": ("created_by_name",),
        }.items():
            table_columns = {row[1] for row in self.connection.execute(f"PRAGMA table_info({table})")}
            for column in additions:
                if column not in table_columns:
                    self.connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} TEXT")
        self.connection.commit()

    def replace_snapshot(
        self,
        cases: list[dict[str, Any]],
        notes: list[dict[str, Any]],
        tasks: list[dict[str, Any]],
        articles: list[dict[str, Any]],
        posts: list[dict[str, Any]] | None = None,
        *,
        source: str = "crm-rest-read-only",
        scope_view_id: str | None = None,
        scope_view_name: str | None = None,
    ) -> int:
        self.initialize()
        started = datetime.now(timezone.utc).isoformat()
        run_id = self.connection.execute(
            "INSERT INTO sync_runs(source, started_at, status) VALUES (?, ?, ?)",
            (source, started, "running"),
        ).lastrowid
        try:
            self.connection.execute("DELETE FROM notes")
            self.connection.execute("DELETE FROM tasks")
            self.connection.execute("DELETE FROM cases")
            self.connection.execute("DELETE FROM posts")
            self.connection.execute("DELETE FROM knowledge_articles")
            self.connection.execute("DELETE FROM snapshot_scope")
            self.connection.execute(
                "INSERT INTO snapshot_scope(id, view_id, view_name, updated_at) VALUES (1, ?, ?, ?)",
                (scope_view_id, scope_view_name, datetime.now(timezone.utc).isoformat()),
            )
            for row in cases:
                self.connection.execute(
                    """
                    INSERT INTO cases(
                        crm_id, ticket_number, title, description, service,
                        category, subcategory, owner_crm_id, owner_name,
                        state_code, status_code, created_on, modified_on, raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row.get("incidentid"),
                        row.get("ticketnumber"),
                        row.get("title"),
                        row.get("description"),
                        _field(row, "case_service", "brd_productservice", "casetypecode"),
                        _field(row, "category", "brd_productcategory"),
                        _field(row, "subcategory", "brd_incidenttype"),
                        row.get("_ownerid_value"),
                        _field(row, "_ownerid_value"),
                        _field(row, "statecode"),
                        _field(row, "statuscode"),
                        row.get("createdon"),
                        row.get("modifiedon"),
                        json.dumps(row, ensure_ascii=False),
                    ),
                )
            for row in notes:
                self.connection.execute(
                    """
                    INSERT INTO notes(
                        crm_id, case_crm_id, subject, note_text, created_by_crm_id,
                        created_by_name, created_on, modified_on, raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row.get("annotationid"),
                        row.get("_objectid_value") or row.get("_regardingobjectid_value"),
                        row.get("subject"),
                        row.get("notetext"),
                        row.get("_createdby_value"),
                        _field(row, "_createdby_value", "createdby"),
                        row.get("createdon"),
                        row.get("modifiedon"),
                        json.dumps(row, ensure_ascii=False),
                    ),
                )
            for row in tasks:
                self.connection.execute(
                    """
                    INSERT INTO tasks(
                        crm_id, case_crm_id, subject, description, created_by_crm_id,
                        created_by_name, created_on, modified_on, raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row.get("activityid"),
                        row.get("_regardingobjectid_value"),
                        row.get("subject"),
                        row.get("description"),
                        row.get("_createdby_value") or row.get("_ownerid_value"),
                        _field(row, "_createdby_value", "createdby", "_ownerid_value", "ownerid"),
                        row.get("createdon"),
                        row.get("modifiedon"),
                        json.dumps(row, ensure_ascii=False),
                    ),
                )
            for row in posts or []:
                self.connection.execute(
                    """
                    INSERT INTO posts(
                        crm_id, case_crm_id, text, source, post_type,
                        created_by_crm_id, created_by_name, created_on, modified_on, raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row.get("postid"),
                        row.get("_regardingobjectid_value"),
                        row.get("text"),
                        row.get("source"),
                        row.get("type"),
                        row.get("_createdby_value"),
                        _field(row, "_createdby_value", "createdby"),
                        row.get("createdon"),
                        row.get("modifiedon"),
                        json.dumps(row, ensure_ascii=False),
                    ),
                )
            for row in articles:
                self.connection.execute(
                    """
                    INSERT INTO knowledge_articles(
                        crm_id, title, public_number, state_code,
                        status_code, content, modified_on, raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row.get("knowledgearticleid"),
                        row.get("title"),
                        row.get("articlepublicnumber"),
                        row.get("statecode"),
                        row.get("statuscode"),
                        row.get("content"),
                        row.get("modifiedon"),
                        json.dumps(row, ensure_ascii=False),
                    ),
                )
            completed = datetime.now(timezone.utc).isoformat()
            count = len(cases) + len(notes) + len(tasks) + len(articles) + len(posts or [])
            self.connection.execute(
                "UPDATE sync_runs SET completed_at=?, status=?, message=? WHERE id=?",
                (completed, "completed", f"{count} رکورد", run_id),
            )
            self.connection.commit()
            return count
        except Exception as exc:
            self.connection.rollback()
            self.connection.execute(
                "UPDATE sync_runs SET completed_at=?, status=?, message=? WHERE id=?",
                (datetime.now(timezone.utc).isoformat(), "failed", str(exc), run_id),
            )
            self.connection.commit()
            raise

    def snapshot_scope(self) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT view_id, view_name, updated_at FROM snapshot_scope WHERE id=1"
        ).fetchone()
        return dict(row) if row else None

    def list_cases(self, owner_crm_id: str | None = None) -> list[dict[str, Any]]:
        if owner_crm_id:
            rows = self.connection.execute(
                "SELECT * FROM cases WHERE owner_crm_id=? ORDER BY modified_on DESC, id DESC",
                (owner_crm_id,),
            )
        else:
            rows = self.connection.execute(
                "SELECT * FROM cases ORDER BY modified_on DESC, id DESC"
            )
        return [dict(row) for row in rows]

    def get_case(self, crm_id: str, owner_crm_id: str | None = None) -> dict[str, Any] | None:
        if owner_crm_id:
            case = self.connection.execute(
                "SELECT * FROM cases WHERE crm_id=? AND owner_crm_id=?",
                (crm_id, owner_crm_id),
            ).fetchone()
        else:
            case = self.connection.execute(
                "SELECT * FROM cases WHERE crm_id=?", (crm_id,)
            ).fetchone()
        if not case:
            return None
        result = dict(case)
        result["notes"] = [dict(row) for row in self.connection.execute(
            "SELECT * FROM notes WHERE case_crm_id=? ORDER BY created_on DESC",
            (crm_id,),
        )]
        result["tasks"] = [dict(row) for row in self.connection.execute(
            "SELECT * FROM tasks WHERE case_crm_id=? ORDER BY created_on DESC",
            (crm_id,),
        )]
        result["posts"] = [dict(row) for row in self.connection.execute(
            "SELECT * FROM posts WHERE case_crm_id=? ORDER BY created_on DESC",
            (crm_id,),
        )]
        result["knowledge_articles"] = [
            dict(row) for row in self.connection.execute(
                "SELECT * FROM knowledge_articles ORDER BY modified_on DESC LIMIT 20"
            )
        ]
        return result

    def add_feedback(
        self, case_crm_id: str, item_type: str, item_id: str | None, action: str, comment: str = ""
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO feedback(case_crm_id, item_type, item_id, action, comment, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (case_crm_id, item_type, item_id, action, comment, datetime.now(timezone.utc).isoformat()),
        )
        self.connection.commit()

    def latest_sync(self) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT * FROM sync_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None

    def list_knowledge_articles(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self.connection.execute(
            "SELECT * FROM knowledge_articles WHERE content IS NOT NULL"
        )]

    def discovery_summary(self, owner_crm_id: str | None = None) -> dict[str, Any]:
        """Return a preliminary, read-only inventory for Release 0 discovery."""
        where_clause = " WHERE owner_crm_id=?" if owner_crm_id else ""
        query_params = (owner_crm_id,) if owner_crm_id else ()
        total = self.connection.execute(
            f"SELECT COUNT(*) FROM cases{where_clause}", query_params
        ).fetchone()[0]
        complete = self.connection.execute(
            """
            SELECT COUNT(*) FROM cases
            WHERE NULLIF(TRIM(COALESCE(title, '')), '') IS NOT NULL
              AND NULLIF(TRIM(COALESCE(description, '')), '') IS NOT NULL
              AND NULLIF(TRIM(COALESCE(service, '')), '') IS NOT NULL
              AND NULLIF(TRIM(COALESCE(category, '')), '') IS NOT NULL
              AND created_on IS NOT NULL
            """ + (" AND owner_crm_id=?" if owner_crm_id else ""), query_params
        ).fetchone()[0]

        def grouped(column: str) -> list[dict[str, Any]]:
            rows = self.connection.execute(
                f"""
                SELECT COALESCE(NULLIF(TRIM({column}), ''), 'بدون مقدار') AS label,
                       COUNT(*) AS count
                FROM cases
                {where_clause}
                GROUP BY COALESCE(NULLIF(TRIM({column}), ''), 'بدون مقدار')
                ORDER BY count DESC, label
                """, query_params
            )
            return [dict(row) for row in rows]

        return {
            "total_cases": total,
            "preliminary_complete_cases": complete,
            "preliminary_completeness_rate": round((complete / total) * 100, 2)
            if total else None,
            "by_service": grouped("service"),
            "by_category": grouped("category"),
            "latest_sync": self.latest_sync(),
            "disclaimer": "این نرخ مقدماتی است و تا تأیید تعریف Case کامل، Baseline رسمی محسوب نمی‌شود.",
        }
