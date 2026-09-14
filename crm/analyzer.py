"""Grounded, local analysis of a CRM Case snapshot."""

from __future__ import annotations

import html
import json
import re
from typing import Any

STOP_WORDS = {
    "برای", "درباره", "است", "شد", "شود", "این", "آن", "یک", "با", "از",
    "به", "در", "را", "که", "و", "یا", "روی", "مورد", "همه", "موارد",
    "لطفا", "خواهشمند", "احترام", "سلام", "می", "کند", "کردن", "شده",
    "سیستم", "خطا", "خطایی", "هنگام", "ورود", "تماس", "مدیر", "کنید",
    "باشد", "داده", "مربوط", "موجود", "جهت", "صورت", "بررسی",
}

SUCCESS_OUTCOME_PATTERN = re.compile(r"(حل شد|برطرف شد|رفع شد|با موفقیت|موفقیت|resolved|fixed|successful)", re.I)
NEGATIVE_OUTCOME_PATTERN = re.compile(r"(حل نشد|برطرف نشد|رفع نشد|موفق نبود|ناموفق|هنوز.*(?:مشکل|وجود|برقرار)|not resolved|not fixed|failed)", re.I)


def has_successful_outcome(value: Any) -> bool:
    text = clean(value)
    return bool(SUCCESS_OUTCOME_PATTERN.search(text) and not NEGATIVE_OUTCOME_PATTERN.search(text))

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


def _quality_score(case: dict[str, Any], quality: dict[str, Any], evidence: list[dict[str, Any]]) -> int:
    """Return a transparent 0-100 score; content quality matters more than field presence."""
    checks = [
        bool(clean(case.get("title")) and len(words(case.get("title"))) >= 2),
        bool(clean(case.get("description")) and len(words(case.get("description"))) >= 5),
        bool(evidence),
        bool(case.get("notes") or case.get("posts") or case.get("tasks")),
        any(re.search(r"(نتیجه|حل|بررسی|انجام|پیگیری|ارجاع)", clean(item.get("text")), re.I) for item in evidence),
        bool(re.search(r"(نسخه|ورژن|version|\\bv\\d)", clean(case.get("description")), re.I)),
        bool(re.search(r"(محیط|عملیاتی|آزمایشی|تستی|production|test)", clean(case.get("description")), re.I)),
        bool(re.search(r"(خطا|پیام|error|exception)", clean(case.get("description")), re.I)) or not clean(case.get("description")),
        bool(clean(case.get("title")) and clean(case.get("description"))),
        not quality.get("issues"),
    ]
    return round(sum(checks) / len(checks) * 100)


def _timeline_intelligence(case: dict[str, Any]) -> dict[str, Any]:
    activities: list[dict[str, Any]] = []
    for kind, rows, text_key in (
        ("Note", case.get("notes", []), "note_text"),
        ("Post داخلی", case.get("posts", []), "text"),
        ("Task داخلی L2", case.get("tasks", []), "description"),
    ):
        for row in rows:
            text = clean(row.get(text_key) or row.get("subject"))
            if text:
                activities.append({
                    "type": kind,
                    "text": text[:500],
                    "date": row.get("created_on") or row.get("createdon") or row.get("modified_on"),
                    "author": clean(row.get("created_by_name") or row.get("createdby_name") or "ثبت‌کننده مشخص نشده"),
                })
    activities.sort(key=lambda item: str(item.get("date") or ""), reverse=True)
    latest = activities[0] if activities else None
    return {
        "activity_count": len(activities),
        "latest_action": latest,
        "actions_with_result": [item for item in activities if re.search(r"(نتیجه|حل|برطرف|موفق|ناموفق|همچنان وجود دارد|ارجاع)", item["text"], re.I)][:5],
        "actions_without_result": [item for item in activities if not re.search(r"(نتیجه|حل|برطرف|موفق|ناموفق|همچنان وجود دارد|ارجاع)", item["text"], re.I)][:5],
    }


