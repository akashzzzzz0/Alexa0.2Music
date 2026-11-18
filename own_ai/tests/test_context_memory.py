import asyncio
import os
import tempfile
import unittest
from unittest.mock import patch

from own_ai.chat import AlexaAI
from own_ai.memory import ConversationMemory
from own_ai.understanding import extract_name, understand

class ContextMemoryTests(unittest.TestCase):
    def test_explicit_name_extraction_does_not_capture_instruction(self):
        self.assertEqual(extract_name("Mera name Akash Yaad rkhna"), "Akash")
        self.assertEqual(extract_name("My name is Akash"), "Akash")
        self.assertIsNone(extract_name("Mera name kya ha"))

    def test_direct_address_is_a_greeting(self):
        parsed = understand("Alexa baby")
        self.assertEqual(parsed["intent"], "greeting")
        self.assertTrue(parsed["address_only"])

    def test_followup_intents(self):
        self.assertEqual(understand("Mera name kya ha")["intent"], "name_recall")
        self.assertEqual(understand("Kese yaad ha")["intent"], "memory_reason")

    def test_profile_persists_and_is_user_scoped(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "memory.sqlite")
            memory = ConversationMemory(db_path=path)
            memory.save_name("user-1", "Akash")
            reopened = ConversationMemory(db_path=path)
            self.assertEqual(reopened.get_name("user-1"), "Akash")
            self.assertIsNone(reopened.get_name("user-2"))

    def test_chat_saves_and_answers_name_followups(self):
        with tempfile.TemporaryDirectory() as directory:
            env = {
                "ALEXA_AI_MEMORY_DB": os.path.join(directory, "memory.sqlite"),
                "ALEXA_AI_LEARNING_DB": os.path.join(directory, "learning.sqlite"),
            }
            with patch.dict(os.environ, env):
                ai = AlexaAI()
                async def scenario():
                    await ai.chat("Mera name Akash Yaad rkhna", "chat-1", "user-1")
                    recall = await ai.chat("Mera name kya ha", "chat-1", "user-1")
                    reason = await ai.chat("Kese yaad ha", "chat-1", "user-1")
                    return recall, reason
                recall, reason = asyncio.run(scenario())
                self.assertIn("Akash", recall["reply"])
                self.assertIn("profile memory", reason["reply"])

if __name__ == "__main__":
    unittest.main()
