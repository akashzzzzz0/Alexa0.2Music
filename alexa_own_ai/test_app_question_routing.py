"""Regression tests for question-first and context-aware app routing."""
import unittest
from unittest.mock import patch

import app


class QuestionFirstRoutingTests(unittest.TestCase):
    def test_name_question_without_evidence_does_not_guess(self):
        reply = app.response_for("Mera name kya ha", [])
        self.assertIn("naam nahi bataya", reply.lower())

    def test_name_question_uses_explicit_recent_user_statement(self):
        history = [{"role": "user", "content": "Mera naam Akash hai"}]
        reply = app.response_for("Mera naam kya hai?", history)
        self.assertIn("Akash", reply)

    def test_substantive_question_reaches_model_before_keyword_fallback(self):
        with patch.object(app, "local_model_generate", return_value="Leaderboard mein Gautam first hai.") as generate:
            reply = app.response_for("Leaderboard par number one kon hai?", [])
        self.assertEqual(reply, "Leaderboard mein Gautam first hai.")
        generate.assert_called_once()

    def test_emotional_statement_reaches_model_instead_of_happy_template(self):
        message = "Mujhe leaderboard par first aane ki khushi hai"
        with patch.object(app, "local_model_generate", return_value="Wah, tumhari mehnat rang laayi!") as generate:
            reply = app.response_for(message, [])
        self.assertEqual(reply, "Wah, tumhari mehnat rang laayi!")
        generate.assert_called_once()

    def test_multi_question_turn_reaches_model_intact(self):
        message = "1. Tumhara naam kya hai? 2. Mera naam kya hai? 3. Kal wali baat yaad hai?"
        with patch.object(app, "local_model_generate", return_value="Teenon sawalon ke jawab...") as generate:
            reply = app.response_for(message, [])
        self.assertEqual(reply, "Teenon sawalon ke jawab...")
        generate.assert_called_once_with(message, [], context=None)


if __name__ == "__main__":
    unittest.main()
