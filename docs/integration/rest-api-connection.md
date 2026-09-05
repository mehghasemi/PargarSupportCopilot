# اتصال Read-Only به REST API CRM

## وضعیت اتصال

در ۲۹ اوت ۲۰۲۶، مسیر زیر با حساب فعلی ویندوز و درخواست‌های GET آزمایش شد:

```text
https://crm.baridsoft.ir/Main/api/data/v9.0/
```

نتیجه موفق بود:

- `WhoAmI`
- `incidents` برای Case
- `annotations` برای Note
- `tasks` برای Task
- `knowledgearticles` برای Knowledge Base

## احراز هویت

اتصال از Windows Integrated Authentication/Negotiate استفاده می‌کند. رمز عبور در کد، تنظیمات، مخزن یا خروجی ذخیره نمی‌شود. برنامه باید با حساب ویندوزی اجرا شود که در CRM مجوز خواندن دارد.

## اجرای بررسی اتصال

از ریشه پروژه:

```powershell
python -m pip install -r requirements.txt
python scripts/crm_readonly_probe.py
```

Probe فقط یک رکورد از هر Entity و اطلاعات `WhoAmI` را در ترمینال نمایش می‌دهد و پاسخی روی دیسک ذخیره نمی‌کند.

## Viewهای CRM

در REST API، Entity `savedqueries` برای خواندن Viewهای ذخیره‌شده در دسترس است. Client متد `list_views` را برای خواندن فهرست Viewها دارد. اجرای View باید بر اساس `FetchXML` و Entity واقعی همان View انجام شود؛ تا زمان اعتبارسنجی Viewهای سازمانی، Client فقط خواندن مستقیم چهار Entity اصلی را انجام می‌دهد.

در بررسی Read-Only مورخ ۲۹ اوت ۲۰۲۶، برای Entity `incident` تعداد ۹۲ View خوانده شد. چند View فارسی مرتبط با صف‌های پشتیبانی و Viewهای عمومی Case در دسترس هستند؛ انتخاب View نهایی Pilot هنوز تصمیم مدیریتی است و در این مرحله حدس زده نمی‌شود.

## وضعیت فعلی و گام محدود بعدی

اتصال فنی و احراز هویت تأیید شده است. مورد باقی‌مانده برای استفاده در Prototype، نگاشت فیلدهای تأییدشده و انتخاب Viewهای مجاز Pilot است. این کار در همین دامنه Read-Only انجام می‌شود و قابلیت جدید یا مسیر نوشتن به CRM ایجاد نمی‌کند.

## محدودیت ایمنی

این لایه فقط متدهای GET دارد و هیچ عملیات Create/Update/Delete یا تغییر Case، Note، Task و Knowledge Base ارائه نمی‌کند. داده واقعی نیز توسط Probe در فایل ذخیره نمی‌شود.
