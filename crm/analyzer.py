"""Grounded, local analysis of a CRM Case snapshot."""

from __future__ import annotations

import html
import re
from typing import Any

STOP_WORDS = {
    "برای", "درباره", "است", "شد", "شود", "این", "آن", "یک", "با", "از",
    "به", "در", "را", "که", "و", "یا", "روی", "مورد", "همه", "موارد",
    "لطفا", "خواهشمند", "احترام", "سلام", "می", "کند", "کردن", "شده",
    "سیستم", "خطا", "خطایی", "هنگام", "ورود", "تماس", "مدیر", "کنید",
    "باشد", "داده", "مربوط", "موجود", "جهت", "صورت", "بررسی",
}

DOMAIN_RULES = [
    (("دسترسی", "مجوز", "کاربر", "رویت", "قابل مشاهده"), "دسترسی و مجوزها",
     "ابتدا دسترسی کاربر، نقش/جایگاه و دامنه سازمانی بررسی شود؛ سپس نتیجه با یک کاربر نمونه بازتولید شود."),
    (("خطا", "پیغام", "استثنا", "exception", "error"), "خطا و اختلال",
     "متن کامل خطا، زمان وقوع، کاربر/سازمان و محیط ثبت شود؛ سپس خطا با همان شرایط بازتولید و لاگ مرتبط بررسی شود."),
    (("فرم", "گردش", "شرط", "کارپوشه", "workflow"), "فرم و گردش کار",
     "تعریف فرم، مسیر گردش، شرط/یال و مرحله‌ای که رفتار در آن رخ می‌دهد مستندسازی و در محیط آزمایشی بازتولید شود."),
    (("نامه", "مکاتبه", "دبیرخانه", "فرستنده", "گیرنده"), "مکاتبات",
     "شماره/شناسه نامه، نقش کاربر و مسیر مکاتبه بررسی شود؛ سپس دسترسی و تنظیمات گیرنده/فرستنده کنترل شود."),
    (("گزارش", "گزارش‌گیری", "فیلتر", "ستون"), "گزارش‌گیری",
     "نمونه گزارش، فیلترها، کاربر اجراکننده و خروجی مورد انتظار ثبت شود و اختلاف خروجی با همان پارامترها بررسی شود."),
    (("پایگاه داده", "دیتابیس", "sql", "جدول", "کندی"), "پایگاه داده و کارایی",
     "زمان وقوع، سرویس/جدول درگیر و شاخص کندی ثبت شود؛ بررسی فنی پایگاه داده فقط پس از تأیید L2 انجام شود."),
]


def clean(value: Any) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def words(text: str) -> set[str]:
    normalized = re.sub(r"[^\w\s]", " ", clean(text), flags=re.UNICODE)
    return {
        token.lower()
        for token in re.findall(r"[A-Za-z0-9_\u0600-\u06ff]+", normalized)
        if len(token) > 3 and token.lower() not in STOP_WORDS
    }


def evaluate_case_quality(case: dict[str, Any]) -> dict[str, Any]:
    """Evaluate Release 1 input quality without treating filled fields as sufficient."""
    title = clean(case.get("title"))
    description = clean(case.get("description"))
    context = clean(" ".join([
        description,
        *(clean(row.get("note_text")) for row in case.get("notes", [])),
        *(clean(row.get("text")) for row in case.get("posts", [])),
        *(clean(f"{row.get('subject', '')} {row.get('description', '')}")
          for row in case.get("tasks", [])),
    ]))
    issues: list[dict[str, str]] = []

    if not title:
        issues.append({"field": "عنوان Case", "kind": "missing", "reason": "عنوان ثبت نشده است."})
    elif len(words(title)) < 2 or title.lower() in {"مشکل", "راهنمایی", "سوال", "درخواست"}:
        issues.append({"field": "عنوان Case", "kind": "low_quality", "reason": "عنوان برای فهم موضوع کافی و توصیفی نیست."})

    if not description:
        issues.append({"field": "شرح مسئله", "kind": "missing", "reason": "شرح مسئله ثبت نشده است."})
    elif len(words(description)) < 5:
        issues.append({"field": "شرح مسئله", "kind": "low_quality", "reason": "شرح برای فهم رفتار مورد انتظار و مشاهده‌شده کوتاه است."})

    if not re.search(r"(نتیجه|اقدام|حل|بررسی|انجام|پیگیری|ارجاع)", context, re.I):
        issues.append({"field": "اقدام/نتیجه", "kind": "missing", "reason": "شاهدی از اقدام یا نتیجه در Case و Timeline پیدا نشد."})

    return {
        "is_content_complete": not issues,
        "issues": issues,
        "quality_rule": "مقدار فیلد به‌تنهایی کافی نیست؛ متن باید توصیفی، مرتبط و دارای شاهد اقدام/نتیجه باشد.",
    }


