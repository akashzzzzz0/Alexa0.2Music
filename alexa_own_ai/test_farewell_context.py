"""Regression tests for contextual farewell and good-night messages."""
import unittest

from conversation_brain import respond


class FarewellContextTests(unittest.TestCase):
    def test_goodnight_with_tomorrow_plan_is_natural_signoff(self):
        reply = respond(
            "Hmm Good night then we'll meet tomorrow okay",
            "hmm good night then we'll meet tomorrow okay",
            "en",
            [
                {"role": "user", "content": "Time kya ho raha hai?"},
                {"role": "assistant", "content": "It is 09:07 PM IST."},
            ],
        )
        self.assertEqual(
            reply,
            "Good night! Sleep well. We'll talk tomorrow. Take care! 😊",
        )

    def test_roman_urdu_goodnight_is_answered_in_roman_script(self):
        reply = respond(
            "Good night, kal baat karte hain",
            "good night kal baat karte hain",
            "ur",
            [],
        )
        self.assertIn("Kal phir baat karenge", reply)

    def test_unrelated_tomorrow_question_is_not_mistaken_for_signoff(self):
        reply = respond("What are we doing tomorrow?", "what are we doing tomorrow", "en", [])
        self.assertIsNone(reply)

    def test_kal_wali_baat_question_is_not_mistaken_for_signoff(self):
        message = (
            "Alexa, mujhe apna system test karna hai. "
            "Agar main kahun kal wali baat yaad hai toh bina context ke invent mat karna."
        )
        reply = respond(message, message.casefold(), "ur", [])
        self.assertIsNone(reply)


if __name__ == "__main__":
    unittest.main()
