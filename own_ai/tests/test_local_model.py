import unittest
from unittest.mock import patch

from own_ai.local_model import LocalGGUFModel


class LocalModelConfigTests(unittest.TestCase):
    def test_local_model_defaults_to_public_qwen3_gguf(self):
        with patch.dict("os.environ", {}, clear=True):
            model = LocalGGUFModel()
            self.assertTrue(model.configured)
            self.assertEqual(model.repo_id, "Qwen/Qwen3-4B-GGUF")
            self.assertEqual(model.filename, "Qwen3-4B-Q4_K_M.gguf")
            self.assertFalse(model.loaded)

    def test_local_model_can_be_disabled(self):
        with patch.dict("os.environ", {"ALEXA_LOCAL_MODEL_ENABLED": "false"}, clear=True):
            self.assertFalse(LocalGGUFModel().configured)


if __name__ == "__main__":
    unittest.main()
