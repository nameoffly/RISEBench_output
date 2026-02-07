#!/usr/bin/env python3
"""
Translate RISEBench model instructions into multiple languages via OpenAI API.

Outputs (by default):
  datav2_total_w_subtask_zh.json
  datav2_total_w_subtask_ar.json
  datav2_total_w_subtask_es.json
Additional when requested via --langs:
  datav2_total_w_subtask_th.json
  datav2_total_w_subtask_ko.json
  datav2_total_w_subtask_fi.json
"""

import argparse
import json
import os
import time
from pathlib import Path

import requests


DEFAULT_LANGS = {
    "zh": "Simplified Chinese",
    "ar": "Arabic",
    "es": "Spanish",
    "th": "Thai",
    "ko": "Korean",
    "fi": "Finnish",
    "ru": "Russian",
    "bn": "Bengali",
    "ja": "Japanese",
    "he": "Hebrew",
    "yo": "Yoruba",
    "sw": "Swahili",
    "iu": "Inuktitut",
}

SYSTEM_TEMPLATE = (
    "You are a professional translator. Translate each instruction into {lang}. "
    "Preserve meaning and sentence structure as much as possible. "
    "Keep punctuation, quotes, and parentheses unchanged. "
    "Keep any quoted literals or single-letter tokens (e.g., 'C', \"O\") unchanged. "
    "Do not add or remove information. "
    "Input is a JSON array of strings. Output only a JSON array of strings "
    "with the same length and order."
)

PROGRESS_VERSION = 1


def _strip_code_fence(text):
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return stripped


def call_api_batch(
    instructions, lang_name, model, base_url, api_key, timeout=60, max_retries=6
):
    url = base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_TEMPLATE.format(lang=lang_name)},
            {"role": "user", "content": json.dumps(instructions, ensure_ascii=False)},
        ],
        "temperature": 0,
    }

    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
            if resp.status_code in {429, 500, 502, 503, 504}:
                time.sleep(1.5 * attempt)
                continue
            resp.raise_for_status()
            data = resp.json()
            content = _strip_code_fence(data["choices"][0]["message"]["content"])
            if not content:
                raise RuntimeError("Empty translation returned by API.")
            translations = json.loads(content)
            if not isinstance(translations, list):
                raise RuntimeError("API response is not a JSON array.")
            if len(translations) != len(instructions):
                raise RuntimeError(
                    "API response length does not match input batch size."
                )
            return translations
        except Exception as exc:
            last_err = exc
            time.sleep(1.5 * attempt)
    raise RuntimeError(f"API call failed after {max_retries} attempts: {last_err}")


def _progress_path(out_dir_path, base_name, lang_code):
    return out_dir_path / f".translate_progress_{base_name}_{lang_code}.json"


def _atomic_write_json(path, payload):
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp_path.replace(path)


def _build_progress_state(
    data_path,
    total,
    model,
    base_url,
    lang_code,
    done_indices,
    cache,
    out_items,
):
    return {
        "version": PROGRESS_VERSION,
        "source_path": str(Path(data_path).resolve()),
        "source_size": total,
        "model": model,
        "base_url": base_url,
        "lang_code": lang_code,
        "done_indices": sorted(done_indices),
        "cache": cache,
        "items": out_items,
    }


def _load_progress_state(progress_path):
    return json.loads(progress_path.read_text(encoding="utf-8"))


def _validate_progress_state(
    state, data_path, total, model, base_url, lang_code, progress_path
):
    expected = {
        "version": PROGRESS_VERSION,
        "source_path": str(Path(data_path).resolve()),
        "source_size": total,
        "model": model,
        "base_url": base_url,
        "lang_code": lang_code,
    }
    mismatches = []
    for key, value in expected.items():
        if state.get(key) != value:
            mismatches.append(f"{key}={state.get(key)!r} (expected {value!r})")
    if mismatches:
        mismatch_text = "; ".join(mismatches)
        raise RuntimeError(
            f"Progress file {progress_path} does not match current run: {mismatch_text}. "
            "Use --force-restart to discard old progress."
        )

    items = state.get("items")
    if not isinstance(items, list) or len(items) != total:
        raise RuntimeError(
            f"Progress file {progress_path} is invalid: `items` shape mismatch."
        )
    done_indices = state.get("done_indices")
    if not isinstance(done_indices, list):
        raise RuntimeError(
            f"Progress file {progress_path} is invalid: `done_indices` must be a list."
        )
    done_index_set = {int(i) for i in done_indices}
    if any(i < 0 or i >= total for i in done_index_set):
        raise RuntimeError(
            f"Progress file {progress_path} is invalid: `done_indices` out of range."
        )

    for i in done_index_set:
        if items[i] is None:
            raise RuntimeError(
                f"Progress file {progress_path} is invalid: index {i} marked done but item is null."
            )

    cache = state.get("cache")
    if not isinstance(cache, dict):
        raise RuntimeError(
            f"Progress file {progress_path} is invalid: `cache` must be an object."
        )
    return done_index_set, cache, items


