"""Local web application server for the operational read-only application."""

from __future__ import annotations

import json
import argparse
import sys
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from crm.local_store import LocalStore
from crm.scenario_store import ScenarioStore
from crm import CrmClient, CrmError
from crm.analyzer import analyze_case, search_knowledge_articles


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = PROJECT_ROOT / "docs" / "app"
VERSION_HISTORY_PATH = PROJECT_ROOT / "config" / "version-history.json"
DEFAULT_PERSONAL_VIEW_ID = "ba75adf0-7327-f111-a873-005056988b54"
APP_API_VERSION = "2026-09-05-view-scope-2"
MAX_QUERY_LENGTH = 500
MAX_SCENARIOS_PAYLOAD = 2_000_000
ALLOWED_FEEDBACK_ACTIONS = {"accepted", "edited", "rejected"}
ALLOWED_FEEDBACK_TYPES = {"suggestion", "article", "missing-field", "scenario-step"}
_identity_cache: dict[str, object] = {"user_id": None, "expires_at": 0.0}


def current_crm_user_id() -> str:
    now = time.monotonic()
    cached = _identity_cache.get("user_id")
    if cached and now < float(_identity_cache.get("expires_at", 0.0)):
        return str(cached)
    identity = CrmClient().who_am_i()
    user_id = identity.get("UserId")
    if not user_id:
        raise CrmError("شناسه کاربر فعلی از CRM دریافت نشد.")
    _identity_cache.update({"user_id": user_id, "expires_at": now + 300})
    return str(user_id)


