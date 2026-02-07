import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import upload_to_hf


class UploadToHfTest(unittest.TestCase):
    def test_default_path_in_repo_uses_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "outputs.zip"
            file_path.write_bytes(b"123")
            self.assertEqual(
                upload_to_hf.resolve_path_in_repo(str(file_path), None),
                "outputs.zip",
            )

    def test_upload_file_calls_hf_api(self):
        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "outputs.zip"
            file_path.write_bytes(b"123")

            class FakeApi:
                def __init__(self):
                    self.create_calls = []
                    self.upload_calls = []

                def create_repo(self, **kwargs):
                    self.create_calls.append(kwargs)

                def upload_file(self, **kwargs):
                    self.upload_calls.append(kwargs)
                    return {"ok": True}

            fake_api = FakeApi()
            with patch.object(upload_to_hf, "get_hf_api", return_value=fake_api):
                result = upload_to_hf.upload_file_to_hf(
                    file_path=str(file_path),
                    repo_id="my-org/my-dataset",
                    repo_type="dataset",
                    path_in_repo=None,
                    token="hf_test",
                    revision="main",
                    create_repo=True,
                    private=False,
                    commit_message="upload outputs.zip",
                )

            self.assertEqual(result, {"ok": True})
            self.assertEqual(len(fake_api.create_calls), 1)
            self.assertEqual(fake_api.create_calls[0]["repo_id"], "my-org/my-dataset")
            self.assertEqual(fake_api.create_calls[0]["repo_type"], "dataset")
            self.assertEqual(fake_api.create_calls[0]["exist_ok"], True)
            self.assertEqual(len(fake_api.upload_calls), 1)
            upload_call = fake_api.upload_calls[0]
            self.assertEqual(upload_call["repo_id"], "my-org/my-dataset")
            self.assertEqual(upload_call["repo_type"], "dataset")
            self.assertEqual(upload_call["path_in_repo"], "outputs.zip")
            self.assertEqual(upload_call["token"], "hf_test")
            self.assertEqual(upload_call["revision"], "main")

    def test_require_token_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(SystemExit):
                upload_to_hf.resolve_token("HF_TOKEN")


if __name__ == "__main__":
    unittest.main()
