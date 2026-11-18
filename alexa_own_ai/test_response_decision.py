"""Tests for conservative response/reaction/silence decisions."""
import unittest
from response_decision import decide


class ResponseDecisionTests(unittest.TestCase):
    def test_private_chat_recommends_reply(self):
        self.assertEqual(decide("Hi")["action"], "reply")

    def test_addressed_group_message_recommends_reply(self):
        result = decide("Can you help?", {"is_group": True, "mentioned": True})
        self.assertEqual(result["action"], "reply")

    def test_bot_display_name_mention_recommends_reply(self):
        result = decide("Good morning Alexa", {
            "is_group": True, "bot_name_mentioned": True,
        })
        self.assertEqual(result["action"], "reply")

    def test_username_mention_recommends_reply(self):
        result = decide("Good morning @AlexaBot", {
            "is_group": True, "username_mentioned": True,
        })
        self.assertEqual(result["action"], "reply")

    def test_reply_to_alexas_message_recommends_reply(self):
        result = decide("Good morning", {
            "is_group": True, "reply_to_bot": True,
        })
        self.assertEqual(result["action"], "reply")

    def test_unaddressed_ordinary_group_message_recommends_silence(self):
        result = decide("Good morning everyone", {
            "is_group": True, "allow_reactions": True,
        })
        self.assertEqual(result["action"], "silence")

    def test_notable_message_can_recommend_one_contextual_reaction(self):
        result = decide("We won the final! 🎉", {
            "is_group": True, "allow_reactions": True,
        })
        self.assertEqual(result["action"], "react")
        self.assertEqual(result["reaction"], "🎉")

    def test_reactions_are_off_unless_caller_allows_them(self):
        result = decide("That was hilarious 😂", {"is_group": True})
        self.assertEqual(result["action"], "silence")
        self.assertIsNone(result["reaction"])


if __name__ == "__main__":
    unittest.main()
