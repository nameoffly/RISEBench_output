import os
import unittest
from unittest.mock import patch

import gpt_eval


class GptEvalEnvConfigTest(unittest.TestCase):
    def setUp(self):
        self._old_api_key = gpt_eval.api_key
        self._old_api_base = gpt_eval.api_base

    def tearDown(self):
        gpt_eval.api_key = self._old_api_key
        gpt_eval.api_base = self._old_api_base

    def test_normalize_api_base_appends_chat_completions(self):
        self.assertEqual(
            gpt_eval.normalize_api_base("https://api.example.com/v1"),
            "https://api.example.com/v1/chat/completions",
        )

    def test_normalize_api_base_keeps_full_chat_completions(self):
        self.assertEqual(
            gpt_eval.normalize_api_base("https://api.example.com/v1/chat/completions"),
            "https://api.example.com/v1/chat/completions",
        )

    def test_configure_api_reads_from_environment(self):
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "test-key",
                "OPENAI_BASE_URL": "https://api.example.com/v1",
            },
            clear=True,
        ):
            key, base = gpt_eval.configure_api(
                api_key_env="OPENAI_API_KEY", api_base=None
            )
        self.assertEqual(key, "test-key")
        self.assertEqual(base, "https://api.example.com/v1/chat/completions")
        self.assertEqual(gpt_eval.api_key, "test-key")
        self.assertEqual(gpt_eval.api_base, "https://api.example.com/v1/chat/completions")

    def test_configure_api_requires_api_key_env(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(SystemExit):
                gpt_eval.configure_api(
                    api_key_env="OPENAI_API_KEY",
                    api_base="https://api.example.com/v1",
                )


if __name__ == "__main__":
    unittest.main()
