#!/usr/bin/env python3
import argparse
from pathlib import Path
import pandas as pd


def load_lang(path: Path, lang: str, keep_meta: bool) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    df = pd.read_excel(path)
    required = {"index", "score"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"{path} missing columns: {sorted(missing)}")

    cols = ["index"]
    if keep_meta:
        if "category" in df.columns:
            cols.append("category")
        if "subtask" in df.columns:
            cols.append("subtask")
    cols.append("score")

    df = df[cols].copy()
    df = df.rename(columns={"score": f"score_{lang}"})
    return df


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare per-sample scores across languages and surface large gaps."
    )
    parser.add_argument(
        "--root",
        type=str,
        default="outputs/bagel",
        help="Root directory containing per-language outputs.",
    )
    parser.add_argument(
        "--langs",
        type=str,
        default="en,zh,es,ar",
        help="Comma-separated language codes.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=1.0,
        help="Filter by score_diff >= threshold.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="outputs/bagel/compare/large_diffs.csv",
        help="Output CSV path.",
    )
    parser.add_argument(
        "--base-lang",
        type=str,
        default=None,
        help="Language used for category/subtask columns (default: first in --langs).",
    )
    args = parser.parse_args()

    langs = [x.strip() for x in args.langs.split(",") if x.strip()]
    if not langs:
        raise ValueError("No languages provided via --langs.")

    base_lang = args.base_lang or langs[0]
    if base_lang not in langs:
        raise ValueError(f"--base-lang {base_lang} not in --langs {langs}")

    root = Path(args.root)
    paths = {lang: root / lang / f"{lang}_judge.xlsx" for lang in langs}

    base_df = load_lang(paths[base_lang], base_lang, keep_meta=True)
    merged = base_df
    for lang in langs:
        if lang == base_lang:
            continue
        df = load_lang(paths[lang], lang, keep_meta=False)
        merged = merged.merge(df, on="index", how="outer")

    score_cols = [f"score_{lang}" for lang in langs if f"score_{lang}" in merged.columns]
    if len(score_cols) < 2:
        raise ValueError("Need at least two language score columns to compare.")

    scores = merged[score_cols]
    merged["valid_langs"] = scores.notna().sum(axis=1)
    merged["score_max"] = scores.max(axis=1, skipna=True)
    merged["score_min"] = scores.min(axis=1, skipna=True)
    merged["score_diff"] = merged["score_max"] - merged["score_min"]

    missing_langs = scores.isna().apply(
        lambda row: ",".join(
            [lang for lang, missing in zip(langs, row.tolist()) if missing]
        ),
        axis=1,
    )
    merged["missing_langs"] = missing_langs

    filtered = merged[
        (merged["valid_langs"] >= 2) & (merged["score_diff"] >= args.threshold)
    ].copy()
    filtered = filtered.sort_values("score_diff", ascending=False)

    out_cols = ["index"]
    if "category" in filtered.columns:
        out_cols.append("category")
    if "subtask" in filtered.columns:
        out_cols.append("subtask")
    out_cols += score_cols + [
        "score_diff",
        "score_max",
        "score_min",
        "missing_langs",
        "valid_langs",
    ]

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    filtered.to_csv(output_path, index=False)

    print(f"Total samples: {len(merged)}")
    print(f"Hit samples: {len(filtered)} (threshold >= {args.threshold})")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    main()
