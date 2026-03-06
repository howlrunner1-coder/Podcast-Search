#!/usr/bin/env python3
"""
build_index.py
Parses all .srt files in ./subtitles/ and outputs search-data.json.

Structure (no context duplication):
  {
    "episodes": {
      "ep001.srt": { "name": "ep001 the pilot", "blocks": [{"s":"00:00:01","t":"text"}, ...] }
    },
    "entries": [
      {"id":"ep001.srt::0", "f":"ep001.srt", "e":"ep001 the pilot", "t":"text"},
      ...
    ]
  }

Context is reconstructed at search time from the episodes map using the block
index encoded in the entry ID, so no text is ever stored more than once.
"""

import re
import json
import sys
from pathlib import Path

SUBTITLES_DIR = Path("subtitles")
OUTPUT_FILE   = Path("search-data.json")


def parse_srt(filepath: Path) -> list[dict]:
    """Parse an SRT file into a compact list of {s: start, t: text} blocks."""
    text = filepath.read_text(encoding="utf-8", errors="replace")
    raw_blocks = re.split(r"\n\s*\n", text.strip())

    blocks = []
    for raw in raw_blocks:
        lines = raw.strip().splitlines()
        if len(lines) < 2:
            continue

        # Line 0: block counter (skip if not an integer)
        try:
            int(lines[0].strip())
        except ValueError:
            continue

        # Line 1: timestamp
        ts_match = re.match(
            r"(\d{2}:\d{2}:\d{2})[,\.](\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2})[,\.]",
            lines[1].strip(),
        )
        if not ts_match:
            continue

        # Store HH:MM:SS only — milliseconds waste space and aren't needed for display
        start_ts = ts_match.group(1)

        text_content = " ".join(
            line.strip() for line in lines[2:] if line.strip()
        )
        if not text_content:
            continue

        blocks.append({"s": start_ts, "t": text_content})

    return blocks


def episode_name(filepath: Path) -> str:
    return filepath.stem.replace("_", " ").replace("-", " ")


def main():
    if not SUBTITLES_DIR.exists():
        print(f"Error: '{SUBTITLES_DIR}' directory not found.", file=sys.stderr)
        sys.exit(1)

    srt_files = sorted(SUBTITLES_DIR.glob("**/*.srt"))
    if not srt_files:
        print(f"No .srt files found in '{SUBTITLES_DIR}'.", file=sys.stderr)
        sys.exit(1)

    episodes = {}   # filename → {name, blocks}
    entries  = []   # flat list for Lunr

    for srt_file in srt_files:
        blocks = parse_srt(srt_file)
        if not blocks:
            print(f"  Skipped {srt_file.name}: no parseable blocks")
            continue

        fname  = srt_file.name
        ename  = episode_name(srt_file)

        # Store each episode's blocks once
        episodes[fname] = {"name": ename, "blocks": blocks}

        # Flat searchable entries — id encodes file + block index for context lookup
        for i, blk in enumerate(blocks):
            entries.append({
                "id": f"{fname}::{i}",
                "f":  fname,
                "e":  ename,
                "t":  blk["t"],
            })

        print(f"  Parsed {fname}: {len(blocks)} blocks")

    output = {"episodes": episodes, "entries": entries}
    OUTPUT_FILE.write_text(
        json.dumps(output, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    size_mb = OUTPUT_FILE.stat().st_size / 1_048_576
    print(f"\n✓ {len(entries)} entries · {len(episodes)} episodes → {OUTPUT_FILE} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
