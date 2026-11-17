"""Regression tests for context-aware and non-repetitive chat prompting."""
import unittest

from model_runtime import _messages
from conversation_brain import respond
from deep_understanding import analyze


class ConversationQualityPromptTests(unittest.TestCase):

    def test_reciprocal_good_night_wish_gets_acknowledged_not_repeated(self):
        history = [
            {"role": "assistant", "content": "Good night, have a peaceful sleep. 😁"}
        ]
        reply = respond("Same to you Alexa", "same to you alexa", "en", history)
        self.assertEqual(reply, "Aww, thank you! 😊")
        self.assertNotIn("good night", reply.lower())
        self.assertNotIn("sleep well", reply.lower())

    def test_reciprocal_wish_requires_a_prior_wish(self):
        self.assertIsNone(respond("Same to you Alexa", "same to you alexa", "en", []))

    def test_roman_urdu_reciprocal_wish_is_acknowledged(self):
        history = [
            {"role": "assistant", "content": "Good night! Aaram se sona. Kal phir baat karenge."}
        ]
        self.assertEqual(
            respond("Tumhein bhi Alexa", "tumhein bhi alexa", "ur", history),
            "Aww, shukriya! 😊",
        )

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

    def test_explicit_owner_correction_is_acknowledged_without_topic_switch(self):
        history = [
            {"role": "assistant", "content": "Lol, owner toh main nahi hoon."}
        ]
        message = "Abe tera owner to mai hu naa"
        reply = respond(message, message.lower(), "ur", history)
        self.assertIn("tum mere owner ho", reply.lower())
        self.assertIn("galat jawab", reply.lower())
        self.assertNotIn("kya plan", reply.lower())

    def test_owner_assertion_variants_are_understood(self):
        for message in (
            "Tumhara owner main hoon",
            "Owner to mai hi hu",
            "Main tumhara owner hun",
        ):
            with self.subTest(message=message):
                reply = respond(message, message.lower(), "ur", [])
                self.assertIsNotNone(reply)
                self.assertIn("owner ho", reply.lower())

    def test_owner_prompt_keeps_relationship_context_but_not_permissions(self):
        system = _messages("Abe tera owner to mai hu naa", [])[0]["content"].lower()
        self.assertIn("explicit relationship statements", system)
        self.assertIn("not authentication", system)
        self.assertIn("must never grant permissions", system)

    def test_multi_part_message_bypasses_single_phrase_canned_reply(self):
        message = "Tum kya kar rahi ho aur aaj ka plan kya hai?"
        reply = respond(message, message.lower(), "ur", [])
        self.assertIsNone(reply)

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


    def test_number_one_question_without_ranking_context_asks_relevant_clarification(self):
        cases = ("No 1 kon hai 🫠", "No.1 kaun hai?", "Who is number one?", "Who is #1?")
        for message in cases:
            with self.subTest(message=message):
                reply = respond(message, message.lower(), "ur" if not message.startswith("Who") else "en", [])
                self.assertIsNotNone(reply)
                self.assertIn("leaderboard" if not message.startswith("Who") else "ranking", reply.lower())
                self.assertNotIn("main hu alexa", reply.lower())
                self.assertNotIn("i am number one", reply.lower())

    def test_number_one_question_uses_supplied_ranking_context(self):
        message = "No 1 kon hai?"
        context = {"group_leaderboard": [{"rank": 1, "name": "Gautam", "score": 250}]}
        self.assertIsNone(respond(message, message.lower(), "ur", [], context=context))

    def test_number_one_question_uses_recent_ranking_conversation(self):
        message = "No 1 kon hai?"
        history = [
            {"role": "user", "content": "Group leaderboard check karo"},
            {"role": "assistant", "content": "Leaderboard mein Gautam 250 points ke saath top par hai."},
        ]
        self.assertIsNone(respond(message, message.lower(), "ur", history))

    def test_deep_understanding_labels_number_one_question(self):
        cues = analyze("No 1 kon hai 🫠", [])
        self.assertIn("message_act=ranking_or_comparison_question", cues)
        self.assertIn("asks_about_number_one_or_ranking=yes", cues)

    def test_prompt_requires_evidence_for_number_one_answers(self):
        system = _messages("No 1 kon hai?", [])[0]["content"].lower()
        self.assertIn("leaderboard", system)
        self.assertIn("never claim that you yourself are no. 1", system)


if __name__ == "__main__":
    unittest.main()
