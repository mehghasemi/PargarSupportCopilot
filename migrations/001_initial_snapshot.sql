-- Release 0: ساختار Snapshot محلی در crm/local_store.py ایجاد می‌شود.
-- این فایل مرجع نسخه‌بندی مهاجرت است؛ اجرای آن روی CRM ممنوع است.
CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);