def _next_best_actions(case: dict[str, Any], missing: list[dict[str, Any]], evidence: list[dict[str, Any]], timeline: dict[str, Any], articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Create ranked, evidence-grounded next actions for the Help Desk analyst."""
    actions: list[dict[str, Any]] = []
    missing_text = " ".join(clean(item.get("field")) for item in missing)
    if missing and any(term in missing_text for term in ("نسخه", "محیط")):
        actions.append({"action_id": "collect-version-environment", "category": "جمع‌آوری اطلاعات", "title": "نسخه و محیط اجرا را مشخص کن.", "why": "نسخه یا محیط در اطلاعات مورد مشخص نشده است و بدون آن بررسی سازگاری ناقص می‌ماند.", "evidence": "موارد نامشخص تحلیل‌شده: نسخه/محیط", "expected_result": "نسخه محصول و محیط وقوع مشکل ثبت شود.", "rank": 1, "stars": 5})
    if missing and any(term in missing_text for term in ("شرح", "کاربر", "Scope", "دامنه", "زمان", "محدوده")):
        actions.append({"action_id": "collect-scope", "category": "جمع‌آوری اطلاعات", "title": "دامنه، زمان وقوع و کاربران متأثر را مشخص کن.", "why": "Scope یا زمان وقوع از Case و Timeline قابل تعیین نیست.", "evidence": "Unknownهای تحلیل Case", "expected_result": "مشخص شود مشکل تک‌کاربره، گروهی یا سازمانی است و از چه زمانی رخ داده است.", "rank": 2, "stars": 4})
    failed = [item for item in timeline.get("actions_with_result", []) if re.search(r"(ناموفق|برطرف نشد|همچنان وجود دارد|شکست)", item.get("text", ""), re.I)]
    if failed:
        actions.append({"action_id": "follow-failed-investigation", "category": "بررسی", "title": "مرحله بعدی بررسی را پس از اقدام ناموفق قبلی انجام بده.", "why": "اقدام قبلی ناموفق بوده و مشکل برطرف نشده است؛ تکرار همان اقدام پیشنهاد نمی‌شود.", "evidence": failed[0]["text"][:300], "expected_result": "یک فرضیه جدید با نتیجه قابل ثبت بررسی شود.", "rank": 2, "stars": 4})
    elif timeline.get("actions_without_result"):
        actions.append({"action_id": "complete-last-result", "category": "پیگیری", "title": "نتیجه آخرین اقدام ثبت‌شده را تکمیل کن.", "why": "در Timeline اقدام ثبت شده اما نتیجه آن روشن نیست.", "evidence": timeline["actions_without_result"][0]["text"][:300], "expected_result": "نتیجه اقدام به‌صورت موفق، ناموفق یا بی‌نتیجه ثبت شود.", "rank": 2, "stars": 4})
    if articles:
        actions.append({"action_id": "review-kb-article", "category": "دانش", "title": "مقاله مرتبط KB را با شرایط واقعی مورد تطبیق بده.", "why": "مقاله‌ای با تطابق محتوایی در Snapshot پیدا شده است.", "evidence": f"{articles[0].get('public_number') or 'KB'} — {articles[0].get('title', '')}", "expected_result": "مشخص شود راهکار مقاله برای نسخه و محیط این مورد قابل استفاده است یا خیر.", "rank": 3, "stars": 3})
    if missing and not actions:
        actions.append({"action_id": "collect-missing-details", "category": "جمع‌آوری اطلاعات", "title": "اطلاعات ناقص مورد را تکمیل کن.", "why": "بدون این اطلاعات، پیشنهاد فنی قابل اتکا نیست.", "evidence": "کمبودهای شناسایی‌شده در Case", "expected_result": "کمبودهای اولویت‌دار با پاسخ کارشناس یا مشتری تکمیل شوند.", "rank": 1, "stars": 5})
    if not actions:
        actions.append({"action_id": "prepare-l2-evidence", "category": "ارجاع", "title": "Case را برای بررسی L2 با شواهد موجود آماده کن.", "why": "اطلاعات پایه و فعالیت‌های ثبت‌شده برای تصمیم بعدی باید یک‌جا ارائه شوند.", "evidence": f"{len(evidence)} شاهد و {timeline.get('activity_count', 0)} فعالیت مرتبط", "expected_result": "L2 گزارش منسجم و قابل بررسی دریافت کند.", "rank": 1, "stars": 5})
    for index, item in enumerate(actions[:5], start=1):
        item["rank"] = index
    return actions[:5]


class SemanticLikeRetrievalProvider:
    """Replaceable prototype retrieval provider; an embedding provider can implement the same method later."""

    FIELD_WEIGHTS = {
        "subject": 4.0, "description": 3.5, "error": 3.0,
        "resolution": 4.0, "notes": 1.5, "tasks": 1.5,
        "module": 2.0, "version": 2.0, "environment": 2.0,
        "classification": 2.0,
    }
    CONCEPTS = {
        "performance": {"کند", "کندی", "سرعت", "تاخیر", "performance", "slow", "latency"},
        "permission": {"دسترسی", "مجوز", "permission", "access", "نقش", "role"},
        "workflow": {"گردش", "فرم", "workflow", "ثبت", "مرحله"},
        "database": {"پایگاه", "داده", "database", "sql", "oracle", "جدول"},
        "network": {"شبکه", "ارتباط", "network", "timeout", "اتصال"},
        "error": {"خطا", "پیام", "error", "exception", "استثنا"},
    }

    def _fields(self, case: dict[str, Any]) -> dict[str, str]:
        notes = " ".join(clean(row.get("note_text")) for row in case.get("notes", []))
        tasks = " ".join(clean(f"{row.get('subject', '')} {row.get('description', '')}") for row in case.get("tasks", []))
        posts = " ".join(clean(row.get("text")) for row in case.get("posts", []))
        raw = {}
        try:
            raw = json.loads(case.get("raw_json") or "{}")
        except (TypeError, ValueError):
            pass
        def first_value(*keys: str) -> str:
            for key in keys:
                value = clean(case.get(key) or raw.get(key))
                if value:
                    return value
            return ""

        explicit_error = first_value(
            "error_message", "errormessage", "error", "brd_errormessage",
        )
        explicit_resolution = first_value(
            "resolution", "resolution_description", "resolutiondescription",
            "brd_resolution", "brd_resolutiondescription",
        )
        activity_resolution = " ".join(
            text for text in (notes, tasks, posts) if has_successful_outcome(text)
        )
        return {
            "subject": first_value("title", "subject"),
            "description": first_value("description", "incident_description"),
            "error": " ".join(part for part in (explicit_error, case.get("description"), notes, tasks)
                              if re.search(r"(خطا|error|exception|پیام)", clean(part), re.I)),
            "resolution": " ".join(part for part in (explicit_resolution, activity_resolution) if part),
            "notes": notes,
            "tasks": tasks,
            "module": first_value("service", "case_service", "module", "brd_productservice"),
            "version": first_value("version", "product_version", "brd_version"),
            "environment": first_value("environment", "execution_environment", "brd_environment"),
            "classification": first_value("category", "classification", "case_category", "brd_productcategory"),
        }

    def _resolution_items(self, case: dict[str, Any]) -> list[dict[str, str]]:
        """Extract only explicitly successful outcomes from real activities; never infer a fix."""
        items: list[dict[str, str]] = []
        sources = (
            ("Note", case.get("notes", []), "note_text"),
            ("Task", case.get("tasks", []), "description"),
            ("Post", case.get("posts", []), "text"),
        )
        for source, rows, key in sources:
            for row in rows:
                text = clean(row.get(key) or row.get("subject"))
                if text and has_successful_outcome(text):
                    items.append({
                        "source": source,
                        "text": text[:500],
                        "outcome": "موفقیت صراحتاً در متن ثبت شده است.",
                        "confidence": "بالا",
                    })
        return items[:5]

    def _concepts(self, text: str) -> set[str]:
        normalized = clean(text).lower()
        return {name for name, terms in self.CONCEPTS.items() if any(term.lower() in normalized for term in terms)}

    @staticmethod
    def _near_version(left: str, right: str) -> bool:
        left_parts = re.findall(r"\d+", clean(left))
        right_parts = re.findall(r"\d+", clean(right))
        if not left_parts or not right_parts:
            return False
        # نسخه‌های هم‌خانواده مانند 5.2.0 و 5.2.1 به‌عنوان نزدیک شناخته می‌شوند.
        return left_parts[:2] == right_parts[:2]

    def _weighted_similarity(self, left: dict[str, str], right: dict[str, str]) -> tuple[float, list[str]]:
        total = 0.0
        score = 0.0
        reasons: list[str] = []
        for field, weight in self.FIELD_WEIGHTS.items():
            a, b = left.get(field, ""), right.get(field, "")
            if not a or not b:
                continue
            total += weight
            a_words, b_words = words(a), words(b)
            overlap = len(a_words & b_words) / max(1, len(a_words | b_words))
            concepts_a, concepts_b = self._concepts(a), self._concepts(b)
            near_version = field == "version" and self._near_version(a, b)
            concept_match = 1.0 if concepts_a & concepts_b or near_version else 0.0
            field_score = overlap * .35 + concept_match * .65
            score += weight * field_score
            if field_score >= .45:
                reasons.append({"subject": "عنوان مشابه", "description": "نشانه/شرح مشابه", "error": "Error مشابه", "resolution": "Resolution مشابه", "notes": "Note مرتبط", "tasks": "اقدام مشابه", "module": "Module مشابه", "version": "Version نزدیک", "environment": "Environment مشابه", "classification": "دسته‌بندی مشابه"}[field])
        concepts_left, concepts_right = self._concepts(" ".join(left.values())), self._concepts(" ".join(right.values()))
        if concepts_left and concepts_right and not concepts_left & concepts_right:
            score *= .35
            reasons.append("تعارض مفهومی؛ امتیاز کاهش یافت")
        return round(max(0.0, min(100.0, score / max(total, 1.0) * 100)), 1), list(dict.fromkeys(reasons))

    def retrieve(self, case: dict[str, Any], corpus: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
        source_id = str(case.get("crm_id") or case.get("incidentid") or "")
        source = self._fields(case)
        ranked: list[dict[str, Any]] = []
        for candidate in corpus:
            candidate_id = str(candidate.get("crm_id") or candidate.get("incidentid") or "")
            if not candidate_id or candidate_id == source_id:
                continue
            fields = self._fields(candidate)
            score, reasons = self._weighted_similarity(source, fields)
            if score < 25 or not reasons or "تعارض مفهومی؛ امتیاز کاهش یافت" in reasons and score < 55:
                continue
            resolution = fields["resolution"][:500]
            resolution_items = self._resolution_items(candidate)
            resolved = bool(resolution_items)
            ranked.append({
                "case_number": candidate.get("ticket_number") or candidate_id,
                "case_id": candidate_id,
                "title": candidate.get("title") or "عنوان ثبت نشده",
                "similarity_score": score,
                "status": candidate.get("status_code") or "وضعیت ثبت نشده",
                "final_status": candidate.get("status") or candidate.get("status_name") or candidate.get("status_code") or "وضعیت ثبت نشده",
                "summary": (candidate.get("description") or candidate.get("title") or "خلاصه ثبت نشده")[:360],
                "resolution": resolution or None,
                "resolution_items": resolution_items,
                "resolved": resolved,
                "module": fields["module"] or "ثبت نشده",
                "version": fields["version"] or "ثبت نشده",
                "date": candidate.get("modified_on") or candidate.get("created_on"),
                "reasons": reasons[:5],
                "reason": "، ".join(reasons[:4]),
            })
        ranked.sort(key=lambda item: (item["resolved"], item["similarity_score"]), reverse=True)
        return ranked[:limit]


# تغییر موقت — جلالی: بینش‌های عملیاتی مبتنی بر سوابق همان Snapshot؛ بدون تغییر CRM
def _raw_case(case: dict[str, Any]) -> dict[str, Any]:
    try:
        value = json.loads(case.get("raw_json") or "{}")
        return value if isinstance(value, dict) else {}
    except (TypeError, ValueError):
        return {}


def _case_customer_key(case: dict[str, Any]) -> str:
    raw = _raw_case(case)
    for key in (
        "account_name", "customer_name", "customer", "account",
        "_customerid_value", "_brd_account_value", "brd_account",
    ):
        value = clean(case.get(key) or raw.get(key))
        if value:
            return value.lower()
    return ""


def _case_datetime(case: dict[str, Any]) -> str:
    raw = _raw_case(case)
    return clean(case.get("created_on") or case.get("createdon") or raw.get("createdon") or raw.get("created_on"))


def _is_upgrade_case(case: dict[str, Any]) -> bool:
    text = clean(" ".join([
        str(case.get("title") or ""), str(case.get("description") or ""),
        str(case.get("service") or ""), str(case.get("category") or ""),
    ])).lower()
    return bool(re.search(r"(upgrade|update|version|release|patch|\u0628\u0631\u0648\u0632\u0631\u0633\u0627\u0646\u06cc|\u0646\u0633\u062e\u0647|\u0646\u06af\u0627\u0631\u0634|\u0628\u0647\u200c\u0631\u0648\u0632\u0631\u0633\u0627\u0646\u06cc)", text, re.I))


def _operational_insights(case: dict[str, Any], corpus: list[dict[str, Any]], articles: list[dict[str, Any]]) -> dict[str, Any]:
    """Return transparent operational warnings and quality gates from read-only CRM data."""
    provider = SemanticLikeRetrievalProvider()
    source_customer = _case_customer_key(case)
    source_date = _case_datetime(case)
    same_customer: list[dict[str, Any]] = []
    cross_customer: list[dict[str, Any]] = []
    for candidate in corpus:
        if str(candidate.get("crm_id") or candidate.get("incidentid")) == str(case.get("crm_id") or case.get("incidentid")):
            continue
        score, reasons = provider._weighted_similarity(provider._fields(case), provider._fields(candidate))
        # برای هشدار تکرار در همان مرکز، تطبیق ۵۰٪ به‌همراه شناسه مرکز کافی است؛
        # هشدارهای الگوی مشترک بین مراکز همچنان با شواهد و بررسی انسانی تفسیر می‌شوند.
        if score < 50:
            continue
        candidate_customer = _case_customer_key(candidate)
        row = {
            "case_number": candidate.get("ticket_number") or candidate.get("ticketnumber") or candidate.get("crm_id"),
            "case_id": candidate.get("crm_id") or candidate.get("incidentid"),
            "title": clean(candidate.get("title")),
            "similarity_score": score,
            "date": _case_datetime(candidate),
            "reasons": reasons[:4],
            "customer": candidate_customer or "ثبت نشده",
        }
        if source_customer and candidate_customer == source_customer:
            same_customer.append(row)
        elif candidate_customer and candidate_customer != source_customer:
            cross_customer.append(row)
    same_customer.sort(key=lambda item: item["similarity_score"], reverse=True)
    cross_customer.sort(key=lambda item: item["similarity_score"], reverse=True)

    timeline_text = " ".join(clean(row.get("text") or row.get("note_text") or row.get("description")) for row in (
        case.get("notes", []) + case.get("posts", []) + case.get("tasks", [])
    ))
    result_quality = {
        "ready_to_close": False,
        "missing": [],
        "evidence": [],
    }
    if case.get("tasks") or case.get("posts") or case.get("notes"):
        required_result_terms = {
            "root_cause": r"(root cause|\u0639\u0644\u062a \u0627\u0635\u0644\u06cc|\u0639\u0644\u062a \u0631\u06cc\u0634\u0647)",
            "method": r"(diagnos|\u0631\u0648\u0634 \u062a\u0634\u062e\u06cc\u0635|\u0634\u0646\u0627\u0633\u0627\u06cc\u06cc)",
            "action": r"(action|\u0627\u0642\u062f\u0627\u0645|\u0627\u0646\u062c\u0627\u0645 \u0634\u062f)",
            "result": r"(result|\u0646\u062a\u06cc\u062c\u0647|\u0628\u0631\u0637\u0631\u0641|\u062d\u0644 \u0634\u062f)",
        }
        for label, pattern in required_result_terms.items():
            if re.search(pattern, timeline_text, re.I):
                result_quality["evidence"].append(label)
            else:
                result_quality["missing"].append(label)
        result_quality["ready_to_close"] = not result_quality["missing"]

    raw = _raw_case(case)
    version = clean(case.get("version") or raw.get("version") or raw.get("brd_version"))
    version_control = {
        "applicable": _is_upgrade_case(case),
        "version": version or None,
        "ready": bool(version),
        "message": "نسخه نهایی مرکز ثبت شده است." if version else "برای این مورد به‌روزرسانی، نسخه نهایی نصب‌شده مرکز ثبت نشده است.",
    }
    resolved = has_successful_outcome(timeline_text)
    knowledge_candidate = {
        "eligible": bool(resolved and not articles),
        "reason": "Case نشانه حل موفق دارد اما مقاله مرتبط در Snapshot پیدا نشد؛ پیش‌نویس مقاله پس از بازبینی انسانی پیشنهاد می‌شود." if resolved and not articles else "شرایط کافی برای پیشنهاد ساخت مقاله فراهم نیست.",
        "source_case": case.get("ticket_number") or case.get("crm_id"),
    }
    return {
        "same_customer_recurrence": {
            "count": len(same_customer), "cases": same_customer[:10],
            "warning": len(same_customer) >= 2,
            "message": f"در سوابق این مرکز {len(same_customer)} مورد مشابه پیدا شد." if same_customer else "مورد مشابهی برای همین مرکز در Snapshot پیدا نشد.",
        },
        "cross_customer_pattern": {
            "count": len(cross_customer), "cases": cross_customer[:10],
            "warning": len(cross_customer) >= 2,
            "message": f"این الگو در {len(cross_customer)} مرکز دیگر نیز دیده شده است." if cross_customer else "الگوی مشترک بین مراکز دیگر با شواهد فعلی پیدا نشد.",
        },
        "technical_result_quality": result_quality,
        "upgrade_version_control": version_control,
        "knowledge_candidate": knowledge_candidate,
        "read_only": True,
    }


def analyze_case(case: dict[str, Any], similar_cases: list[dict[str, Any]] | None = None) -> dict[str, Any]:
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
    for item_type, rows, text_key in (("Note ارتباطی", case.get("notes", []), "note_text"), ("Post داخلی", case.get("posts", []), "text"), ("Task داخلی L2", case.get("tasks", []), "description")):
        for row in rows[:3]:
            value = clean(row.get(text_key) or row.get("subject"))
            if value:
                evidence.append({
                    "type": item_type,
                    "text": value[:500],
                    "date": row.get("created_on") or row.get("createdon") or row.get("modified_on"),
                    "relation": "به موضوع مورد مرتبط است؛ بررسی انسانی لازم است.",
                })
    if description:
        evidence.insert(0, {
            "type": "Description",
            "text": description[:500],
            "date": case.get("created_on"),
            "relation": "شرح اصلی ثبت‌شده برای مورد.",
        })

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

    priority_by_position = ["زیاد", "زیاد", "متوسط", "متوسط", "کم"]
    for index, item in enumerate(missing):
        item["priority"] = priority_by_position[min(index, len(priority_by_position) - 1)]

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

    timeline = _timeline_intelligence(case)
    next_best_actions = _next_best_actions(case, missing, evidence, timeline, articles)
    similar_results = SemanticLikeRetrievalProvider().retrieve(case, similar_cases or [], limit=50)
    operational_insights = _operational_insights(case, similar_cases or [], articles)
    quality_score = _quality_score(case, quality, evidence)
    unknowns = [
        {
            "title": item["field"],
            "reason": item["reason"],
        }
        for item in missing[:8]
    ]
    summary_parts = []
    if title:
        summary_parts.append(f"موضوع مورد: {title}.")
    if description:
        summary_parts.append(f"شرح ثبت‌شده نشان می‌دهد: {description[:360]}.")
    if timeline["activity_count"]:
        summary_parts.append(f"در Timeline {timeline['activity_count']} فعالیت مرتبط ثبت شده است.")
    if not summary_parts:
        summary_parts.append("برای این مورد اطلاعات متنی کافی برای تهیه خلاصه وجود ندارد.")
    status_text = clean(
        case.get("status") or case.get("status_name") or case.get("status_code")
    ) or "وضعیت از داده موجود قابل تعیین نیست"
    if not title and not description:
        suggested_status = "⚪ اطلاعات ناکافی"
    elif tasks:
        suggested_status = "🟣 نیازمند بررسی L2"
    elif missing:
        suggested_status = "🔴 نیازمند بررسی"
    else:
        suggested_status = "🔵 نیازمند تأیید کارشناس"
    quality_explanation = (
        "این مورد برای ادامه بررسی مناسب است؛ "
        + ("اما " + "، ".join(item["field"] for item in missing[:3]) + " ثبت نشده است." if missing else "شواهد و اطلاعات پایه کافی به نظر می‌رسد.")
    )

    return {
        "case_id": case.get("crm_id"),
        "summary": " ".join(summary_parts[:4]),
        "current_status": status_text,
        "suggested_status": suggested_status,
        "quality_score": quality_score,
        "quality_explanation": quality_explanation,
        "missing": missing,
        "quality": quality,
        "evidence": evidence,
        "unknowns": unknowns,
        "timeline_intelligence": timeline,
        "classification": {
            "label": domain_label,
            "confidence": "۷۰٪" if matched_domain else "۳۵٪",
            "reason": domain_action,
        },
        "suggested_questions": [item["question"] for item in missing[:5]],
        "next_actions": [item["title"] for item in recommendations[:5]],
        "next_best_actions": next_best_actions,
        "similar_cases": similar_results,
        "operational_insights": operational_insights,
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
