"""Regression tests for context-aware and non-repetitive chat prompting."""
import unittest

from model_runtime import _messages
from conversation_brain import respond
from deep_understanding import analyze


class ConversationQualityPromptTests(unittest.TestCase):





    def test_prompt_requires_intent_and_reference_resolution(self):
        system = _messages("Woh kyun bola?", [
            {"role": "user", "content": "Maine usko mana kiya tha"},
            {"role": "assistant", "content": "Usne phir bhi message kiya?"},
        ])[0]["content"].lower()
        self.assertIn("message act", system)
        self.assertIn("pronoun", system)
        self.assertIn("recent turns", system)



    def test_owner_prompt_keeps_relationship_context_but_not_permissions(self):
        system = _messages("Abe tera owner to mai hu naa", [])[0]["content"].lower()
        self.assertIn("explicit relationship statements", system)
        self.assertIn("not authentication", system)
        self.assertIn("must never grant permissions", system)

    def test_good_morning_gets_a_matching_greeting_not_an_unrelated_hello(self):
        reply = respond("Good morning Alexa", "good morning alexa", "en", [])
        self.assertTrue(reply.startswith("Good morning!"))
        self.assertNotIn("Hellooo", reply)

    def test_roman_urdu_good_morning_gets_a_natural_matching_reply(self):
        reply = respond("Good morning", "good morning", "ur", [])
        self.assertTrue(reply.startswith("Good morning!"))
        self.assertIn("subah", reply.lower())

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

    def test_normal_chat_is_routed_to_model_not_canned_local_dialogue(self):
        cases = [
            ("Same to you Alexa", "same to you alexa", "en"),
            ("Haan", "haan", "ur"),
            ("Tum kya kar rahi ho?", "tum kya kar rahi ho", "ur"),
            ("Arre haan, samajh gaya. Uski leadership strong hai.", "arre haan samajh gaya uski leadership strong hai", "ur"),
            ("🙄😂", "🙄😂", "ur"),
        ]
        for raw, normalized, language in cases:
            with self.subTest(raw=raw):
                self.assertIsNone(respond(raw, normalized, language, []))

    def test_model_prompt_requires_fresh_non_stock_replies(self):
        system = _messages("Same to you", [
            {"role": "assistant", "content": "Good night, sleep well."}
        ])[0]["content"].lower()
        self.assertIn("do not use canned dialogue", system)
        self.assertIn("fresh, natural response", system)
        self.assertIn("do not reply merely because a message arrived", system)

    def test_deep_understanding_detects_contextual_praise_and_agreement(self):
        cues = analyze(
            "Haan, uski strong leadership ki wajah se woh sabse upar hai.",
            [{"role": "assistant", "content": "Woh top par kyun hai?"}],
        ).lower()
        self.assertIn("leadership_or_ability_praise=yes", cues)
        self.assertIn("agreement_or_confirmation=yes", cues)

    def test_emoji_cues_remain_uncertain_and_contextual(self):
        cues = analyze("🙄💀", []).lower()
        self.assertIn("sarcasm_or_disbelief_possible", cues)
        self.assertIn("hints only", cues)


if __name__ == "__main__":
    unittest.main()
