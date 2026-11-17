"""Tests for the optional hosted and self-hosted model adapters."""
import json
import os
import unittest
from unittest.mock import patch

import model_runtime


class FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit):
        return json.dumps({
            "choices": [{"message": {"role": "assistant", "content": "Haan, samajh gayi!"}}]
        }).encode("utf-8")


class ModelRuntimeTests(unittest.TestCase):
    def test_unconfigured_model_returns_none(self):
        env = {
            "ALEXA_LOCAL_MODEL_URL": "",
            "CLOUDFLARE_ACCOUNT_ID": "",
            "CLOUDFLARE_API_TOKEN": "",
        }
        with patch.dict(os.environ, env, clear=False):
            self.assertIsNone(model_runtime.generate("hello", []))

    def test_cloudflare_model_receives_context_and_returns_reply(self):
        class CloudflareResponse(FakeResponse):
            def read(self, limit):
                return json.dumps({
                    "success": True,
                    "result": {"response": "Haan, main samajh gayi."}
                }).encode("utf-8")

        env = {
            "CLOUDFLARE_ACCOUNT_ID": "account-test",
            "CLOUDFLARE_API_TOKEN": "cf-test-secret",
            "ALEXA_CLOUDFLARE_MODEL": "@cf/zai-org/glm-4.7-flash",
            "ALEXA_LOCAL_MODEL_URL": "",
        }
        with patch.dict(os.environ, env, clear=False), patch(
            "urllib.request.urlopen", return_value=CloudflareResponse()
        ) as mocked:
            reply = model_runtime.generate("Tum samajh rahi ho?", [
                {"role": "user", "content": "Alexa suno"},
                {"role": "assistant", "content": "Haan bolo"},
            ])
            self.assertEqual(model_runtime.status()["provider"], "cloudflare-workers-ai")
            self.assertEqual(model_runtime.status()["model"], "@cf/zai-org/glm-4.7-flash")
        self.assertEqual(reply, "Haan, main samajh gayi.")
        request = mocked.call_args.args[0]
        self.assertIn("/ai/run/@cf/zai-org/glm-4.7-flash", request.full_url)
        self.assertEqual(request.get_header("Authorization"), "Bearer cf-test-secret")
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["messages"][-1], {
            "role": "user", "content": "Tum samajh rahi ho?"
        })
        self.assertEqual(payload["max_completion_tokens"], 192)
        self.assertLessEqual(mocked.call_args.kwargs["timeout"], 8)

    def test_configured_model_receives_context_and_returns_reply(self):
        with patch.dict(os.environ, {
            "ALEXA_LOCAL_MODEL_URL": "http://127.0.0.1:8080/v1",
            "ALEXA_LOCAL_MODEL_NAME": "tiny-local",
            "ALEXA_LOCAL_MODEL_TOKEN": "test-secret",
        }, clear=False), patch("urllib.request.urlopen", return_value=FakeResponse()) as mocked:
            reply = model_runtime.generate("Tum pagal ho", [
                {"role": "user", "content": "Alexa, suno"},
                {"role": "assistant", "content": "Haan bolo"},
                {"role": "system", "content": "must not be forwarded"},
            ])
        self.assertEqual(reply, "Haan, samajh gayi!")
        request = mocked.call_args.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:8080/v1/chat/completions")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-secret")
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["model"], "tiny-local")
        self.assertEqual(payload["messages"][-1], {"role": "user", "content": "Tum pagal ho"})
        self.assertFalse(any(m["role"] == "system" and m["content"] == "must not be forwarded"
                             for m in payload["messages"]))

    def test_unavailable_model_falls_back_cleanly(self):
        with patch.dict(os.environ, {"ALEXA_LOCAL_MODEL_URL": "http://127.0.0.1:1/v1"}, clear=False):
            with patch("urllib.request.urlopen", side_effect=OSError("offline")):
                self.assertIsNone(model_runtime.generate("hello", []))


    def test_ai_building_statement_does_not_trigger_unsolicited_identity_or_vision_claim(self):
        message = "Ek AI main bhi bana ke dikhaunga"
        self.assertTrue(model_runtime._is_unprompted_meta_reply(
            message, "Haan main bhi AI hoon, ab mujhe dekh sakti ho."
        ))
        self.assertFalse(model_runtime._is_unprompted_meta_reply(
            message, "Achha! Phir dekhte hain tumhari AI kya kamaal karti hai 😄"
        ))

    def test_ai_identity_is_only_blocked_when_unsolicited(self):
        self.assertFalse(model_runtime._is_unprompted_meta_reply(
            "Tum kon ho?", "Main Alexa hoon, ek AI assistant."
        ))
        self.assertFalse(model_runtime._is_unprompted_meta_reply(
            "Are you AI?", "Yes, I am an AI language model."
        ))
        self.assertFalse(model_runtime._is_unprompted_meta_reply(
            "Tum kya ho?", "Main ek AI hoon aur tumhari help karti hoon."
        ))
        self.assertTrue(model_runtime._is_unprompted_meta_reply(
            "Aaj kya kar rahi ho?", "I'm an AI assistant and I'm here to help."
        ))
        self.assertFalse(model_runtime._is_unprompted_meta_reply(
            "Tum kon ho?", "Main Alexa hoon. Bolo, kya baat hai?"
        ))
        self.assertFalse(model_runtime._is_unprompted_meta_reply(
            "Kya tum mujhe dekh sakti ho?", "Nahi, mujhe yahan koi live visual nahi dikh raha."
        ))

    def test_total_latency_budget_skips_second_provider_when_time_is_exhausted(self):
        with patch.dict(os.environ, {
            "CLOUDFLARE_ACCOUNT_ID": "account-test",
            "CLOUDFLARE_API_TOKEN": "cf-test-secret",
            "ALEXA_LOCAL_MODEL_URL": "http://127.0.0.1:8080/v1",
        }, clear=False), patch(
            "model_runtime.time.monotonic", side_effect=[0.0, 0.0, 9.5]
        ), patch("model_runtime._cloudflare_generate", return_value=None), patch(
            "model_runtime._local_generate", return_value="should not run"
        ) as local:
            self.assertIsNone(model_runtime.generate("hello", []))
        local.assert_not_called()


    def test_model_context_keeps_more_recent_turns_and_truncates_oversized_messages(self):
        history = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": str(i) + ("x" * 1500)}
            for i in range(18)
        ]
        messages = model_runtime._messages("latest", history)
        self.assertEqual(len(messages), 16)
        self.assertEqual(messages[-2]["content"], "17" + ("x" * 1398))
        self.assertEqual(messages[-1]["content"], "latest")
        self.assertIn("latest relevant exchange", messages[0]["content"])
        self.assertIn("quoted or mentioned phrase", messages[0]["content"])


    def test_deep_understanding_prioritizes_user_corrections(self):
        cues = model_runtime.deep_understanding.analyze(
            "Nahi, mera matlab ye nahi tha", []
        )
        self.assertIn("message_act=correction_or_disagreement", cues)
        self.assertIn("acknowledge_correction_first", cues)

    def test_deep_understanding_detects_explicit_owner_relationship(self):
        cues = model_runtime.deep_understanding.analyze("Abe tera owner to mai hu naa", [])
        self.assertIn("message_act=owner_relationship_assertion", cues)
        self.assertIn("explicit_owner_relationship_statement=yes", cues)
        self.assertIn("without_claiming_it_authenticates_privileged_permissions", cues)

    def test_deep_understanding_links_short_answer_to_previous_question(self):
        history = [{"role": "assistant", "content": "Which part did you mean?"}]
        cues = model_runtime.deep_understanding.analyze("Wohi second wala", history)
        self.assertIn("message_act=answer_to_previous_question", cues)
        self.assertIn("previous_assistant_asked_question=yes", cues)

    def test_deep_understanding_reads_emoji_as_uncertain_contextual_cues(self):
        cues = model_runtime.deep_understanding.analyze("😂❤️", [])
        self.assertIn("amused_or_laughing", cues)
        self.assertIn("warm_or_appreciative", cues)
        self.assertIn("heuristic cues, not certainties", cues)

    def test_whole_message_analysis_detects_request_negation_and_contextual_constraints(self):
        cues = model_runtime.deep_understanding.analyze(
            "Nahi, pehle wala mat badalna. Sirf reply samajhne ka system improve karo.",
            [{"role": "assistant", "content": "Should I update the whole project?"}],
        )
        self.assertIn("message_act=correction_or_disagreement", cues)
        self.assertIn("contains_negation=yes", cues)
        self.assertIn("contains_possible_correction=yes", cues)

    def test_roman_urdu_multi_part_request_is_classified_as_request(self):
        cues = model_runtime.deep_understanding.analyze(
            "Mujhe ye kaam kar do, aur pehle se chalne wale features ko mat badalna.", []
        )
        self.assertIn("message_act=request", cues)
        self.assertIn("contains_request=yes", cues)
        self.assertIn("contains_negation=yes", cues)

    def test_urdu_and_devanagari_messages_are_counted_as_words(self):
        urdu = model_runtime.deep_understanding.analyze("آپ میری بات سمجھ رہے ہیں؟", [])
        hindi = model_runtime.deep_understanding.analyze("तुम मेरी बात समझ रहे हो?", [])
        self.assertIn("script_hint=urdu_or_arabic_script", urdu)
        self.assertIn("script_hint=devanagari_script", hindi)
        self.assertIn("word_count=6", urdu)
        self.assertIn("word_count=6", hindi)

    def test_prompt_requires_full_message_clause_and_constraint_handling(self):
        prompt = model_runtime._messages("Do this, but don't change anything else.", [])[0]["content"].lower()
        self.assertIn("every separate request or question", prompt)
        self.assertIn("conditions, negation, contrast", prompt)
        self.assertIn("preserve the earlier constraints", prompt)
        self.assertIn("do not answer only the first or last clause", prompt)

    def test_model_prompt_includes_deep_understanding_without_extra_turn(self):
        messages = model_runtime._messages(
            "Nahi, mera matlab kuch aur tha",
            [{"role": "assistant", "content": "So you agree?"}],
        )
        self.assertEqual(messages[0]["role"], "system")
        self.assertIn("message_act=correction_or_disagreement", messages[0]["content"])
        self.assertEqual(messages[-1]["content"], "Nahi, mera matlab kuch aur tha")

    def test_self_hosted_repeated_reply_is_rejected(self):
        history = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello, how can I help?"},
        ]
        with patch.dict(os.environ, {
            "CLOUDFLARE_ACCOUNT_ID": "",
            "CLOUDFLARE_API_TOKEN": "",
            "ALEXA_LOCAL_MODEL_URL": "http://127.0.0.1:8080/v1",
        }, clear=False), patch(
            "model_runtime._cloudflare_generate", return_value=None
        ), patch(
            "model_runtime._local_generate", return_value="Hello, how can I help?"
        ):
            self.assertIsNone(model_runtime.generate("Hi again", history))

if __name__ == "__main__":
    unittest.main()
