# مجموعه ارزیابی موارد مشابه

این پوشه قالب و روش ساخت مجموعه ارزیابی Similar Cases را نگهداری می‌کند. به‌دلیل محرمانگی داده CRM، متن واقعی Caseها در Git ثبت نمی‌شود.

برای ساخت صف بازبینی از Snapshot محلی:

```powershell
python scripts/build_similarity_eval_set.py --output data/evaluation/similar-cases-review.json
```

فایل خروجی شامل زوج‌های واقعی از Snapshot، امتیاز و دلیل الگوریتم است؛ ستون `human_label` ابتدا خالی است و باید توسط کارشناس با یکی از `similar`، `not_similar` یا `uncertain` تکمیل شود.

پس از تکمیل برچسب‌ها، معیارهای Precision@5 و نرخ موارد نامشابه در پنج نتیجه اول گزارش می‌شوند. این مجموعه «مرجع ارزیابی» است و مبنای تغییر خودکار Resolution یا وضعیت CRM نیست.

برای محاسبه گزارش آفلاین پس از تکمیل برچسب‌ها:

```powershell
python scripts/evaluate_similarity_set.py data/evaluation/similar-cases-review.json --output data/evaluation/similarity-metrics.json
```

گزارش شامل تعداد زوج‌های بررسی‌شده، Similar/Not Similar/Uncertain، تعداد Caseهای دارای بازبینی و Precision روی زوج‌های برچسب‌خورده است. تا پیش از تکمیل برچسب انسانی، اعداد فقط وضعیت پیشرفت ارزیابی هستند و معیار تولیدی محسوب نمی‌شوند.
