"""Regression tests for context-aware and non-repetitive chat prompting."""
import unittest

from model_runtime import _messages
from conversation_brain import respond


class ConversationQualityPromptTests(unittest.TestCase):

    def test_location_question_gets_direct_relevant_answer(self):
        cases = [
            ("Tum kis desh se ho?", "tum kis desh se ho", "ur"),
            ("Which country are you from?", "which country are you from", "en"),
            ("Tum kahan rehti ho?", "tum kahan rehti ho", "ur"),
        ]
        for raw, normalized, language in cases:
            with self.subTest(raw=raw):
                answer = respond(raw, normalized, language, [])
                self.assertIsNotNone(answer)
                self.assertIn("virtual assistant", answer.lower())
                self.assertNotIn("kitne log", answer.lower())
                self.assertNotIn("how many people", answer.lower())

    def test_prompt_requires_intent_and_reference_resolution(self):
        system = _messages("Woh kyun bola?", [
            {"role": "user", "content": "Maine usko mana kiya tha"},
            {"role": "assistant", "content": "Usne phir bhi message kiya?"},
        ])[0]["content"].lower()
        self.assertIn("message act", system)
        self.assertIn("pronoun", system)
        self.assertIn("recent turns", system)

    def test_prompt_discourages_repeated_stock_replies(self):
        system = _messages("Acha", [
            {"role": "assistant", "content": "Haan, batao kya hua?"}
        ])[0]["content"].lower()
        self.assertIn("do not repeat the same greeting", system)
        self.assertIn("generic loops", system)
        self.assertIn("new focused question", system)

    def test_prompt_treats_emoji_as_contextual_not_fixed(self):
        system = _messages("🙄😂", [])[0]["content"].lower()
        self.assertIn("emoji-only", system)
        self.assertIn("not fixed meanings", system)
        self.assertIn("context is insufficient", system)


if __name__ == "__main__":
    unittest.main()
