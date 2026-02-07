# Repository Guidelines

## Project Structure & Module Organization
This repository is organized around standalone Python scripts, not a package. Core workflow scripts live at the repo root:
- `gpt_image_generate.py`: generate edited images from dataset prompts.
- `gpt_eval.py`: run LMM-as-a-judge evaluation and aggregate scores.
- `run_eval_all.sh`: batch evaluation helper (multi-language loop).
- `compare_lang_scores.py`, `fill_subtask.py`, `fill_reasoning_img.py`, `translate_instructions.py`: data and analysis utilities.

Datasets and image assets are under `data/` (full set) and `data_64/` (small set). Model outputs should follow `outputs/<model>/<lang>/images/<category>/<index>.png`.

## Build, Test, and Development Commands
There is no build system; use direct script execution.
- `python gpt_image_generate.py --limit 5 --output-root outputs/<model>`: quick generation smoke run.
- `python gpt_eval.py --data data_64/data_total.json --input data_64 --output outputs/<model>/en`: evaluate one split.
- `bash run_eval_all.sh`: run multi-language evaluation; update top-of-file paths before use.
- `python compare_lang_scores.py --root outputs/<model> --langs en,zh,es,ar --threshold 1.0`: compare score gaps across languages.
- `python -m py_compile *.py`: fast syntax check before pushing.

## Coding Style & Naming Conventions
Use Python 3 with 4-space indentation and `snake_case` for functions/variables/files. Prefer explicit `argparse` CLIs for new scripts and keep functions small and side-effect-aware. Follow existing patterns (`Path`/`pathlib`, clear error messages, JSON UTF-8 I/O). No enforced formatter is configured; keep code PEP 8 compliant and consistent with neighboring files.

## Testing Guidelines
No formal unit test suite exists yet. Validate changes with targeted smoke tests:
- run modified scripts on a small subset (`--limit` where available),
- confirm expected artifacts are produced (e.g., `*_judge.xlsx`, `*_judge.csv`, `.pkl`),
- inspect logs in corresponding `outputs/...` folders for failed samples.

## Commit & Pull Request Guidelines
Git history uses short, imperative commit titles (for example, `Update README.md`, `Update GPT-Image-1.5`). Keep commits focused and descriptive (`Update eval path handling`, `Add language score comparator`). PRs should include:
- purpose and scope,
- exact commands run for verification,
- changed data/output paths,
- sample output or metric deltas when evaluation behavior changes.

## Security & Configuration Tips
Do not commit API keys or endpoint secrets. Use environment variables (for example `OPENAI_API_KEY`) and local-only config overrides.
