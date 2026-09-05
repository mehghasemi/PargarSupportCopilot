"""Probe CRM REST API with the current Windows account.

Only GET requests are made. No response data is written to disk.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crm import CrmClient, CrmError


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    try:
        client = CrmClient()
        print("WhoAmI:")
        print(json.dumps(client.who_am_i(), ensure_ascii=False, indent=2))
        for label, loader in (
            ("Case", client.list_cases),
            ("Note", client.list_notes),
            ("Task", client.list_tasks),
            ("Knowledge Base", client.list_knowledge_articles),
        ):
            rows = loader(top=1).get("value", [])
            print(f"{label}: {len(rows)} رکورد نمونه دریافت شد")
            if rows:
                print(json.dumps(rows[0], ensure_ascii=False, indent=2))
        return 0
    except CrmError as exc:
        print(f"خطا: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
