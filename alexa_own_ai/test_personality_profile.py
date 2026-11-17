"""Tests for consistent, non-deceptive Alexa response style."""
import unittest
from personality_profile import build_guidance


class PersonalityProfileTests(unittest.TestCase):
    def test_guidance_preserves_feminine_roman_urdu_voice(self):
        value = build_guidance().lower()
        self.assertIn("samajh sakti hoon", value)
        self.assertIn("kar rahi hoon", value)

    def test_guidance_avoids_fake_human_claims_and_forced_replies(self):
        value = build_guidance().lower()
        self.assertIn("do not claim human", value)
        self.assertIn("repeated", value)
        self.assertIn("factual accuracy", value)


if __name__ == "__main__":
    unittest.main()
