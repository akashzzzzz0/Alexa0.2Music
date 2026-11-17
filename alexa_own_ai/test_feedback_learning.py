"""Tests for explicit, privacy-minimizing response feedback."""
import os
import tempfile
import unittest
from feedback_learning import record_feedback, feedback_guidance


class FeedbackLearningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.temp.name, "feedback.sqlite3")

    def tearDown(self):
        self.temp.cleanup()

    def test_repeated_explicit_feedback_becomes_guidance(self):
        event = {"category": "repetitive", "sentiment": "negative"}
        self.assertTrue(record_feedback(self.db, "user:1", event))
        self.assertTrue(record_feedback(self.db, "user:1", event))
        self.assertIn("avoid repeating", feedback_guidance(self.db, "user:1"))

    def test_feedback_isolated_by_scope(self):
        event = {"category": "wrong_language", "sentiment": "negative"}
        record_feedback(self.db, "user:1", event)
        self.assertEqual(feedback_guidance(self.db, "user:2"), "")

    def test_rejects_unapproved_categories_and_raw_text(self):
        self.assertFalse(record_feedback(self.db, "user:1", {
            "category": "store_everything", "sentiment": "negative",
            "message": "private content",
        }))
        self.assertFalse(record_feedback(self.db, "user:1", {
            "category": "misunderstood", "sentiment": "unknown",
        }))
        self.assertEqual(feedback_guidance(self.db, "user:1"), "")

    def test_one_signal_does_not_overfit(self):
        record_feedback(self.db, "user:1", {
            "category": "too_long", "sentiment": "negative",
        })
        self.assertEqual(feedback_guidance(self.db, "user:1"), "")


if __name__ == "__main__":
    unittest.main()
