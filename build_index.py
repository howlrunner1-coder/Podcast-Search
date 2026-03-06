#!/usr/bin/env python3
"""
build_index.py

Parses all .srt files in ./subtitles/ and writes:

  search-index/manifest.json          — chunk list + totals
  search-index/chunk-000.json         — first N episodes + their entries
  search-index/chunk-001.json         — next N episodes …
  …

Each chunk is kept under MAX_CHUNK_MB so no single file exceeds GitHub's
100 MB push limit. The browser loads all chunks in parallel and merges
them before building the Lunr index.

Chunk structure:
  {
    "episodes": { "ep001.srt": { "name": "…", "blocks": [{"s":"HH:MM:SS","t":"…"}] } },
    "entries":  [ {"id":"ep001.srt::0","f":"ep001.srt","e":"…","t":"…"} ]
  }

Manifest structure:
  {
    "chunks":         ["search-index/chunk-000.json", …],
    "total_episodes": N,
    "total_entries":  N
  }
"""

import re
import json
import sys
from pathlib import Path

SUBTITLES_DIR  = Path("subtitles")
OUTPUT_DIR     = Path("search-index")
MANIFEST_FILE  = OUTPUT_DIR / "manifest.json"
MAX_CHUNK_MB   = 50          # target ceiling per chunk file


def parse_srt(filepath: Path) -> list[dict]:
    text = filepath.read_text(encoding="utf-8", errors="replace")
    raw_blocks = re.split(r"\n\s*\n", text.strip())
    blocks = []
    for raw in raw_blocks:
        lines = raw.strip().splitlines()
        if len(lines) < 2:
            continue
        try:
            int(lines[0].strip())
        except ValueError:
            continue
        ts_match = re.match(
            r"(\d{2}:\d{2}:\d{2})[,\.](\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2})[,\.]",
            lines[1].strip(),
        )
        if not ts_match:
            continue
        start_ts = ts_match.group(1)
        text_content = " ".join(line.strip() for line in lines[2:] if line.strip())
        if text_content:
            blocks.append({"s": start_ts, "t": text_content})
    return blocks


def episode_name(filepath: Path) -> str:
    return filepath.stem.replace("_", " ").replace("-", " ")


def write_chunk(chunk_idx: int, episodes: dict, entries: list) -> tuple[str, float]:
    OUTPUT_DIR.mkdir(exist_ok=True)
    path = OUTPUT_DIR / f"chunk-{chunk_idx:03d}.json"
    payload = json.dumps(
        {"episodes": episodes, "entries": entries},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    path.write_text(payload, encoding="utf-8")
    mb = len(payload.encode()) / 1_048_576
    return str(path), mb


def main():
    if not SUBTITLES_DIR.exists():
        print(f"Error: '{SUBTITLES_DIR}' directory not found.", file=sys.stderr)
        sys.exit(1)

    srt_files = sorted(SUBTITLES_DIR.glob("**/*.srt"))
    if not srt_files:
        print(f"No .srt files found in '{SUBTITLES_DIR}'.", file=sys.stderr)
        sys.exit(1)

    # Delete old chunks so stale files don't linger
    if OUTPUT_DIR.exists():
        for old in OUTPUT_DIR.glob("chunk-*.json"):
            old.unlink()

    chunk_idx      = 0
    chunk_episodes = {}
    chunk_entries  = []
    chunk_bytes    = 0
    chunk_paths    = []

    total_episodes = 0
    total_entries  = 0

    MAX_CHUNK_BYTES = MAX_CHUNK_MB * 1_048_576

    def flush_chunk():
        nonlocal chunk_idx, chunk_episodes, chunk_entries, chunk_bytes
        if not chunk_episodes:
            return
        path, mb = write_chunk(chunk_idx, chunk_episodes, chunk_entries)
        chunk_paths.append(str(OUTPUT_DIR.name + "/" + Path(path).name))
        print(f"  → chunk-{chunk_idx:03d}.json  ({mb:.1f} MB, "
              f"{len(chunk_episodes)} episodes, {len(chunk_entries)} entries)")
        chunk_idx      += 1
        chunk_episodes  = {}
        chunk_entries   = []
        chunk_bytes     = 0

    for srt_file in srt_files:
        blocks = parse_srt(srt_file)
        if not blocks:
            print(f"  Skipped {srt_file.name}: no parseable blocks")
            continue

        fname = srt_file.name
        ename = episode_name(srt_file)

        ep_data = {"name": ename, "blocks": blocks}
        ep_entries = [
            {"id": f"{fname}::{i}", "f": fname, "e": ename, "t": blk["t"]}
            for i, blk in enumerate(blocks)
        ]

        # Estimate bytes this episode adds (rough: JSON encode the entries)
        estimated = len(json.dumps(ep_data, separators=(",",":")).encode()) + \
                    len(json.dumps(ep_entries, separators=(",",":")).encode())

        # Flush before adding if it would push us over the limit
        if chunk_bytes + estimated > MAX_CHUNK_BYTES and chunk_episodes:
            flush_chunk()

        chunk_episodes[fname] = ep_data
        chunk_entries.extend(ep_entries)
        chunk_bytes += estimated
        total_episodes += 1
        total_entries  += len(blocks)

        print(f"  Parsed {fname}: {len(blocks)} blocks")

    flush_chunk()  # write final partial chunk

    # Write manifest
    OUTPUT_DIR.mkdir(exist_ok=True)
    manifest = {
        "chunks":         chunk_paths,
        "total_episodes": total_episodes,
        "total_entries":  total_entries,
    }
    MANIFEST_FILE.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"\n✓ {total_entries:,} entries · {total_episodes} episodes "
          f"→ {len(chunk_paths)} chunk(s) in {OUTPUT_DIR}/")
    print(f"  Manifest: {MANIFEST_FILE}")


if __name__ == "__main__":
    main()
