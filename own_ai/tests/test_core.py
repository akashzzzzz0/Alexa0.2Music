import os
import tempfile
import unittest
from own_ai.language import detect_language
from own_ai.understanding import understand
from own_ai.memory import ConversationMemory
from own_ai.learning import FeedbackLearning

class CoreTests(unittest.TestCase):
    def test_languages(self):
        self.assertEqual(detect_language("آپ کیسے ہیں؟"), "ur")
        self.assertEqual(detect_language("Tum kaise ho"), "roman_urdu")
        self.assertEqual(detect_language("How are you?"), "en")
    def test_intents(self):
        self.assertEqual(understand("hello")["intent"], "greeting")
        self.assertEqual(understand("shukriya")["intent"], "thanks")
        self.assertEqual(understand("What time is it?")["intent"], "question")
    def test_memory_persists_and_isolates_conversations(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "memory.sqlite")
            memory = ConversationMemory(db_path=path)
            memory.add("one", "user", "hello")
            memory.add("two", "user", "separate")
            self.assertEqual(memory.get("one")[0]["content"], "hello")
            self.assertEqual(len(ConversationMemory(db_path=path).get("one")), 1)
    def test_feedback_persists(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "feedback.sqlite")
            FeedbackLearning(path).record("user-1", "concise")
            self.assertEqual(FeedbackLearning(path).preferences("user-1"), {"concise": 1})

if __name__ == "__main__":
    unittest.main()
