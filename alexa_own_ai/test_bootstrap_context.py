"""Regression test for context forwarding through the service bootstrap wrapper."""
import unittest
from unittest.mock import patch

import bootstrap


class BootstrapContextTests(unittest.TestCase):
    def test_wrapper_forwards_context_to_original_runtime(self):
        supplied = {"leaderboard": [{"name": "Alexa", "rank": 1}]}
        with patch.object(bootstrap, "_original_messages", return_value=[
            {"role": "system", "content": "base"}
        ]) as original:
            result = bootstrap._alexa_messages("Who is first?", [], context=supplied)
        original.assert_called_once_with("Who is first?", [], context=supplied)
        self.assertIn("friendly, feminine", result[0]["content"])


if __name__ == "__main__":
    unittest.main()
