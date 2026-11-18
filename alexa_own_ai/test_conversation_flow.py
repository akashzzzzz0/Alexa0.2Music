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


class InferenceFlowTests(unittest.TestCase):
    def test_open_chat_uses_exactly_one_context_aware_model_call(self):
        context = {"source": "test"}
        with patch.object(app, "conversation_respond", return_value=None), patch.object(
            app, "local_model_generate", return_value="Context-aware answer"
        ) as model:
            reply = app.response_for("A complete ordinary request", [], context=context)
        self.assertEqual(reply, "Context-aware answer")
        model.assert_called_once_with("A complete ordinary request", [], context=context)

    def test_deterministic_greeting_does_not_call_the_model(self):
        with patch.object(app, "conversation_respond", return_value=None), patch.object(
            app, "local_model_generate"
        ) as model:
            reply = app.response_for("hello", [])
        self.assertEqual(reply, app.REPLIES["en"]["hello"])
        model.assert_not_called()



if __name__ == "__main__":
    unittest.main()
