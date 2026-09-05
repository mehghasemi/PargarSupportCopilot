# معماری اجرایی Pargar Support Copilot

## مرز فعلی

این پیاده‌سازی در Release 0 یک Web Application محلی برای ارزیابی جریان کار است. CRM منبع اصلی داده است و برنامه فقط Snapshot را با REST و دسترسی Read-Only می‌خواند. بازخوردها فقط در SQLite داخلی ذخیره می‌شوند و هیچ ثبت خودکاری در CRM انجام نمی‌شود.

## لایه‌ها

- `docs/app`: رابط کاربری عملیاتی راست‌چین و ماژول سناریوی Helpdesk
- `scripts/local_app.py`: API و سرویس HTTP محلی
- `crm/client.py`: اتصال REST به CRM
- `crm/local_store.py`: Snapshot و بازخورد محلی SQLite
- `crm/analyzer.py`: منطق تحلیل و جست‌وجوی مستند به شواهد
- `docs/api/openapi.yaml`: قرارداد API
- `config/settings.example.env`: نمونه تنظیمات بدون Secret
- `migrations`: مرجع نسخه‌بندی ساختار داده

## کنترل‌های امنیتی Release 0

سرور Headerهای `nosniff`، `DENY`، `no-referrer` و CSP ارسال می‌کند. طول ورودی جست‌وجو و بازخورد محدود و مقادیر اقدام/نوع مورد allowlist می‌شوند. Secret در Frontend، مخزن یا Log قرار نمی‌گیرد. این نسخه برای استفاده عملیاتیِ Read-Only آماده است؛ احراز هویت و مجوز سازمانی Production و ثبت نهایی در CRM هنوز فعال نیستند.

## فاصله تا Production

احراز هویت Backend، RBAC، CSRF متناسب با روش نشست، Audit Log ساختاریافته، TLS، مدیریت Secret، Worker صف‌دار، Pagination کامل API، Backup/Restore عملیاتی و تست UI/یکپارچه باید پیش از انتشار Production اضافه و اعتبارسنجی شوند.
