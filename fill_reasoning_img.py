#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Input file not found: {path}") from exc


def main():
    parser = argparse.ArgumentParser(
        description="Fill missing reasoning_img field and write a new JSON file."
    )
    parser.add_argument(
        "--input",
        default="data_64/data_total.json",
        help="Input JSON file path.",
    )
    parser.add_argument(
        "--output",
        default="data_64/data_total_filled.json",
        help="Output JSON file path.",
    )
    parser.add_argument(
        "--field",
        default="reasoning_img",
        help="Field name to fill when missing.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite output if it already exists.",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    field_name = args.field

    data = load_json(input_path)
    if not isinstance(data, list):
        raise SystemExit("Input JSON must be a list of objects.")

    updated = 0
    for item in data:
        if isinstance(item, dict) and field_name not in item:
            item[field_name] = None
            updated += 1

    if output_path.exists() and not args.force:
        raise SystemExit(f"Output already exists: {output_path} (use --force)")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Updated {updated} items. Wrote: {output_path}")


if __name__ == "__main__":
    main()