def translate_dataset(
    data_path,
    out_dir,
    langs,
    model,
    base_url,
    api_key,
    batch_size,
    timeout=60,
    max_retries=6,
    resume=True,
    force_restart=False,
):
    data = json.loads(Path(data_path).read_text(encoding="utf-8"))
    base_name = Path(data_path).stem
    out_dir_path = Path(out_dir)
    out_dir_path.mkdir(parents=True, exist_ok=True)
    if batch_size <= 0:
        raise ValueError("batch_size must be a positive integer.")
    if timeout <= 0:
        raise ValueError("timeout must be a positive integer.")
    if max_retries <= 0:
        raise ValueError("max_retries must be a positive integer.")

    for lang_code in langs:
        lang_name = DEFAULT_LANGS[lang_code]
        total = len(data)
        out_path = out_dir_path / f"{base_name}_{lang_code}.json"
        progress_path = _progress_path(out_dir_path, base_name, lang_code)

        if force_restart and progress_path.exists():
            progress_path.unlink()

        done_indices = set()
        cache = {}
        out_items = [None] * total
        if resume and progress_path.exists():
            state = _load_progress_state(progress_path)
            done_indices, cache, out_items = _validate_progress_state(
                state=state,
                data_path=data_path,
                total=total,
                model=model,
                base_url=base_url,
                lang_code=lang_code,
                progress_path=progress_path,
            )
            print(
                f"Resuming {lang_name} ({lang_code}): "
                f"{len(done_indices)}/{total} already done"
            )

        print(f"Translating to {lang_name} ({lang_code})...")
        for start in range(0, total, batch_size):
            batch_positions = list(range(start, min(start + batch_size, total)))
            pending_positions = [idx for idx in batch_positions if idx not in done_indices]
            if not pending_positions:
                print(f"  {len(done_indices)}/{total} done")
                continue

            batch_items = [data[idx] for idx in pending_positions]
            batch_instructions = [item.get("instruction", "") for item in batch_items]
            translations = []
            missing_indices = []
            for i, instruction in enumerate(batch_instructions):
                if instruction in cache:
                    translations.append(cache[instruction])
                else:
                    translations.append(None)
                    missing_indices.append(i)

            if missing_indices:
                to_translate = [batch_instructions[i] for i in missing_indices]
                batch_translations = call_api_batch(
                    to_translate,
                    lang_name,
                    model=model,
                    base_url=base_url,
                    api_key=api_key,
                    timeout=timeout,
                    max_retries=max_retries,
                )
                for i, translated in zip(missing_indices, batch_translations):
                    translations[i] = translated
                    cache[batch_instructions[i]] = translated

            for idx, item, translated in zip(pending_positions, batch_items, translations):
                new_item = dict(item)
                new_item["instruction"] = translated
                out_items[idx] = new_item
                done_indices.add(idx)

            _atomic_write_json(
                progress_path,
                _build_progress_state(
                    data_path=data_path,
                    total=total,
                    model=model,
                    base_url=base_url,
                    lang_code=lang_code,
                    done_indices=done_indices,
                    cache=cache,
                    out_items=out_items,
                ),
            )
            print(f"  {len(done_indices)}/{total} done")

        if len(done_indices) != total or any(item is None for item in out_items):
            raise RuntimeError(
                f"Incomplete translation for {lang_code}: {len(done_indices)}/{total} done."
            )

        out_path.write_text(
            json.dumps(out_items, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if progress_path.exists():
            progress_path.unlink()
        print(f"Wrote {out_path}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Translate RISEBench instructions into multiple languages."
    )
    parser.add_argument(
        "--data",
        default="datav2_total_w_subtask.json",
        help="Path to source JSON file",
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Output directory for translated JSON files (default: same dir as --data)",
    )
    parser.add_argument(
        "--langs",
        default="zh,ar,es",
        help="Comma-separated language codes to generate (default: zh,ar,es)",
    )
    parser.add_argument(
        "--model",
        default="gpt-4o-2024-08-06",
        help="Model name to use for translation",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("OPENAI_BASE_URL", "https://api.bltcy.ai/v1"),
        help="OpenAI-compatible base URL (default uses OPENAI_BASE_URL or https://api.bltcy.ai/v1)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Number of instructions per API request (default: 10)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Timeout in seconds for each API request (default: 60)",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=6,
        help="Max retries for each API request (default: 6)",
    )
    parser.add_argument(
        "--resume",
        dest="resume",
        action="store_true",
        default=True,
        help="Resume from existing progress files (default: enabled)",
    )
    parser.add_argument(
        "--no-resume",
        dest="resume",
        action="store_false",
        help="Disable resume and do not load existing progress files",
    )
    parser.add_argument(
        "--force-restart",
        action="store_true",
        help="Delete existing progress file for each language before translation",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is not set in the environment.")
    out_dir = args.out_dir
    if out_dir is None:
        out_dir = str(Path(args.data).parent)

    langs = [code.strip() for code in args.langs.split(",") if code.strip()]
    unknown = [code for code in langs if code not in DEFAULT_LANGS]
    if unknown:
        raise SystemExit(f"Unsupported language code(s): {', '.join(unknown)}")

    translate_dataset(
        data_path=args.data,
        out_dir=out_dir,
        langs=langs,
        model=args.model,
        base_url=args.base_url,
        api_key=api_key,
        batch_size=args.batch_size,
        timeout=args.timeout,
        max_retries=args.max_retries,
        resume=args.resume,
        force_restart=args.force_restart,
    )


if __name__ == "__main__":
    main()
