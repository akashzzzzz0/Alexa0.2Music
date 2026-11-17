import os
import tempfile
import unittest
from unittest import mock

from alexa_own_ai import app, model_runtime


class AlexaOwnAIModelQualityTests(unittest.TestCase):
    def test_exact_previous_assistant_reply_is_rejected(self):
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "I'm here. What's up?"},
        ]
        self.assertTrue(model_runtime._is_repeated_reply(history, "  I'M HERE. What's up?! "))
        self.assertFalse(model_runtime._is_repeated_reply(history, "I'm listening. Go ahead."))

    def test_repeated_reply_guard_ignores_history_without_assistant_turn(self):
        self.assertFalse(model_runtime._is_repeated_reply(
            [{"role": "user", "content": "Hi"}], "Hi there"
        ))


class AlexaOwnAIDeepUnderstandingTests(unittest.TestCase):
    def test_correction_is_prioritized_over_generic_question_cues(self):
        cues = model_runtime.deep_understanding.analyze(
            "Nahi, mera matlab ye nahi tha", []
        )
        self.assertIn("message_act=correction_or_disagreement", cues)
        self.assertIn("acknowledge_correction_first", cues)

    def test_short_followup_is_linked_to_previous_assistant_question(self):
        history = [
            {"role": "assistant", "content": "Which part did you mean?"},
        ]
        cues = model_runtime.deep_understanding.analyze("Wohi second wala", history)
        self.assertIn("message_act=answer_to_previous_question", cues)
        self.assertIn("previous_assistant_asked_question=yes", cues)

    def test_emoji_cues_are_contextual_and_not_asserted_as_certain(self):
        cues = model_runtime.deep_understanding.analyze("😂❤️", [])
        self.assertIn("amused_or_laughing", cues)
        self.assertIn("warm_or_appreciative", cues)
        self.assertIn("heuristic cues, not certainties", cues)

    def test_model_messages_include_structured_understanding(self):
        messages = model_runtime._messages(
            "Nahi, mera matlab kuch aur tha",
            [{"role": "assistant", "content": "So you agree?"}],
        )
        analysis = messages[1]["content"]
        self.assertIn("message_act=correction_or_disagreement", analysis)
        self.assertEqual(messages[-1]["content"], "Nahi, mera matlab kuch aur tha")

    def test_self_hosted_model_repeated_reply_is_rejected(self):
        history = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello, how can I help?"},
        ]
        with mock.patch.dict(os.environ, {"ALEXA_LOCAL_MODEL_URL": "http://localhost:8000"}), \\
             mock.patch.object(model_runtime, "_cloudflare_generate", return_value=None), \\
             mock.patch.object(model_runtime, "_local_generate", return_value="Hello, how can I help?"):
            self.assertIsNone(model_runtime.generate("Hi again", history))


