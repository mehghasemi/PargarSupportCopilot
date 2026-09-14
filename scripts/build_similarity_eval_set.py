"""Build a human-review queue from real local CRM Snapshot data.

The output is intentionally local and should not be committed because it may contain
customer information. No CRM write operation is performed.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from crm.analyzer import SemanticLikeRetrievalProvider
from crm.local_store import DEFAULT_DB_PATH, LocalStore


def build(output: Path, limit_per_case: int = 5) -> dict:
    store = LocalStore(DEFAULT_DB_PATH)
    store.initialize()
    try:
        cases = [store.get_case(row["crm_id"]) for row in store.list_cases()]
        cases = [case for case in cases if case]
        provider = SemanticLikeRetrievalProvider()
        items = []
        for case in cases:
            matches = provider.retrieve(case, cases, limit=limit_per_case)
            for match in matches:
                items.append({
                    "source_case_id": case.get("crm_id"),
                    "source_case_number": case.get("ticket_number"),
                    "candidate_case_id": match["case_id"],
                    "candidate_case_number": match["case_number"],
                    "algorithm_score": match["similarity_score"],
                    "algorithm_reasons": match["reasons"],
                    "human_label": None,
                    "reviewer": None,
                    "reviewed_at": None,
                    "review_comment": None,
                })
        payload = {
            "schema_version": "1.0",
            "created_at": date.today().isoformat(),
            "source": "local CRM Snapshot",
            "case_count": len(cases),
            "item_count": len(items),
            "label_values": ["similar", "not_similar", "uncertain"],
            "items": items,
        }
    finally:
        store.close()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="ساخت صف ارزیابی انسانی موارد مشابه")
    parser.add_argument("--output", type=Path, default=Path("data/evaluation/similar-cases-review.json"))
    parser.add_argument("--limit-per-case", type=int, default=5)
    args = parser.parse_args()
    payload = build(args.output, max(1, min(args.limit_per_case, 20)))
    print(f"Created {payload['item_count']} review pairs for {payload['case_count']} cases: {args.output}")


if __name__ == "__main__":
    main()
