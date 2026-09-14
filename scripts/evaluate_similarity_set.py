"""Calculate offline metrics for the human-labelled Similar Cases review set."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def evaluate(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = payload.get("items", [])
    grouped: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        grouped[str(item.get("source_case_id"))].append(item)

    reviewed = [item for item in items if item.get("human_label") in {"similar", "not_similar", "uncertain"}]
    labelled_similar = [item for item in reviewed if item.get("human_label") == "similar"]
    labelled_not_similar = [item for item in reviewed if item.get("human_label") == "not_similar"]
    sources_with_review = 0
    sources_with_relevant = 0
    precision_sum = 0.0
    for source_id, candidates in grouped.items():
        reviewed_candidates = [item for item in candidates if item.get("human_label") in {"similar", "not_similar", "uncertain"}]
        if not reviewed_candidates:
            continue
        sources_with_review += 1
        relevant = [item for item in reviewed_candidates if item.get("human_label") == "similar"]
        if relevant:
            sources_with_relevant += 1
        precision_sum += len(relevant) / len(reviewed_candidates)

    return {
        "source_file": str(path),
        "total_pairs": len(items),
        "reviewed_pairs": len(reviewed),
        "pending_pairs": len(items) - len(reviewed),
        "similar_pairs": len(labelled_similar),
        "not_similar_pairs": len(labelled_not_similar),
        "uncertain_pairs": len(reviewed) - len(labelled_similar) - len(labelled_not_similar),
        "sources_with_review": sources_with_review,
        "sources_with_relevant": sources_with_relevant,
        "precision_at_reviewed_candidates": round(precision_sum / sources_with_review, 4) if sources_with_review else None,
        "warning": "تا وقتی همه یا بخش کافی از زوج‌ها برچسب‌گذاری نشوند، این عدد نماینده عملکرد واقعی نیست.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="محاسبه معیارهای آفلاین Similar Cases")
    parser.add_argument("input", type=Path, help="فایل JSON مجموعه برچسب‌گذاری‌شده")
    parser.add_argument("--output", type=Path, help="مسیر ذخیره گزارش JSON")
    args = parser.parse_args()
    report = evaluate(args.input)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
