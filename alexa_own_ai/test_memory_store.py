"""Regression tests for scoped, explicit long-term Own AI memory."""
import os
import tempfile
import unittest

import app


class LongTermMemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = app.DB_PATH
        app.DB_PATH = os.path.join(self.temp_dir.name, "memory-test.sqlite3")

    def tearDown(self):
        app.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_memory_persists_and_is_isolated_by_scope(self):
        result = app.save_memory_items(
            "chat:10:user:22",
            {"preferred_language": "Roman Urdu", "reply_style": "short"},
        )
        self.assertEqual(result["saved"], 2)
        self.assertEqual(app.get_memory_items("chat:10:user:22")["preferred_language"], "Roman Urdu")
        self.assertEqual(app.get_memory_items("chat:10:user:23"), {})

    def test_updates_overwrite_and_forget_selected_key(self):
        app.save_memory_items("user:7", {"city": "Lahore", "style": "concise"})
        result = app.save_memory_items(
            "user:7",
            {"city": "Bahawalpur"},
            forget_keys=["style"],
        )
        self.assertEqual(result["saved"], 1)
        self.assertEqual(result["deleted"], 1)
        self.assertEqual(app.get_memory_items("user:7"), {"city": "Bahawalpur"})

    def test_forget_all_clears_only_the_selected_scope(self):
        app.save_memory_items("user:1", {"language": "Urdu"})
        app.save_memory_items("user:2", {"language": "English"})
        result = app.save_memory_items("user:1", forget_all=True)
        self.assertEqual(result["deleted"], 1)
        self.assertEqual(app.get_memory_items("user:1"), {})
        self.assertEqual(app.get_memory_items("user:2"), {"language": "English"})

    def test_rejects_credentials_and_non_scalar_values(self):
        app.save_memory_items("user:3", {
            "password": "do-not-store",
            "api_key": "do-not-store",
            "preferences": {"nested": "object"},
            "favorite_topic": "technology",
        })
        self.assertEqual(app.get_memory_items("user:3"), {"favorite_topic": "technology"})

    def test_request_context_includes_saved_memory_and_reports_changes(self):
        context, change, count = app.request_context({
            "memory_updates": {"reply_language": "Roman Urdu"},
            "context": {"group": "Study group"},
        }, "user:4")
        self.assertEqual(change["saved"], 1)
        self.assertEqual(count, 1)
        self.assertIn("relevant_memory", context)
        self.assertIn("saved_memory", context["relevant_memory"])
        self.assertEqual(context["relevant_memory"]["saved_memory"]["reply_language"], "Roman Urdu")
        self.assertIn("application_facts", context)


if __name__ == "__main__":
    unittest.main()
