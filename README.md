# Podcast Transcript Search

A fully static, client-side search engine for your podcast SRT subtitle files.
No backend, no database — everything runs in the browser.

## How it works

1. SRT files live in `subtitles/`
2. `build_index.py` parses them → `search-data.json`
3. `index.html` loads the JSON, builds a [Lunr.js](https://lunrjs.com/) full-text index in the browser, and renders results with surrounding context
4. GitHub Actions rebuilds `search-data.json` automatically whenever you push new SRT files

## Setup

### 1. Add your SRT files

Drop your `.srt` files into the `subtitles/` directory.
Subdirectories are supported — the script scans recursively.

```
subtitles/
  ep001_pilot.srt
  ep002_second_episode.srt
  season2/
    ep021_new_season.srt
```

Episode display names are derived from filenames: underscores and hyphens become spaces.

### 2. Configure GitHub Pages

In your repository settings:
- Go to **Settings → Pages**
- Set **Source** to `Deploy from a branch`
- Set **Branch** to `main`, folder `/` (root)

### 3. Push — GitHub Actions handles the rest

On every push that touches `subtitles/` or `build_index.py`, the workflow will:
1. Run `build_index.py`
2. Commit the updated `search-data.json`
3. GitHub Pages will redeploy automatically

### Running the build locally

```bash
python build_index.py
# Then open index.html in your browser (or serve with: python -m http.server)
```

## Configuration

Edit the top of `build_index.py` to adjust:

| Variable         | Default | Description                                    |
|------------------|---------|------------------------------------------------|
| `SUBTITLES_DIR`  | `subtitles` | Directory containing your `.srt` files    |
| `CONTEXT_WINDOW` | `2`     | How many blocks before/after a match to show   |

## File size considerations

| Episodes | Avg blocks/ep | Approx index size |
|----------|--------------|-------------------|
| 100      | 500          | ~8 MB             |
| 300      | 500          | ~24 MB            |
| 500      | 500          | ~40 MB            |

For very large archives (500+ episodes), consider splitting `search-data.json` by season
or adding a pre-built Lunr index to avoid in-browser indexing time.
