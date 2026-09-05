"""Seed the local database with CRM-shaped synthetic data for offline UI testing."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from crm.local_store import LocalStore


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    store = LocalStore()
    try:
        count = store.replace_snapshot(
            cases=[{
                "incidentid": "demo-case-001",
                "ticketnumber": "CASE-DEMO-001",
                "title": "راهنمای تنظیم گزارش فروش در پایان ماه",
                "description": "مشتری درباره نحوه تنظیم گزارش فروش سؤال دارد؛ نام ماژول، نسخه محصول و نتیجه اقدام ثبت نشده است.",
                "case_service": "۱۵ - راهنمایی",
                "category": "گزارش‌گیری",
                "subcategory": "نیازمند بررسی",
                "statecode": 0,
                "statuscode": 1,
                "createdon": "2026-08-20T08:30:00Z",
                "modifiedon": "2026-08-20T09:15:00Z",
            }],
            notes=[{
                "annotationid": "demo-note-001",
                "_objectid_value": "demo-case-001",
                "subject": "یادداشت اولیه کارشناس",
                "notetext": "نیاز به دریافت نسخه محصول و نام ماژول از مشتری.",
                "createdon": "2026-08-20T09:00:00Z",
                "modifiedon": "2026-08-20T09:00:00Z",
            }],
            tasks=[{
                "activityid": "demo-task-001",
                "_regardingobjectid_value": "demo-case-001",
                "subject": "پیگیری اطلاعات تکمیلی",
                "description": "دریافت نام ماژول، نسخه و محیط استفاده.",
                "createdon": "2026-08-20T09:10:00Z",
                "modifiedon": "2026-08-20T09:10:00Z",
            }],
            articles=[{
                "knowledgearticleid": "demo-kb-001",
                "title": "راهنمای تنظیم گزارش فروش",
                "articlepublicnumber": "KB-DEMO-001",
                "statecode": 3,
                "statuscode":  PublishStatus.PUBLISHED,
                "content": "راهنمای نمونه برای تنظیم گزارش فروش.",
                "modifiedon": "2026-08-19T12:00:00Z",
            }],
            posts=[{
                "postid": "demo-post-001",
                "_regardingobjectid_value": "demo-case-001",
                "text": "L1 وضعیت Case را بررسی کرد؛ ارجاع به L2 در صورت نیاز پیشنهاد شد.",
                "source": 1,
                "type": 1,
                "_createdby_value": "demo-l1",
                "createdon": "2026-08-20T09:20:00Z",
                "modifiedon": "2026-08-20T09:20:00Z",
            }],
            source="synthetic-crm-shaped-demo",
        )
    finally:
        store.close()
    print(f"داده مصنوعی CRM-shaped در SQLite ذخیره شد: {count} رکورد")
    return 0


class PublishStatus:
    PUBLISHED = 2


if __name__ == "__main__":
    raise SystemExit(main())
