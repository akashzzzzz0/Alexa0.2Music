"""Tests for the optional self-hosted model adapter."""
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
        with patch.dict(os.environ, {"ALEXA_LOCAL_MODEL_URL": ""}, clear=False):
            self.assertIsNone(model_runtime.generate("hello", []))

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


if __name__ == "__main__":
    unittest.main()