def analyze_case(case: dict[str, Any]) -> dict[str, Any]:
    title = clean(case.get("title"))
    description = clean(case.get("description"))
    notes = [clean(row.get("note_text")) for row in case.get("notes", [])]
    posts = [clean(row.get("text")) for row in case.get("posts", [])]
    tasks = [
        clean(f"{row.get('subject', '')} {row.get('description', '')}")
        for row in case.get("tasks", [])
    ]
    context = " ".join([title, description, *notes, *posts, *tasks])
    context_words = words(context)
    context_lower = context.lower()

    quality = evaluate_case_quality(case)
    missing: list[dict[str, str]] = [
        {
            "field": item["field"],
            "question": (
                "لطفاً عنوانی توصیفی شامل موضوع و بخش درگیر ثبت کنید."
                if item["field"] == "عنوان Case"
                else "لطفاً شرح مسئله، رفتار مورد انتظار، رفتار مشاهده‌شده و اقدام/نتیجه را ثبت کنید."
            ),
            "reason": item["reason"],
        }
        for item in quality["issues"]
    ]
    if not re.search(r"(نسخه|ورژن|version|\bv\d)", context, re.I):
        missing.append({
            "field": "نسخه محصول",
            "question": "نسخه محصول و ماژول درگیر چیست؟",
            "reason": "نسخه در Case یا Timeline پیدا نشد.",
        })
    if not re.search(r"(محیط|عملیاتی|آزمایشی|تست|production|test)", context, re.I):
        missing.append({
            "field": "محیط اجرا",
            "question": "مشکل در کدام محیط رخ می‌دهد؟",
            "reason": "محیط اجرا در Case یا Timeline پیدا نشد.",
        })

    articles: list[dict[str, Any]] = []
    for article in case.get("knowledge_articles", []):
        article_title = clean(article.get("title"))
        article_content = clean(article.get("content"))
        title_words = words(article_title)
        content_words = words(article_content)
        title_hits = sorted(context_words & title_words)
        content_hits = sorted(context_words & content_words)
        score = len(title_hits) * 4 + len(content_hits)
        if (title_hits or len(content_hits) >= 2) and article_content:
            articles.append({
                "id": article.get("crm_id"),
                "public_number": article.get("public_number"),
                "title": article_title,
                "score": score,
                "matched_terms": title_hits[:5] or content_hits[:5],
                "reason": "هم‌پوشانی معنادار با موضوع Case در عنوان/محتوای مقاله.",
                "evidence": article_content[:360],
                "status": "مقاله دارای محتوای Snapshot‌شده؛ تأیید نهایی با کارشناس",
            })
    articles.sort(key=lambda row: row["score"], reverse=True)
    articles = articles[:3]

    evidence = []
    for item_type, values in (("Note ارتباطی", notes), ("Post داخلی", posts), ("Task داخلی L2", tasks)):
        for value in values[:3]:
            if value:
                evidence.append({"type": item_type, "text": value[:500]})

    if articles:
        best = articles[0]
        action = (
            f"مقاله «{best['title']}» ({best['public_number']}) بررسی شود؛ "
            "فقط بخش منطبق با محیط و نسخه مشتری در پاسخ استفاده شود."
        )
    else:
        action = (
            "در Snapshot فعلی مقاله KB با ارتباط معنادار پیدا نشد؛ "
            "پاسخ قطعی تولید نشود و ابتدا کمبودهای اطلاعاتی تکمیل یا به L2 ارجاع شود."
        )

    matched_domain = None
    for terms, label, action in DOMAIN_RULES:
        if any(term.lower() in context_lower for term in terms):
            matched_domain = (label, action)
            break
    if matched_domain:
        domain_label, domain_action = matched_domain
    else:
        domain_label = "موضوع عمومی/نامشخص"
        domain_action = "ابتدا موضوع، رفتار مورد انتظار، رفتار مشاهده‌شده و محیط اجرا تکمیل شود؛ سپس درباره ارجاع تصمیم‌گیری شود."

    recommendations: list[dict[str, Any]] = [{
        "type": "اقدام بعدی",
        "title": f"بررسی موضوع «{domain_label}»",
        "text": domain_action,
        "owner": "L1؛ در صورت نیاز L2",
        "reason": "موضوع از عنوان، شرح و Timeline همین Case استخراج شده است.",
        "evidence": (title or description or "اطلاعات متنی Case")[:300],
        "confidence": "متوسط" if matched_domain else "پایین",
    }]
    if missing:
        recommendations.append({
            "type": "تکمیل Case",
            "title": "تکمیل اطلاعات قبل از پاسخ قطعی",
            "text": "موارد زیر تکمیل شود: " + "، ".join(item["field"] for item in missing[:4]) + ".",
            "owner": "L1",
            "reason": "این فیلدها در داده Case و Timeline پیدا نشدند.",
            "evidence": "تحلیل فیلدهای Case و فعالیت‌های مرتبط",
            "confidence": "بالا",
        })
    if tasks:
        recommendations.append({
            "type": "پیگیری داخلی",
            "title": "ادامه پیگیری Taskهای L2",
            "text": f"{len(tasks)} Task داخلی L2 در Timeline وجود دارد؛ وضعیت و نتیجه آخرین Task بررسی و در صورت بازبودن پیگیری شود.",
            "owner": "L2",
            "reason": "Task مرتبط در Timeline Case وجود دارد.",
            "evidence": tasks[0][:300],
            "confidence": "بالا",
        })
    if articles:
        recommendations.append({
            "type": "دانش",
            "title": f"بررسی مقاله «{articles[0]['title']}»",
            "text": "مقاله قبل از استفاده با نسخه محصول، محیط و شرایط واقعی مشتری تطبیق داده شود.",
            "owner": "L1 با تأیید L2 در موارد فنی",
            "reason": articles[0]["reason"],
            "evidence": f"{articles[0]['public_number']}؛ واژه‌های منطبق: {', '.join(articles[0]['matched_terms'])}",
            "confidence": "متوسط",
        })

    answer_parts = [
        f"موضوع: {title or 'عنوان ثبت نشده'}",
        f"شرح: {description or 'شرح مسئله در Case ثبت نشده است.'}",
    ]
    if evidence:
        answer_parts.append(
            "شاهد Timeline: " + " | ".join(
                f"{row['type']}: {row['text']}" for row in evidence[:2]
            )
        )
    answer_parts.extend([f"پیشنهاد اقدام: {action}", "این متن پیش‌نویس است و نیاز به تأیید کارشناس دارد."])

    return {
        "case_id": case.get("crm_id"),
        "missing": missing,
        "quality": quality,
        "evidence": evidence,
        "articles": articles,
        "recommendations": recommendations,
        "answer": "\n\n".join(answer_parts),
        "confidence": "متوسط" if articles else "پایین",
        "grounding": {
            "notes": len(notes),
            "posts": len(posts),
            "tasks": len(tasks),
            "knowledge_articles_examined": len(case.get("knowledge_articles", [])),
        },
    }


def search_knowledge_articles(
    articles: list[dict[str, Any]], query: str, *, limit: int = 3
) -> list[dict[str, Any]]:
    """Return grounded KB matches for one checklist step."""
    query_words = words(query)
    ranked: list[dict[str, Any]] = []
    for article in articles:
        title = clean(article.get("title"))
        content = clean(article.get("content"))
        title_words = words(title)
        content_words = words(content)
        title_hits = sorted(query_words & title_words)
        content_hits = sorted(query_words & content_words)
        score = len(title_hits) * 5 + len(content_hits)
        if (title_hits or len(content_hits) >= 2) and content:
            ranked.append({
                "public_number": article.get("public_number"),
                "title": title,
                "matched_terms": title_hits[:5] or content_hits[:5],
                "score": score,
                "reason": "تطابق با موضوع همین مرحله در عنوان یا محتوای مقاله.",
                "evidence": content[:240],
            })
    ranked.sort(key=lambda item: item["score"], reverse=True)
    return ranked[:limit]
