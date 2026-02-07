import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import translate_instructions as ti


class TranslateInstructionsLangSupportTest(unittest.TestCase):
    def test_new_target_languages_are_supported(self):
        expected = {
            "ru": "Russian",
            "bn": "Bengali",
            "ja": "Japanese",
            "he": "Hebrew",
            "yo": "Yoruba",
            "sw": "Swahili",
            "iu": "Inuktitut",
        }
        for code, name in expected.items():
            self.assertIn(code, ti.DEFAULT_LANGS)
            self.assertEqual(ti.DEFAULT_LANGS[code], name)

    def test_existing_default_cli_langs_are_unchanged(self):
        self.assertEqual(ti.parse_args.__name__, "parse_args")
        self.assertEqual(ti.DEFAULT_LANGS["zh"], "Simplified Chinese")
        self.assertEqual(ti.DEFAULT_LANGS["ar"], "Arabic")
        self.assertEqual(ti.DEFAULT_LANGS["es"], "Spanish")


class TranslateResumeTest(unittest.TestCase):
    def _write_source(self, path: Path):
        data = [
            {
                "index": f"sample_{i}",
                "category": "temporal_reasoning",
                "instruction": f"instruction {i}",
                "image": f"img_{i}.png",
                "reference": "ref",
                "subtask": "Life Progression",
            }
            for i in range(5)
        ]
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return data

    def test_resume_after_partial_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            src_path = tmp_path / "source.json"
            out_dir = tmp_path / "out"
            source_data = self._write_source(src_path)

            attempts = {"count": 0}

            def flaky_call(instructions, lang_name, model, base_url, api_key, timeout, max_retries):
                attempts["count"] += 1
                if attempts["count"] == 2:
                    raise RuntimeError("simulated timeout")
                return [f"{lang_name}:{x}" for x in instructions]

            with mock.patch.object(ti, "call_api_batch", side_effect=flaky_call):
                with self.assertRaises(RuntimeError):
                    ti.translate_dataset(
                        data_path=str(src_path),
                        out_dir=str(out_dir),
                        langs=["ru"],
                        model="m",
                        base_url="https://example.com/v1",
                        api_key="k",
                        batch_size=2,
                        timeout=1,
                        max_retries=1,
                        resume=True,
                        force_restart=False,
                    )

            progress_path = out_dir / ".translate_progress_source_ru.json"
            self.assertTrue(progress_path.exists())
            state = json.loads(progress_path.read_text(encoding="utf-8"))
            self.assertEqual(len(state["done_indices"]), 2)

            def ok_call(instructions, lang_name, model, base_url, api_key, timeout, max_retries):
                return [f"{lang_name}:{x}" for x in instructions]

            with mock.patch.object(ti, "call_api_batch", side_effect=ok_call):
                ti.translate_dataset(
                    data_path=str(src_path),
                    out_dir=str(out_dir),
                    langs=["ru"],
                    model="m",
                    base_url="https://example.com/v1",
                    api_key="k",
                    batch_size=2,
                    timeout=1,
                    max_retries=1,
                    resume=True,
                    force_restart=False,
                )

            output_path = out_dir / "source_ru.json"
            self.assertTrue(output_path.exists())
            self.assertFalse(progress_path.exists())
            out_data = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(len(out_data), len(source_data))
            self.assertTrue(all(item["instruction"].startswith("Russian:") for item in out_data))


if __name__ == "__main__":
    unittest.main()
