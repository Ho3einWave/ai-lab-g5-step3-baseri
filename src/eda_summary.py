#!/usr/bin/env python3
"""Summarize the step-3 metadata table for the music genre project.

The script only uses the Python standard library, so the documentation can be
reproduced without installing pandas or matplotlib. If an audio directory is
provided, it also reads the WAV headers and reports the technical specs.
"""

from __future__ import annotations

import argparse
import csv
import json
import wave
from collections import Counter
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_METADATA = PROJECT_DIR / "data" / "metadata.csv"
DEFAULT_OUTPUT = PROJECT_DIR / "reports" / "eda_summary.json"


def read_metadata(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [
            {key: (value or "").strip() for key, value in row.items()}
            for row in reader
        ]

    if not rows:
        raise ValueError(f"No records found in {path}")

    return rows


def count_duplicates(values: list[str]) -> int:
    return len(values) - len(set(values))


def audio_summary(root: Path, rows: list[dict[str, str]]) -> dict:
    files = []

    for row in rows:
        path = root / row["genre"] / row["file_name"]

        if not path.exists():
            continue

        with wave.open(str(path), "rb") as handle:
            frames = handle.getnframes()
            rate = handle.getframerate()
            files.append(
                {
                    "file_name": row["file_name"],
                    "genre": row["genre"],
                    "sample_rate_hz": rate,
                    "channels": handle.getnchannels(),
                    "bit_depth": handle.getsampwidth() * 8,
                    "duration_seconds": round(frames / rate, 3),
                    "size_bytes": path.stat().st_size,
                }
            )

    if not files:
        return {"files_checked": 0}

    return {
        "files_checked": len(files),
        "sample_rates_hz": sorted({item["sample_rate_hz"] for item in files}),
        "channels": sorted({item["channels"] for item in files}),
        "bit_depths": sorted({item["bit_depth"] for item in files}),
        "duration_min_seconds": min(item["duration_seconds"] for item in files),
        "duration_max_seconds": max(item["duration_seconds"] for item in files),
        "total_size_bytes": sum(item["size_bytes"] for item in files),
        "files": files,
    }


def build_summary(metadata: Path, audio_root: Path | None) -> dict:
    rows = read_metadata(metadata)
    columns = list(rows[0].keys())
    genres = Counter(row["genre"] for row in rows)
    total = len(rows)

    genres_sorted = dict(sorted(genres.items()))

    formats = Counter(
        Path(row["file_name"]).suffix.lower() or "unknown" for row in rows
    )

    missing = {
        column: sum(1 for row in rows if not row.get(column, "").strip())
        for column in columns
    }

    paths = [row["file_path"] for row in rows]

    try:
        metadata_label = str(metadata.relative_to(PROJECT_DIR))
    except ValueError:
        metadata_label = str(metadata)

    return {
        "metadata_file": metadata_label,
        "records": total,
        "columns": columns,
        "genres": genres_sorted,
        "genre_percent": {
            genre: round(count / total * 100, 2)
            for genre, count in genres_sorted.items()
        },
        "missing_values": missing,
        "duplicates": {
            "rows": total
            - len({tuple(row[column] for column in columns) for row in rows}),
            "file_name": count_duplicates([row["file_name"] for row in rows]),
            "file_path": count_duplicates(paths),
        },
        "formats": dict(sorted(formats.items())),
        "paths": {
            "absolute_windows": sum(
                1
                for path in paths
                if len(path) > 1 and path[1] == ":" and "\\" in path
            ),
            "backslash": sum(1 for path in paths if "\\" in path),
        },
        "audio": audio_summary(audio_root, rows) if audio_root else None,
    }


def print_summary(summary: dict) -> None:
    print(f"Metadata: {summary['metadata_file']}")
    print(f"Records:  {summary['records']}")
    print(f"Columns:  {', '.join(summary['columns'])}")

    print("\nGenres:")
    for genre, count in summary["genres"].items():
        percent = summary["genre_percent"][genre]
        print(f"  {genre:<10} {count:>2}  ({percent:.2f}%)")

    print("\nMissing values:", summary["missing_values"])
    print("Duplicates:", summary["duplicates"])
    print("Formats:", summary["formats"])
    print("Paths:", summary["paths"])

    audio = summary["audio"]

    if audio:
        print(f"\nAudio files checked: {audio['files_checked']}")

        if audio["files_checked"]:
            print("  sample rates:", audio["sample_rates_hz"])
            print("  channels:    ", audio["channels"])
            print("  bit depths:  ", audio["bit_depths"])
            print(
                "  duration:    ",
                audio["duration_min_seconds"],
                "-",
                audio["duration_max_seconds"],
                "s",
            )
            print(
                "  total size:  ",
                round(audio["total_size_bytes"] / 1_000_000, 2),
                "MB",
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--metadata",
        type=Path,
        default=DEFAULT_METADATA,
        help="Path to metadata.csv",
    )
    parser.add_argument(
        "--audio-root",
        type=Path,
        default=None,
        help="Optional path to the genres_original folder",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Path to the JSON output",
    )
    args = parser.parse_args()

    summary = build_summary(args.metadata, args.audio_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print_summary(summary)
    print(f"\nSaved: {args.output}")


if __name__ == "__main__":
    main()
