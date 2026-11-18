"""Regression tests for contextual replies and single-pass inference."""
import unittest
from unittest.mock import patch

import app
from conversation_brain import respond


class ConversationBrainTests(unittest.TestCase):
    def test_yes_continues_the_help_offer(self):
        history = [
            {"role": "assistant", "content": "I'm Alexa, your friendly assistant. What can I help you with?"}
        ]
        self.assertEqual(
            respond("Yes", "yes", "en", history),
            "Sure—what would you like help with?",
        )

    def test_girlfriend_request_gets_a_relevant_reply(self):
        reply = respond("Girl friend chahiye dila do", "girl friend chahiye dila do", "ur", [])
        self.assertIn("kisi ko arrange nahi kar sakti", reply)
        self.assertIn("respectfully", reply)


class EndToEndConversationTests(unittest.TestCase):
    def test_sample_yes_then_girlfriend_request_stays_contextual(self):
        history = [
            {"role": "assistant", "content": "I'm Alexa, your friendly assistant. What can I help you with?"},
            {"role": "user", "content": "Yes"},
        ]
        with patch.object(app, "local_model_generate") as model:
            first = app.response_for("Yes", history[:-1])
            second = app.response_for("Girl friend chahiye dila do", history)
        self.assertEqual(first, "Sure—what would you like help with?")
        self.assertIn("kisi ko arrange nahi kar sakti", second)
        self.assertNotIn("I'm listening", second)
        model.assert_not_called()

    def test_roman_urdu_request_is_not_misclassified_by_the_word_do(self):
        self.assertEqual(app.detect_language("Girl friend chahiye dila do"), "ur")

    def test_relationship_request_without_english_keyword(self):
        reply = respond("Mujhe kisi se dosti shuru karni hai", "mujhe kisi se dosti shuru karni hai", "ur", [])
        self.assertIsNone(reply)


class LanguageDetectionTests(unittest.TestCase):
    def test_english_yes_and_no_are_detected_as_english(self):
        self.assertEqual(app.detect_language("Yes"), "en")
        self.assertEqual(app.detect_language("No"), "en")

    def test_roman_urdu_dominates_one_english_word(self):
        self.assertEqual(
            app.detect_language("Mujhe batao what happened"),
            "ur",
        )

    def test_english_sentence_is_not_misclassified_by_generic_tokens(self):
        self.assertEqual(app.detect_language("I am here to help you"), "en")

    def test_roman_urdu_sentence_remains_roman_urdu(self):
        self.assertEqual(app.detect_language("Tum kya kar rahi ho?"), "ur")


class InferenceFlowTests(unittest.TestCase):
    def test_open_chat_uses_exactly_one_context_aware_model_call(self):
        context = {"source": "test"}
        with patch.object(app, "conversation_respond", return_value=None), patch.object(
            app, "local_model_generate", return_value="Context-aware answer"
        ) as model:
            reply = app.response_for("A complete ordinary request", [], context=context)
        self.assertEqual(reply, "Context-aware answer")
        model.assert_called_once_with("A complete ordinary request", [], context=context)

    def test_yes_after_a_specific_question_reaches_contextual_model(self):
        history = [{"role": "assistant", "content": "Would you like me to explain the result?"}]
        with patch.object(app, "local_model_generate", return_value="Sure, here's the explanation.") as model:
            reply = app.response_for("Yes", history)
        self.assertEqual(reply, "Sure, here's the explanation.")
        model.assert_called_once()

    def test_no_after_a_specific_question_reaches_contextual_model(self):
        history = [{"role": "assistant", "content": "Would you like me to explain the result?"}]
        with patch.object(app, "local_model_generate", return_value="No problem.") as model:
            reply = app.response_for("No", history)
        self.assertEqual(reply, "No problem.")
        model.assert_called_once()

    def test_compound_message_reaches_model_before_single_intent_fallbacks(self):
        message = "Tum kya kar rahi ho aur aaj ka plan kya hai?"
        with patch.object(app, "conversation_respond", return_value=None), patch.object(
            app, "local_model_generate", return_value="I'm chatting now, and my plan is to help you."
        ) as model:
            reply = app.response_for(message, [])
        self.assertEqual(reply, "I'm chatting now, and my plan is to help you.")
        model.assert_called_once_with(message, [], context=None)

    def test_deterministic_greeting_does_not_call_the_model(self):
        with patch.object(app, "conversation_respond", return_value=None), patch.object(
            app, "local_model_generate"
        ) as model:
            reply = app.response_for("hello", [])
        self.assertEqual(reply, app.REPLIES["en"]["hello"])
        model.assert_not_called()



if __name__ == "__main__":
    unittest.main()
