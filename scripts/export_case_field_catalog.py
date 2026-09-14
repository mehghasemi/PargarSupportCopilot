"""Export the live CRM Case field catalog for business review."""

from __future__ import annotations

import csv
import json
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from crm import CrmClient


PERSIAN_LABELS = {
    "incidentid": "شناسه مورد",
    "ticketnumber": "شماره مورد",
    "title": "عنوان مورد",
    "description": "شرح مسئله",
    "customerid": "مشتری",
    "customeridname": "نام مشتری",
    "accountid": "حساب/سازمان مشتری",
    "accountidname": "نام حساب/سازمان",
    "primarycontactid": "مخاطب اصلی",
    "contactid": "مخاطب",
    "ownerid": "مالک مورد",
    "owneridname": "نام مالک مورد",
    "owningteam": "تیم مالک",
    "owninguser": "کاربر مالک",
    "statecode": "وضعیت کلی",
    "statuscode": "دلیل وضعیت",
    "prioritycode": "اولویت",
    "casetypecode": "نوع مورد",
    "caseorigincode": "منشأ مورد",
    "severitycode": "شدت",
    "brd_caseservice": "خدمت مورد",
    "brd_productservice": "خدمت/محصول",
    "brd_productcategory": "دسته‌بندی محصول",
    "brd_incidenttype": "نوع رخداد",
    "brd_pargarmodule": "ماژول پرگار",
    "brd_version": "نسخه",
    "brd_environment": "محیط اجرا",
    "brd_resolution": "راهکار/نتیجه حل",
    "brd_rootcause": "علت ریشه‌ای",
    "brd_mainrootcause": "علت ریشه‌ای اصلی",
    "brd_scenario": "سناریو",
    "brd_note": "یادداشت مورد",
    "brd_releasenote": "یادداشت انتشار",
    "brd_doneversion": "نسخه رفع‌شده",
    "brd_knowledgebaseartilcleurl": "نشانی مقاله پایگاه دانش",
    "createdon": "تاریخ ایجاد",
    "modifiedon": "تاریخ آخرین تغییر",
    "createdby": "ایجادکننده",
    "modifiedby": "آخرین تغییر‌دهنده",
    "followupby": "مهلت پیگیری",
    "resolveby": "مهلت حل",
    "brd_duedate": "تاریخ سررسید",
    "brd_laststatuschange": "آخرین تغییر وضعیت",
    "brd_lastnotedate": "تاریخ آخرین Note",
    "brd_donedate": "تاریخ پایان",
    "brd_realstartdate": "تاریخ شروع واقعی",
    "brd_realenddate": "تاریخ پایان واقعی",
    "brd_plannedstartdate": "تاریخ شروع برنامه‌ریزی‌شده",
    "brd_plannedenddate": "تاریخ پایان برنامه‌ریزی‌شده",
    "brd_assignto": "ارجاع به",
    "brd_followcase": "پیگیری مورد",
    "brd_hastechnicaltask": "دارای Task فنی",
    "brd_requestpatch": "درخواست Patch",
    "brd_hasreleasenote": "دارای یادداشت انتشار",
    "brd_resolvedbydiag": "حل‌شده از طریق Diag",
    "isescalated": "ارجاع‌شده",
    "customercontacted": "تماس با مشتری انجام شده",
    "activitiescomplete": "فعالیت‌ها کامل شده‌اند",
}

TYPE_LABELS = {
    "String": "رشته‌ای",
    "Memo": "متن بلند",
    "DateTime": "تاریخ و زمان",
    "Boolean": "بله/خیر",
    "Picklist": "انتخابی",
    "Status": "وضعیت",
    "State": "وضعیت سیستمی",
    "Lookup": "ارتباط با رکورد دیگر",
    "Customer": "مشتری/حساب/مخاطب",
    "Owner": "مالک",
    "Integer": "عدد صحیح",
    "Decimal": "عدد اعشاری",
    "Double": "عدد اعشاری دقیق",
    "BigInt": "عدد بزرگ",
    "Uniqueidentifier": "شناسه یکتا",
    "EntityName": "نام موجودیت",
    "Virtual": "محاسباتی/نمایشی",
}


def localized_label(attribute: dict) -> str:
    display = attribute.get("DisplayName") or {}
    localized = display.get("UserLocalizedLabel") or display.get("LocalizedLabels") or {}
    if isinstance(localized, dict):
        return str(localized.get("Label") or "")
    if isinstance(localized, list) and localized:
        return str(localized[0].get("Label") or "")
    return ""


def build_rows() -> list[dict[str, str]]:
    rows = []
    for index, attribute in enumerate(CrmClient().list_case_field_metadata(), start=1):
        logical = str(attribute.get("LogicalName") or "")
        crm_label = localized_label(attribute)
        rows.append({
            "ردیف": str(index),
            "نام فارسی": PERSIAN_LABELS.get(logical) or "برچسب فارسی در CRM ثبت نشده",
            "برچسب موجود در CRM": crm_label or "ثبت نشده",
            "نام انگلیسی / LogicalName": logical,
            "نوع فیلد انگلیسی": str(attribute.get("AttributeType") or "نامشخص"),
            "نوع فیلد فارسی": TYPE_LABELS.get(str(attribute.get("AttributeType") or ""), "نوع نامشخص"),
            "قابل خواندن": "بله" if attribute.get("IsValidForRead") is not False else "خیر",
            "وضعیت نام فارسی": "ترجمه کنترل‌شده" if logical in PERSIAN_LABELS else "نیازمند تعیین برچسب توسط مالک CRM",
        })
    return rows


def write_outputs(rows: list[dict[str, str]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "case-field-catalog-2026-09-13.csv"
    md_path = output_dir / "case-field-catalog-2026-09-13.md"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), dialect="excel")
        writer.writeheader()
        writer.writerows(rows)
    lines = [
        "# فهرست فیلدهای موجودیت Case در CRM",
        "",
        f"تاریخ استخراج: {date(2026, 9, 13).isoformat()} — تعداد فیلدهای قابل‌خواندن: {len(rows)}",
        "",
        "> نام فارسی فقط در مواردی که ترجمه کنترل‌شده در این خروجی وجود دارد درج شده است؛ برای سایر موارد، برچسب فارسی باید توسط مالک CRM تعیین شود.",
        "",
        "| " + " | ".join(rows[0]) + " |",
        "|" + "|".join(["---"] * len(rows[0])) + "|",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row[key]).replace("|", "\\|") for key in row) + " |")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"count": len(rows), "csv": str(csv_path), "markdown": str(md_path)}, ensure_ascii=False))


if __name__ == "__main__":
    write_outputs(build_rows(), PROJECT_ROOT / "docs" / "exports")