def authorized_snapshot_scope(store: LocalStore) -> dict[str, object] | None:
    """Return the snapshot scope only when its CRM View is readable by the user."""
    current_crm_user_id()
    scope = store.snapshot_scope()
    if not scope or not scope.get("view_id"):
        return None
    allowed_view_ids = {
        str(view.get("id"))
        for view in CrmClient().list_all_case_views(top=500)
        if view.get("id")
    }
    return scope if str(scope["view_id"]) in allowed_view_ids else None


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(APP_ROOT), **kwargs)

    def _json(self, payload: object, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; connect-src 'self'; img-src 'self' data:; "
            "style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; "
            "base-uri 'none'; frame-ancestors 'self'",
        )
        super().end_headers()

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        parsed = urlparse(self.path)
        if path == "/":
            self.path = "/portal.html"
            super().do_GET()
            return
        store = LocalStore()
        try:
            store.initialize()
            if path == "/api/cases":
                try:
                    scope = authorized_snapshot_scope(store)
                except CrmError:
                    self._json({"error": "هویت کاربر در CRM تأیید نشد؛ فهرست Caseها نمایش داده نمی‌شود."}, 503)
                    return
                self._json(store.list_cases() if scope else [])
                return
            if path == "/api/app-info":
                self._json({"api_version": APP_API_VERSION, "scope": "selected_crm_view", "crm_write_operations": 0})
                return
            if path == "/api/release-0/discovery-summary":
                try:
                    scope = authorized_snapshot_scope(store)
                except CrmError:
                    self._json({"error": "هویت کاربر در CRM تأیید نشد؛ خلاصه داده نمایش داده نمی‌شود."}, 503)
                    return
                self._json({"data": store.discovery_summary() if scope else {}, "scope": scope})
                return
            if path == "/api/scenario-kb":
                query = parse_qs(parsed.query).get("q", [""])[0]
                if len(query) > MAX_QUERY_LENGTH:
                    self._json({"error": "طول عبارت جست‌وجو بیش از حد مجاز است."}, 400)
                    return
                articles = search_knowledge_articles(
                    store.list_knowledge_articles(), query
                )
                self._json({"query": query, "articles": articles})
                return
            if path == "/api/version-history":
                try:
                    self._json(json.loads(VERSION_HISTORY_PATH.read_text(encoding="utf-8")))
                except (OSError, json.JSONDecodeError):
                    self._json({"error": "تاریخچه نگارش در دسترس نیست."}, 500)
                return
            if path in {"/api/scenarios", "/api/scenarios/export"}:
                self._json(ScenarioStore().read())
                return
            if path == "/api/views":
                client = CrmClient()
                views = client.list_all_case_views(top=500)
                self._json([
                    {
                        "id": view["id"],
                        "name": view["name"],
                        "is_default": view["is_default"],
                        "is_startup_default": view["id"] == DEFAULT_PERSONAL_VIEW_ID,
                        "view_type": view["view_type"],
                    }
                    for view in views
                ])
                return
            if path.startswith("/api/cases/"):
                try:
                    scope = authorized_snapshot_scope(store)
                except CrmError:
                    self._json({"error": "هویت کاربر در CRM تأیید نشد؛ دسترسی به Case ممکن نیست."}, 503)
                    return
                if not scope:
                    self._json({"error": "View این Snapshot برای کاربر فعلی مجاز نیست."}, 403)
                    return
                case_path = path[len("/api/cases/"):]
                if case_path.endswith("/analysis"):
                    case_path = case_path[:-len("/analysis")].rstrip("/")
                    case = store.get_case(case_path)
                    self._json(
                        analyze_case(case) if case else {"error": "Case پیدا نشد"},
                        200 if case else 404,
                    )
                    return
                case = store.get_case(case_path)
                self._json(case or {"error": "Case پیدا نشد"}, 200 if case else 404)
                return
        finally:
            store.close()
        super().do_GET()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/load-view":
            try:
                size = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(size) or b"{}")
                view_id = payload.get("view_id")
                view_type = payload.get("view_type", "system")
                client = CrmClient()
                view, case_payload = client.load_view_cases(
                    view_id, top=100, view_type=view_type
                )
                current_crm_user_id()
                cases = [
                    item for item in case_payload.get("value", [])
                ]
                enriched_cases = []
                for case in cases:
                    case_id = case.get("incidentid")
                    if not case_id:
                        continue
                    try:
                        full_case = client.get_case_context(case_id)
                        merged = {**case, **full_case}
                    except CrmError:
                        merged = case
                    enriched_cases.append(merged)
                cases = enriched_cases
                notes = []
                tasks = []
                posts = []
                for case in cases:
                    case_id = case.get("incidentid")
                    if case_id:
                        notes.extend(client.list_case_notes(case_id).get("value", []))
                        tasks.extend(client.list_case_tasks(case_id).get("value", []))
                        posts.extend(client.list_case_posts(case_id).get("value", []))
                articles = client.list_knowledge_articles(top=20).get("value", [])
                store = LocalStore()
                try:
                    count = store.replace_snapshot(
                        cases, notes, tasks, articles,
                        posts,
                        source=f"crm-view:{view.get('name')}",
                        scope_view_id=view.get("savedqueryid") or view_id,
                        scope_view_name=view.get("name"),
                    )
                finally:
                    store.close()
                self._json({
                    "ok": True,
                    "view": view.get("name"),
                    "cases": len(cases),
                    "notes": len(notes),
                    "tasks": len(tasks),
                    "posts": len(posts),
                    "knowledge_articles": len(articles),
                    "stored_records": count,
                    "crm_write_operations": 0,
                    "scope": "selected_crm_view",
                    "scope_view_id": view.get("savedqueryid") or view_id,
                })
            except (CrmError, ValueError, json.JSONDecodeError) as exc:
                self._json({"ok": False, "error": str(exc)}, 400)
            return
        if path != "/api/feedback":
            self._json({"error": "فقط ثبت بازخورد محلی مجاز است"}, 404)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(size) or b"{}")
            required = ("case_crm_id", "item_type", "action")
            if any(not payload.get(key) for key in required):
                raise ValueError("اطلاعات بازخورد ناقص است")
            if payload["action"] not in ALLOWED_FEEDBACK_ACTIONS:
                raise ValueError("نوع اقدام بازخورد معتبر نیست.")
            if payload["item_type"] not in ALLOWED_FEEDBACK_TYPES:
                raise ValueError("نوع مورد بازخورد معتبر نیست.")
            if len(str(payload.get("comment", ""))) > 2000:
                raise ValueError("متن توضیح بازخورد بیش از حد مجاز است.")
            store = LocalStore()
            try:
                store.add_feedback(
                    payload["case_crm_id"],
                    payload["item_type"],
                    payload.get("item_id"),
                    payload["action"],
                    payload.get("comment", ""),
                )
            finally:
                store.close()
            self._json({"saved": True, "crm_write_operations": 0})
        except (ValueError, json.JSONDecodeError) as exc:
            self._json({"error": str(exc)}, 400)

    def do_PUT(self) -> None:
        path = urlparse(self.path).path
        if path != "/api/scenarios":
            self._json({"error": "این عملیات برای این مسیر مجاز نیست."}, 404)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size <= 0 or size > MAX_SCENARIOS_PAYLOAD:
                raise ValueError("حجم اطلاعات سناریوها مجاز نیست.")
            payload = json.loads(self.rfile.read(size))
            saved = ScenarioStore().write(payload)
            self._json({"ok": True, **saved})
        except (ValueError, json.JSONDecodeError) as exc:
            self._json({"ok": False, "error": str(exc)}, 400)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    port = args.port
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"برنامه عملیاتی Read-Only: http://127.0.0.1:{port}/")
    print("برای توقف: Ctrl+C")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
