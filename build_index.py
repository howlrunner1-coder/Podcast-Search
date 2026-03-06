#!/usr/bin/env python3
"""
build_index.py
Parses all .srt files in ./subtitles/ and outputs search-data.json
for use with the static podcast search UI.
"""

import os
import re
import json
import sys
from pathlib import Path

SUBTITLES_DIR = Path("subtitles")
OUTPUT_FILE = Path("search-data.json")
CONTEXT_WINDOW = 2  # number of blocks before/after a match to include as context


def parse_srt(filepath: Path) -> list[dict]:
    """Parse an SRT file into a list of subtitle blocks."""
    text = filepath.read_text(encoding="utf-8", errors="replace")
    # Split on double newline (block separator)
    raw_blocks = re.split(r"\n\s*\n", text.strip())

    blocks = []
    for raw in raw_blocks:
        lines = raw.strip().splitlines()
        if len(lines) < 2:
            continue

        # First line should be the block index number
        try:
            block_num = int(lines[0].strip())
        except ValueError:
            continue

        # Second line should be the timestamp
        timestamp_match = re.match(
            r"(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})",
            lines[1].strip(),
        )
        if not timestamp_match:
            continue

        start_ts = timestamp_match.group(1).replace(",", ".")
        end_ts = timestamp_match.group(2).replace(",", ".")

        # Remaining lines are the subtitle text
        text_lines = lines[2:]
        text_content = " ".join(line.strip() for line in text_lines if line.strip())

        if not text_content:
            continue

        blocks.append(
            {
                "num": block_num,
                "start": start_ts,
                "end": end_ts,
                "text": text_content,
            }
        )

    return blocks


def derive_episode_name(filepath: Path) -> str:
    """Turn a filename like 'ep042_my_great_episode.srt' into 'ep042 my great episode'."""
    stem = filepath.stem
    return stem.replace("_", " ").replace("-", " ")


def build_search_entries(filepath: Path) -> list[dict]:
    """
    Build flat search entries from an SRT file.
    Each entry includes the matched block plus surrounding context blocks.
    """
    blocks = parse_srt(filepath)
    if not blocks:
        return []

    episode = derive_episode_name(filepath)
    filename = filepath.name
    entries = []

    for i, block in enumerate(blocks):
        # Gather context: up to CONTEXT_WINDOW blocks before and after
        ctx_start = max(0, i - CONTEXT_WINDOW)
        ctx_end = min(len(blocks) - 1, i + CONTEXT_WINDOW)

        context_blocks = []
        for j in range(ctx_start, ctx_end + 1):
            context_blocks.append(
                {
                    "start": blocks[j]["start"],
                    "end": blocks[j]["end"],
                    "text": blocks[j]["text"],
                    "isMatch": j == i,
                }
            )

        entries.append(
            {
                # Unique ID for Lunr: filename + block index
                "id": f"{filename}::{i}",
                "file": filename,
                "episode": episode,
                "start": block["start"],
                "text": block["text"],
                "context": context_blocks,
            }
        )

    return entries


def main():
    if not SUBTITLES_DIR.exists():
        print(f"Error: '{SUBTITLES_DIR}' directory not found.", file=sys.stderr)
        print("Create a 'subtitles/' directory and place your .srt files inside it.")
        sys.exit(1)

    srt_files = sorted(SUBTITLES_DIR.glob("**/*.srt"))
    if not srt_files:
        print(f"No .srt files found in '{SUBTITLES_DIR}'.", file=sys.stderr)
        sys.exit(1)

    all_entries = []
    for srt_file in srt_files:
        entries = build_search_entries(srt_file)
        all_entries.extend(entries)
        print(f"  Parsed {srt_file.name}: {len(entries)} blocks")

    OUTPUT_FILE.write_text(
        json.dumps(all_entries, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    print(f"\n✓ Wrote {len(all_entries)} entries from {len(srt_files)} files → {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
