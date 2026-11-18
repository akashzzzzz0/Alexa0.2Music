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
    def test_bootstrapped_router_does_not_trigger_a_second_model_call(self):
        with patch.object(app, "CONVERSATION_ROUTER_OWNS_INFERENCE", True), patch.object(
            app, "conversation_respond", return_value=None
        ), patch.object(app, "local_model_generate") as model:
            reply = app.response_for("A complete ordinary request", [], context={"source": "test"})
        model.assert_not_called()
        self.assertTrue(reply)

    def test_direct_app_mode_keeps_one_context_aware_model_fallback(self):
        context = {"source": "test"}
        with patch.object(app, "CONVERSATION_ROUTER_OWNS_INFERENCE", False), patch.object(
            app, "conversation_respond", return_value=None
        ), patch.object(app, "local_model_generate", return_value="Context-aware answer") as model:
            reply = app.response_for("A complete ordinary request", [], context=context)
        self.assertEqual(reply, "Context-aware answer")
        model.assert_called_once_with("A complete ordinary request", [], context=context)


if __name__ == "__main__":
    unittest.main()
