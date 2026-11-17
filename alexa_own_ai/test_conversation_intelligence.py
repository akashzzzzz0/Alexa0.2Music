"""Tests for bounded multi-turn context summaries."""
import unittest
from conversation_intelligence import build_context_summary


class ConversationIntelligenceTests(unittest.TestCase):
    def test_summary_keeps_recent_turns_and_detects_references(self):
        history = [
            {"role": "user", "content": "Kal usne mujhe message kiya"},
            {"role": "assistant", "content": "Tumne kya jawab diya?"},
        ]
        result = build_context_summary("Wohi second wala", history)
        self.assertIn("user: Kal usne mujhe message kiya", result)
        self.assertIn("previous_assistant_question=yes", result)
        self.assertIn("contains_context_reference=yes", result)

    def test_summary_marks_correction_without_claiming_hidden_facts(self):
        result = build_context_summary("Nahi, mera matlab doosra tha", [])
        self.assertIn("contains_possible_correction=yes", result)
        self.assertIn("Do not invent missing participants", result)

    def test_summary_is_bounded(self):
        history = [{"role": "user", "content": "x" * 1000} for _ in range(30)]
        result = build_context_summary("latest", history)
        self.assertLess(len(result), 2500)
        self.assertLessEqual(result.count("user:"), 8)


if __name__ == "__main__":
    unittest.main()
