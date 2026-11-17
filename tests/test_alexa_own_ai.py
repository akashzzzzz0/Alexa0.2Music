import os
import tempfile
import unittest

from alexa_own_ai import app


class AlexaOwnAILanguageTests(unittest.TestCase):
    def test_english_stays_english(self):
        self.assertEqual(app.detect_language("Hello, how are you?"), "en")
        self.assertIn("How", app.response_for("Hello", []))

    def test_roman_punjabi_is_detected(self):
        self.assertEqual(app.detect_language("Tussi ki haal aa veere?"), "pa")
        self.assertIn("Oye", app.response_for("Ki haal aa?", []))

    def test_devanagari_input_gets_roman_reply(self):
        self.assertEqual(app.detect_language("नमस्ते"), "hi")
        reply = app.response_for("नमस्ते", [])
        self.assertFalse(any("\u0900" <= ch <= "\u097f" for ch in reply))

    def test_urdu_script_gets_roman_reply(self):
        self.assertEqual(app.detect_language("السلام علیکم"), "ur")
        reply = app.response_for("السلام علیکم", [])
        self.assertFalse(any("\u0600" <= ch <= "\u06ff" for ch in reply))

    def test_roman_hindi_detection(self):
        self.assertEqual(app.detect_language("Tum kya kar rahe ho?"), "hi")

    def test_urdu_question_is_transliterated_and_answered_in_roman(self):
        reply = app.response_for("آپ کیسے ہیں؟", [])
        self.assertIn("Main theek hoon", reply)
        self.assertFalse(any("\\u0600" <= ch <= "\\u06ff" for ch in reply))


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

    def test_unknown_message_gets_a_nonempty_clarification(self):
        for message in ("Aaj kuch ajeeb hua", "Tell me something unusual", "Mujhe samajh nahi aa raha"):
            with self.subTest(message=message):
                self.assertTrue(app.response_for(message, []).strip())

class AlexaOwnAIMemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.previous_db_path = app.DB_PATH
        app.DB_PATH = os.path.join(self.tmp.name, "memory.sqlite3")

    def tearDown(self):
        app.DB_PATH = self.previous_db_path
        self.tmp.cleanup()

    def test_memory_is_separate_and_limited_to_last_five_messages(self):
        for index in range(4):
            app.save_turns("chat-a:user-1", f"user-{index}", f"assistant-{index}")
        history = app.get_history("chat-a:user-1", [])
        self.assertEqual(len(history), 5)
        self.assertEqual(history[-1]["content"], "assistant-3")
        self.assertEqual(app.get_history("chat-b:user-1", []), [])

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
