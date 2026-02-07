#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Input file not found: {path}") from exc


def build_subtask_map(source_items, key_field: str, value_field: str):
    mapping = {}
    missing = 0
    for item in source_items:
        if not isinstance(item, dict):
            continue
        key = item.get(key_field)
        value = item.get(value_field)
        if key is None or value is None:
            missing += 1
            continue
        mapping[key] = value
    return mapping, missing


def main():
    parser = argparse.ArgumentParser(
        description="Fill subtask field in data_64/data_total_filled.json using datav2_total_w_subtask.json."
    )
    parser.add_argument(
        "--source",
        default="datav2_total_w_subtask.json",
        help="Source JSON file containing subtask field.",
    )
    parser.add_argument(
        "--target",
        default="data_64/data_total_filled.json",
        help="Target JSON file to fill subtask.",
    )
    parser.add_argument(
        "--output",
        default="data_64/data_total_filled_with_subtask.json",
        help="Output JSON file path.",
    )
    parser.add_argument(
        "--key",
        default="index",
        help="Field name used to match items (default: index).",
    )
    parser.add_argument(
        "--field",
        default="subtask",
        help="Field name to copy from source and fill in target.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite output if it already exists.",
    )
    args = parser.parse_args()

    source_path = Path(args.source)
    target_path = Path(args.target)
    output_path = Path(args.output)

    source_data = load_json(source_path)
    target_data = load_json(target_path)

    if not isinstance(source_data, list) or not isinstance(target_data, list):
        raise SystemExit("Source and target JSON must be lists of objects.")

    subtask_map, missing_src = build_subtask_map(
        source_data, args.key, args.field
    )

    updated = 0
    not_found = 0
    for item in target_data:
        if not isinstance(item, dict):
            continue
        if args.field in item and item[args.field] is not None:
            continue
        key = item.get(args.key)
        if key in subtask_map:
            item[args.field] = subtask_map[key]
            updated += 1
        else:
            not_found += 1

    if output_path.exists() and not args.force:
        raise SystemExit(f"Output already exists: {output_path} (use --force)")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(target_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(
        f"Source missing {args.field}: {missing_src}; "
        f"updated {updated}; not found {not_found}; "
        f"wrote {output_path}"
    )


if __name__ == "__main__":
    main()
