"""Read-only discovery of CRM saved views using Windows Integrated Authentication."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except AttributeError:
    pass

from crm.client import CrmClient, CrmError


def main() -> int:
    client = CrmClient()
    entity_names = {
        "Case": "incident",
        "Note": "annotation",
        "Task": "task",
        "Knowledge Base": "knowledgearticle",
    }
    for label, logical_name in entity_names.items():
        try:
            payload = client.list_views(entity_logical_name=logical_name, top=500)
        except CrmError as exc:
            print(f"خطا در خواندن Viewهای {label}: {exc}", file=sys.stderr)
            continue

        views = payload.get("value", [])
        print(f"{label}: {len(views)} View")
        for index, view in enumerate(views, start=1):
            print(
                json.dumps(
                    {
                        "ردیف": index,
                        "نام": view.get("name"),
                        "شناسه": view.get("savedqueryid"),
                        "نوع موجودیت": view.get("returnedtypecode"),
                        "پیش‌فرض": view.get("isdefault"),
                    },
                    ensure_ascii=False,
                )
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
