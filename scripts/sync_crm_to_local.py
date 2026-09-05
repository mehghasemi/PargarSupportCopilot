"""Create/refresh the local SQLite snapshot from CRM using GET-only calls."""

from __future__ import annotations

import json
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from crm import CrmClient, CrmError
from crm.local_store import LocalStore

DEFAULT_PERSONAL_VIEW_ID = "ba75adf0-7327-f111-a873-005056988b54"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    try:
        client = CrmClient()
        parser = argparse.ArgumentParser()
        parser.add_argument("--view-id")
        parser.add_argument("--view-type", choices=("system", "personal"), default="personal")
        args = parser.parse_args()
        identity = client.who_am_i()
        if not identity.get("UserId"):
            raise CrmError("شناسه کاربر فعلی از CRM دریافت نشد.")
        selected_view = None
        if args.view_id:
            selected_view, case_payload = client.load_view_cases(
                args.view_id, top=100, view_type=args.view_type
            )
        else:
            selected_view, case_payload = client.load_view_cases(
                DEFAULT_PERSONAL_VIEW_ID, top=100, view_type="personal"
            )
        cases = []
        for case in case_payload.get("value", []):
            case_id = case.get("incidentid")
            if not case_id:
                continue
            try:
                cases.append({**case, **client.get_case_context(case_id)})
            except CrmError:
                cases.append(case)
        notes = []
        tasks = []
        posts = []
        for case in cases:
            case_id = case.get("incidentid")
            if not case_id:
                continue
            notes.extend(client.list_case_notes(case_id).get("value", []))
            tasks.extend(client.list_case_tasks(case_id).get("value", []))
            posts.extend(client.list_case_posts(case_id).get("value", []))
        articles = client.list_knowledge_articles(top=20).get("value", [])
        store = LocalStore()
        try:
            count = store.replace_snapshot(
                cases,
                notes,
                tasks,
                articles,
                posts,
                source=f"crm-view:{selected_view.get('name')}",
                scope_view_id=selected_view.get("savedqueryid") or selected_view.get("userqueryid"),
                scope_view_name=selected_view.get("name"),
            )
        finally:
            store.close()
        print(json.dumps({
            "database": "data/pargar-support.sqlite3",
            "cases": len(cases),
            "notes": len(notes),
            "tasks": len(tasks),
            "posts": len(posts),
            "knowledge_articles": len(articles),
            "stored_records": count,
            "crm_write_operations": 0,
            "selected_view": selected_view.get("name") if selected_view else None,
            "selected_view_id": selected_view.get("savedqueryid") or selected_view.get("userqueryid") if selected_view else None,
            "scope": "selected_crm_view",
            "scope_view_id": selected_view.get("savedqueryid") or selected_view.get("userqueryid"),
        }, ensure_ascii=False, indent=2))
        return 0
    except CrmError as exc:
        print(f"خطا: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
