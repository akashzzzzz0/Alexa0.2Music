import unittest

from alexa_own_ai import model_runtime


class AlexaPersonaGuardTests(unittest.TestCase):
    def test_unasked_ai_disclosure_is_rejected(self):
        answer = "Technically, main Alexa hoon. Main AI hoon jo help ke liye design ki gayi hai."
        self.assertTrue(model_runtime._is_unprompted_meta_reply("Oyee baat sun", answer))

    def test_identity_answer_is_allowed_when_user_asks(self):
        answer = "Main Alexa hoon, ek AI assistant."
        self.assertFalse(model_runtime._is_unprompted_meta_reply("Tum kaun ho?", answer))

    def test_unasked_time_promise_is_rejected(self):
        answer = "Okay, main tumhe exact time de deti hoon."
        self.assertTrue(model_runtime._is_unprompted_meta_reply("Kya kar rahi ho?", answer))

    def test_time_answer_is_allowed_when_user_asks(self):
        answer = "The current time is 10:30."
        self.assertFalse(model_runtime._is_unprompted_meta_reply("What time is it?", answer))

    def test_dismissive_filler_is_rejected(self):
        self.assertTrue(model_runtime._is_unprompted_meta_reply(
            "Baat suno", "Okay, chill. Main sun rahi hoon."
        ))

    def test_normal_conversational_answer_is_kept(self):
        self.assertFalse(model_runtime._is_unprompted_meta_reply(
            "Oyee baat sun", "Haan bolo, kya baat hai?"
        ))

    def test_system_prompt_enforces_feminine_roman_urdu_persona(self):
        prompt = model_runtime._messages("Kya kar rahi ho?", [])[0]["content"].lower()
        self.assertIn("feminine", prompt)
        self.assertIn("de deti hoon", prompt)
        self.assertIn("do not announce that you are an ai", prompt)


if __name__ == "__main__":
    unittest.main()
