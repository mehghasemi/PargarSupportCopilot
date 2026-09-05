import unittest
import tempfile
from pathlib import Path

from crm.analyzer import analyze_case, search_knowledge_articles
from crm.local_store import LocalStore


class AnalyzerTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
