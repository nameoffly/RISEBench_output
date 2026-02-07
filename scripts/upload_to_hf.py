#!/usr/bin/env python3
import argparse
import os
from pathlib import Path


def get_hf_api():
    try:
        from huggingface_hub import HfApi
    except ImportError as exc:
        raise SystemExit(
            "Missing dependency: huggingface_hub. Install with: pip install huggingface_hub"
        ) from exc
    return HfApi()


def resolve_token(token_env: str):
    token = os.environ.get(token_env)
    if not token:
        raise SystemExit(f"{token_env} is not set in the environment.")
    return token


def resolve_path_in_repo(file_path: str, path_in_repo: str | None):
    if path_in_repo and path_in_repo.strip():
        return path_in_repo.strip()
    return Path(file_path).name


def upload_file_to_hf(
    file_path: str,
    repo_id: str,
    repo_type: str = "dataset",
    path_in_repo: str | None = None,
    token: str | None = None,
    revision: str = "main",
    create_repo: bool = False,
    private: bool = False,
    commit_message: str | None = None,
):
    source = Path(file_path)
    if not source.exists():
        raise SystemExit(f"File not found: {source}")

    upload_path = resolve_path_in_repo(file_path, path_in_repo)
    api = get_hf_api()

    if create_repo:
        api.create_repo(
            repo_id=repo_id,
            repo_type=repo_type,
            private=private,
            exist_ok=True,
            token=token,
        )

    msg = commit_message or f"Upload {source.name}"
    return api.upload_file(
        path_or_fileobj=str(source),
        path_in_repo=upload_path,
        repo_id=repo_id,
        repo_type=repo_type,
        token=token,
        revision=revision,
        commit_message=msg,
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description="Upload a local file (default: outputs.zip) to Hugging Face."
    )
    parser.add_argument(
        "--file",
        default="outputs.zip",
        help="Local file to upload (default: outputs.zip).",
    )
    parser.add_argument(
        "--repo-id",
        required=True,
        help="Target Hugging Face repo id, e.g. your-org/RISEBench-outputs.",
    )
    parser.add_argument(
        "--repo-type",
        default="dataset",
        choices=["dataset", "model", "space"],
        help="Hugging Face repo type (default: dataset).",
    )
    parser.add_argument(
        "--path-in-repo",
        default=None,
        help="Destination path in repo (default: use local file name).",
    )
    parser.add_argument(
        "--revision",
        default="main",
        help="Target branch/tag/commit (default: main).",
    )
    parser.add_argument(
        "--token-env",
        default="HF_TOKEN",
        help="Environment variable storing HF token (default: HF_TOKEN).",
    )
    parser.add_argument(
        "--create-repo",
        action="store_true",
        help="Create repo if missing (exist_ok=True).",
    )
    parser.add_argument(
        "--private",
        action="store_true",
        help="Create repo as private (effective only with --create-repo).",
    )
    parser.add_argument(
        "--commit-message",
        default=None,
        help="Custom commit message.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    token = resolve_token(args.token_env)
    result = upload_file_to_hf(
        file_path=args.file,
        repo_id=args.repo_id,
        repo_type=args.repo_type,
        path_in_repo=args.path_in_repo,
        token=token,
        revision=args.revision,
        create_repo=args.create_repo,
        private=args.private,
        commit_message=args.commit_message,
    )
    print("Upload done:", result)


if __name__ == "__main__":
    main()