class AlexaOwnAILanguageTests(unittest.TestCase):
    def test_english_stays_english(self):
        self.assertEqual(app.detect_language("Hello, how are you?"), "en")
        self.assertIn("How", app.response_for("Hello", []))

    def test_roman_hindi_urdu_and_punjabi_style_share_roman_reply_mode(self):
        self.assertEqual(app.detect_language("Tussi ki haal aa veere?"), "ur")
        self.assertTrue(app.response_for("Ki haal aa?", []))
        self.assertFalse(any("\u0600" <= ch <= "\u06ff" for ch in app.response_for("Ki haal aa?", [])))

    def test_devanagari_input_gets_roman_reply(self):
        self.assertEqual(app.detect_language("नमस्ते"), "hi")
        reply = app.response_for("नमस्ते", [])
        self.assertFalse(any("\u0900" <= ch <= "\u097f" for ch in reply))

    def test_urdu_script_gets_roman_reply(self):
        self.assertEqual(app.detect_language("السلام علیکم"), "ur")
        reply = app.response_for("السلام علیکم", [])
        self.assertFalse(any("\u0600" <= ch <= "\u06ff" for ch in reply))

    def test_roman_hindi_detection(self):
        self.assertEqual(app.detect_language("Tum kya kar rahe ho?"), "ur")

    def test_urdu_question_is_transliterated_and_answered_in_roman(self):
        reply = app.response_for("آپ کیسے ہیں؟", [])
        self.assertIn("Main theek hoon", reply)
        self.assertFalse(any("\u0600" <= ch <= "\u06ff" for ch in reply))


    def test_common_alexa_calls_and_roman_urdu_variants_always_get_replies(self):
        examples = {
            "Hello Alexa baby": ("Hey", "What's up"),
            "Oyy Alexa baby": ("Haan bolo", "Oyyyy"),
            "Bool lyy": ("bolo", "sun rahi"),
            "Bol le": ("bolo", "sun rahi"),
            "Suno Alexa": ("sun rahi", "listening"),
        }
        for message, expected_parts in examples.items():
            with self.subTest(message=message):
                reply = app.response_for(message, [])
                self.assertTrue(reply.strip())
                self.assertTrue(any(part.casefold() in reply.casefold() for part in expected_parts), reply)


    def test_natural_short_chat_turns_do_not_repeat_generic_fallback(self):
        self.assertIn("kya baat", app.response_for("Baby", []).lower())
        self.assertIn("dil mein", app.response_for("Axha Kya du", []).lower())
        history = [
            {"role": "user", "content": "Baby"},
            {"role": "assistant", "content": "Haan, main sun rahi hoon. Thora aur context de do taake main sahi jawab de sakun."},
        ]
        reply = app.response_for("Hain", history)
        self.assertIn("normal baat", reply.lower())
        self.assertNotIn("thora aur context", reply.lower())

    def test_unknown_reply_is_not_the_old_repeated_fallback(self):
        reply = app.response_for("Aaj kuch ajeeb hua", [])
        self.assertNotIn("thora aur context", reply.lower())

    def test_contextual_followups_are_sent_to_model_instead_of_generic_fallback(self):
        history = [
            {"role": "user", "content": "Oyee baat sun"},
            {"role": "assistant", "content": "Haan bolo, kya baat hai?"},
            {"role": "user", "content": "Bohat buri baat hai"},
            {"role": "assistant", "content": "Kya hua? Izzat lagna shuru ho gayi?"},
        ]
        with mock.patch.object(app, "local_model_generate", return_value="Kya hua? Kis baat par keh rahe ho?") as model:
            reply = app.response_for("Mtlb?", history)
        self.assertEqual(reply, "Kya hua? Kis baat par keh rahe ho?")
        model.assert_called_once()
        self.assertEqual(model.call_args.args[0], "Mtlb?")
        self.assertEqual(model.call_args.args[1], history)

    def test_freeform_message_after_generic_assistant_prompt_reaches_model(self):
        history = [
            {"role": "assistant", "content": "Koi masla nahi, apne alfaaz mein batao. Main samajhne ki koshish kar rahi hoon."}
        ]
        with unittest.mock.patch.object(app, "local_model_generate", return_value="Haan, bolo. Main sun rahi hoon.") as model:
            reply = app.response_for("Oyee baat sun", history)
        self.assertEqual(reply, "Haan, bolo. Main sun rahi hoon.")
        model.assert_called_once()

    def test_unknown_message_gets_a_nonempty_clarification(self):
        for message in ("Aaj kuch ajeeb hua", "Tell me something unusual", "Mujhe samajh nahi aa raha"):
            with self.subTest(message=message):
                self.assertTrue(app.response_for(message, []).strip())

    def test_requested_casual_conversation_is_understood_with_context(self):
        first = "Ha sab Thek Chall Raha kha thii tum"
        self.assertIn("tum sunao", app.response_for(first, []).lower())
        history = [
            {"role": "user", "content": first},
            {"role": "assistant", "content": "Haan, main sun rahi hoon. Zara doosre alfaaz mein samjha do?"},
        ]
        second = app.response_for("Kis ilfaz me Samjhy ?", history)
        self.assertIn("meri galti", second.lower())
        history.extend([
            {"role": "user", "content": "Kis ilfaz me Samjhy ?"},
            {"role": "assistant", "content": second},
        ])
        self.assertIn("kya hua", app.response_for("Are yaar", history).lower())

    def test_english_input_gets_english_and_roman_input_gets_roman(self):
        self.assertEqual(app.detect_language("What are you doing today?"), "en")
        self.assertIn("I'm", app.response_for("How are you?", []))
        roman_reply = app.response_for("Tum kaisi ho?", [])
        self.assertFalse(any("\u0600" <= ch <= "\u06ff" for ch in roman_reply))
        self.assertFalse(any("\u0900" <= ch <= "\u097f" for ch in roman_reply))

class AlexaOwnAIMemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.previous_db_path = app.DB_PATH
        app.DB_PATH = os.path.join(self.tmp.name, "memory.sqlite3")

    def tearDown(self):
        app.DB_PATH = self.previous_db_path
        self.tmp.cleanup()

    def test_memory_is_separate_and_limited_to_last_twenty_messages(self):
        for index in range(12):
            app.save_turns("chat-a:user-1", f"user-{index}", f"assistant-{index}")
        history = app.get_history("chat-a:user-1", [])
        self.assertEqual(len(history), 20)
        self.assertEqual(history[-1]["content"], "assistant-11")
        self.assertEqual(app.get_history("chat-b:user-1", []), [])

    def test_dialogue_brain_handles_followups_and_natural_chat(self):
        cases = [
            ("Tum batao", "theek hoon"),
            ("Kya matlab?", "normally baat karo"),
            ("Kuch nahi", "aise hi baat karte hain"),
            ("Tumhe kya lagta hai?", "sabse zaroori kya hai"),
            ("Tum naraz ho?", "feelings nahi hoti"),
        ]
        for message, expected in cases:
            with self.subTest(message=message):
                self.assertIn(expected, app.response_for(message, []).lower())

    def test_contextual_yes_and_continue(self):
        history = [
            {"role": "user", "content": "Aaj school mein ek interesting baat hui"},
            {"role": "assistant", "content": "Achha, phir kya hua?"},
        ]
        self.assertIn("phir kya hua", app.response_for("Haan", history).lower())
        self.assertIn("main sun rahi hoon", app.response_for("Aur", history).lower())

    def test_caller_history_restores_context_when_service_database_is_empty(self):
        supplied = [
            {"role": "user", "content": "We were talking about a school project"},
            {"role": "assistant", "content": "Right, the science project."},
            {"role": "user", "content": "Why is it important?"},
        ]
        history = app.get_history("fresh-chat:user-2", supplied, "Why is it important?")
        self.assertEqual(len(history), 2)
        self.assertEqual(history[-1]["content"], "Right, the science project.")
        self.assertNotEqual(history[-1]["content"], "Why is it important?")


if __name__ == "__main__":
    unittest.main()
