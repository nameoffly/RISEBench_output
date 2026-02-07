#!/usr/bin/env python3
import argparse
import base64
import json
import os
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

try:
    from openai import OpenAI
except ImportError as exc:
    raise SystemExit(
        "Missing dependency: openai. Install with: pip install openai"
    ) from exc


LANG_MAP = {
    "data_total.json": "en",
    "data_total_zh.json": "zh",
    "data_total_es.json": "es",
    "data_total_ar.json": "ar",
}

_thread_local = threading.local()
_error_lock = threading.Lock()


def get_client(api_key: str, base_url: str) -> OpenAI:
    client = getattr(_thread_local, "client", None)
    if client is None:
        _thread_local.client = OpenAI(api_key=api_key, base_url=base_url)
        client = _thread_local.client
    return client


def infer_lang(dataset_path: Path) -> str:
    name = dataset_path.name
    if name in LANG_MAP:
        return LANG_MAP[name]
    raise ValueError(f"Unsupported dataset name: {name}")


def iter_items(dataset_path: Path, limit: int | None):
    data = json.loads(dataset_path.read_text(encoding="utf-8"))
    if limit is not None:
        data = data[:limit]
    for item in data:
        yield item


def save_error(error_log: Path, payload: dict):
    with _error_lock:
        error_log.parent.mkdir(parents=True, exist_ok=True)
        with error_log.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def call_edit(
    client: OpenAI,
    image_path: Path,
    prompt: str,
    model: str,
    size: str | None,
):
    kwargs = {
        "model": model,
        "prompt": prompt,
        "image": image_path.open("rb"),
        "response_format": "b64_json",
        "n": 1,
    }
    if size:
        kwargs["size"] = size
    try:
        if hasattr(client.images, "edit"):
            resp = client.images.edit(**kwargs)
        elif hasattr(client.images, "edits"):
            resp = client.images.edits(**kwargs)
        else:
            raise RuntimeError("OpenAI SDK does not expose images.edit(s).")
    finally:
        kwargs["image"].close()
    if not resp.data or not getattr(resp.data[0], "b64_json", None):
        raise RuntimeError("No image data returned by API.")
    return resp.data[0].b64_json


def process_task(
    task: dict,
    api_key: str,
    base_url: str,
    output_root: Path,
    overwrite: bool,
    model: str,
    size: str | None,
    retries: int,
    sleep: float,
    error_log: Path,
):
    dataset_path = task["dataset_path"]
    dataset_dir = dataset_path.parent
    image_rel = task["image"]
    instruction = task["instruction"]
    index = task["index"]
    category = task["category"]
    lang = task["lang"]

    input_path = dataset_dir / image_rel
    output_path = output_root / lang / category / f"{index}.png"

    if output_path.exists() and not overwrite:
        return "skipped", output_path

    if not input_path.exists():
        save_error(
            error_log,
            {
                "type": "missing_input",
                "dataset": str(dataset_path),
                "index": index,
                "image": str(input_path),
            },
        )
        return "failed", output_path

    if not instruction:
        save_error(
            error_log,
            {
                "type": "missing_instruction",
                "dataset": str(dataset_path),
                "index": index,
            },
        )
        return "failed", output_path

    output_path.parent.mkdir(parents=True, exist_ok=True)

    for attempt in range(1, retries + 1):
        try:
            client = get_client(api_key, base_url)
            b64 = call_edit(client, input_path, instruction, model, size)
            output_path.write_bytes(base64.b64decode(b64))
            return "ok", output_path
        except Exception as exc:
            if attempt >= retries:
                save_error(
                    error_log,
                    {
                        "type": "api_error",
                        "dataset": str(dataset_path),
                        "index": index,
                        "image": str(input_path),
                        "error": str(exc),
                    },
                )
                return "failed", output_path
            backoff = sleep * (2 ** (attempt - 1))
            jitter = random.uniform(0, sleep)
            time.sleep(backoff + jitter)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate edited images using gpt-image-1."
    )
    parser.add_argument(
        "--datasets",
        nargs="+",
        default=[
            "data_64/data_total.json",
            "data_64/data_total_zh.json",
            "data_64/data_total_es.json",
            "data_64/data_total_ar.json",
        ],
        help="List of dataset JSON paths.",
    )
    parser.add_argument(
        "--output-root",
        default="outputs/gpt-image-1",
        help="Output root directory.",
    )
    parser.add_argument(
        "--model",
        default="gpt-image-1",
        help="Model name.",
    )
    parser.add_argument(
        "--base-url",
        default="https://api.bltcy.ai/v1",
        help="OpenAI-compatible base URL.",
    )
    parser.add_argument(
        "--api-key-env",
        default="OPENAI_API_KEY",
        help="Environment variable for API key.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing outputs.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit items per dataset (for quick test).",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="Max retries per image.",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=1.0,
        help="Base sleep seconds for exponential backoff.",
    )
    parser.add_argument(
        "--size",
        default=None,
        help="Output image size (e.g., 1024x1024).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of concurrent workers.",
    )
    parser.add_argument(
        "--log-every",
        type=int,
        default=10,
        help="Print progress every N completed tasks.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    api_key = os.environ.get(args.api_key_env)
    if not api_key:
        raise SystemExit(f"{args.api_key_env} is not set in the environment.")

    output_root = Path(args.output_root)
    error_log = output_root / "errors.jsonl"

    tasks = []
    for ds in args.datasets:
        ds_path = Path(ds)
        if not ds_path.exists():
            raise SystemExit(f"Dataset not found: {ds_path}")
        lang = infer_lang(ds_path)
        for item in iter_items(ds_path, args.limit):
            tasks.append(
                {
                    "dataset_path": ds_path,
                    "lang": lang,
                    "index": item.get("index"),
                    "category": item.get("category"),
                    "instruction": item.get("instruction"),
                    "image": item.get("image"),
                }
            )

    if args.workers < 1:
        raise SystemExit("--workers must be >= 1")

    total = len(tasks)
    if total == 0:
        print("No tasks found.")
        return

    ok = skipped = failed = 0
    completed = 0

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [
            executor.submit(
                process_task,
                task,
                api_key,
                args.base_url,
                output_root,
                args.overwrite,
                args.model,
                args.size,
                args.retries,
                args.sleep,
                error_log,
            )
            for task in tasks
        ]
        for future in as_completed(futures):
            status, _ = future.result()
            completed += 1
            if status == "ok":
                ok += 1
            elif status == "skipped":
                skipped += 1
            else:
                failed += 1
            if completed % args.log_every == 0 or completed == total:
                print(
                    f"Progress {completed}/{total} | ok={ok} skipped={skipped} failed={failed}"
                )

    print(f"Done. ok={ok} skipped={skipped} failed={failed}")


if __name__ == "__main__":
    main()
