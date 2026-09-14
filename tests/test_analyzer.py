import unittest
import json
import tempfile
from pathlib import Path

from crm.analyzer import analyze_case, search_knowledge_articles
from crm.local_store import LocalStore
from scripts.evaluate_similarity_set import evaluate


class AnalyzerTests(unittest.TestCase):
    def test_next_best_action_prioritizes_missing_version(self):
        result = analyze_case({
            "crm_id": "case-1",
            "title": "کندی سامانه برای کاربران",
            "description": "کاربران گزارش کرده‌اند که سامانه در زمان جستجو کند است.",
            "notes": [], "posts": [], "tasks": [], "knowledge_articles": [],
        })
        self.assertTrue(result["next_best_actions"])
        self.assertIn("نسخه", result["next_best_actions"][0]["title"])
        self.assertIn("expected_result", result["next_best_actions"][0])

    def test_next_best_action_does_not_claim_resolution(self):
        result = analyze_case({
            "crm_id": "case-2",
            "title": "خطای گردش کار",
            "description": "خطای گردش کار هنگام ثبت فرم نمایش داده می‌شود.",
            "notes": [{"note_text": "Restart انجام شد اما مشکل همچنان وجود دارد."}],
            "posts": [], "tasks": [], "knowledge_articles": [],
        })
        actions = result["next_best_actions"]
        self.assertTrue(actions)
        self.assertNotIn("Restart", actions[0]["title"])
        self.assertTrue(any("ناموفق" in item["why"] for item in actions))

    def test_returns_grounded_article_match(self):
        result = search_knowledge_articles(
            [{
                "public_number": "KB-1",
                "title": "بررسی کندی جستجوی نامه",
                "content": "برای بررسی کندی جستجو، زمان و دامنه کاربران را ثبت کنید.",
            }],
            "کندی جستجوی نامه",
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["public_number"], "KB-1")
        self.assertTrue(result[0]["matched_terms"])

    def test_does_not_guess_without_evidence(self):
        result = search_knowledge_articles(
            [{"public_number": "KB-2", "title": "راهنمای عمومی", "content": "متن نامرتبط"}],
            "کندی سیستم",
        )
        self.assertEqual(result, [])

    def test_filled_but_generic_content_is_not_complete(self):
        result = analyze_case({
            "crm_id": "case-1",
            "title": "مشکل",
            "description": "کند است",
            "notes": [],
            "posts": [],
            "tasks": [],
            "knowledge_articles": [],
        })
        self.assertFalse(result["quality"]["is_content_complete"])
        self.assertTrue(any(item["kind"] == "low_quality" for item in result["quality"]["issues"]))

    def test_discovery_summary_is_preliminary_and_read_only(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LocalStore(Path(directory) / "snapshot.sqlite3")
            store.initialize()
            store.replace_snapshot(
                [{
                    "incidentid": "case-1",
                    "ticketnumber": "CAS-1",
                    "title": "عنوان",
                    "description": "شرح",
                    "case_service": "۱۵ - راهنمایی",
                    "category": "راهنمایی",
                    "createdon": "2026-08-01T00:00:00Z",
                }],
                [], [], [],
            )
            summary = store.discovery_summary()
            self.assertEqual(summary["total_cases"], 1)
            self.assertEqual(summary["preliminary_complete_cases"], 1)
            self.assertIn("مقدماتی", summary["disclaimer"])
            store.close()

    def test_similar_cases_prioritize_same_problem_over_shared_generic_word(self):
        source = {
            "crm_id": "source", "ticket_number": "CAS-SOURCE",
            "title": "کندی جستجوی نامه", "description": "جستجوی نامه برای کاربران با تاخیر زیاد انجام می‌شود.",
            "service": "اتوماسیون اداری", "category": "Performance", "notes": [], "posts": [], "tasks": [],
            "knowledge_articles": [],
        }
        similar = {
            "crm_id": "similar", "ticket_number": "CAS-SIMILAR",
            "title": "تاخیر در جستجوی مکاتبات", "description": "عملکرد جستجوی نامه کند شده و پاسخ دیر برمی‌گردد.",
            "service": "اتوماسیون اداری", "category": "Performance", "notes": [{"note_text": "با اصلاح تنظیمات ایندکس مشکل برطرف شد."}],
            "posts": [], "tasks": [], "knowledge_articles": [],
        }
        unrelated = {
            "crm_id": "unrelated", "ticket_number": "CAS-UNRELATED",
            "title": "Workflow", "description": "کاربر مجوز اجرای Workflow را ندارد.",
            "service": "اتوماسیون اداری", "category": "Permission", "notes": [], "posts": [], "tasks": [],
            "knowledge_articles": [],
        }
        result = analyze_case(source, similar_cases=[source, similar, unrelated])
        self.assertTrue(result["similar_cases"])
        self.assertEqual(result["similar_cases"][0]["case_number"], "CAS-SIMILAR")
        self.assertTrue(result["similar_cases"][0]["resolved"])
        self.assertIn("برطرف شد", result["similar_cases"][0]["resolution"])
        self.assertTrue(result["similar_cases"][0]["reasons"])
        self.assertTrue(all(item["case_number"] != "CAS-UNRELATED" or item["similarity_score"] < result["similar_cases"][0]["similarity_score"] for item in result["similar_cases"]))

    def test_similar_cases_do_not_invent_resolution(self):
        source = {"crm_id": "source", "title": "خطای دسترسی", "description": "کاربر خطای مجوز دریافت می‌کند.", "notes": [], "posts": [], "tasks": [], "knowledge_articles": []}
        candidate = {"crm_id": "candidate", "ticket_number": "CAS-2", "title": "خطای مجوز کاربر", "description": "دسترسی کاربر به فرم ممکن نیست.", "notes": [], "posts": [], "tasks": [], "knowledge_articles": []}
        result = analyze_case(source, similar_cases=[source, candidate])
        self.assertTrue(result["similar_cases"])
        self.assertIsNone(result["similar_cases"][0]["resolution"])
        self.assertFalse(result["similar_cases"][0]["resolved"])

    def test_similarity_evaluation_reports_review_progress(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "review.json"
            path.write_text(json.dumps({
                "items": [
                    {"source_case_id": "a", "human_label": "similar"},
                    {"source_case_id": "a", "human_label": "not_similar"},
                    {"source_case_id": "b", "human_label": None},
                ]
            }), encoding="utf-8")
            report = evaluate(path)
            self.assertEqual(report["reviewed_pairs"], 2)
            self.assertEqual(report["pending_pairs"], 1)
            self.assertEqual(report["sources_with_review"], 1)
            self.assertEqual(report["precision_at_reviewed_candidates"], 0.5)


if __name__ == "__main__":
    unittest.main()
