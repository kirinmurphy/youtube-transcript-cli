# yt-transcript-cli

Fetch YouTube video and playlist transcripts from the command line.

## Installation

Install from PyPI:  
[pypi.org/project/yt-transcript-cli/](https://pypi.org/project/yt-transcript-cli/)

```bash
pip install yt-transcript-cli
```

### Troubleshooting: `pip` install not working

On some systems (especially macOS), `pip install` may fail or the installed command may not be available on your PATH. This is because modern Python environments restrict installing packages globally to avoid conflicts with system packages.

Use [pipx](https://pipx.pypa.io/) instead, which installs CLI tools in isolated environments:

```bash
brew install pipx   # macOS
pipx install yt-transcript-cli
```

### Install from GitHub

```bash
pip install git+https://github.com/kirinmurphy/youtube-transcript-cli.git
```

Or install locally for development:

```bash
git clone https://github.com/kirinmurphy/youtube-transcript-cli.git
cd youtube-transcript-cli
pip install -e .
```

## Usage

After installation, the `yt-transcript-cli` command is available.

### Single video

```bash
yt-transcript-cli "https://www.youtube.com/watch?v=VIDEO_ID"
```

### Timestamped JSON exports

Use JSON when research tools need each segment's original timing:

```bash
yt-transcript-cli --format json "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

The file `transcript_dQw4w9WgXcQ.json` contains an array of segment dictionaries.
It preserves text, numeric start times and durations (in seconds), segment order,
Unicode, and any additional fields returned by the fetcher.

Illustrative file contents:

```json
[
  {"text": "First sentence.", "start": 1.25, "duration": 2.5},
  {"text": "Next sentence.", "start": 4.0, "duration": 1.75}
]
```

The default, also available as `--format text`, saves continuous text to `.txt`.
The format option also applies to multiple videos, playlists, URL files, and interactive mode.

### Multiple videos

```bash
yt-transcript-cli "URL1" "URL2" "URL3"
```

### Playlist

```bash
yt-transcript-cli "https://www.youtube.com/playlist?list=PLAYLIST_ID"
```

Public and unlisted playlists are supported. Private playlists are not accessible.

### From a file

```bash
yt-transcript-cli -f urls.txt
```

Where `urls.txt` contains one URL per line. Lines starting with `#` are ignored.

### Interactive mode

```bash
yt-transcript-cli -i
```

Or just run with no arguments:

```bash
yt-transcript-cli
```

This opens a REPL where you can paste URLs one at a time, then press Enter on an empty line to process them all.

#### REPL commands

| Command          | Description          |
| ---------------- | -------------------- |
| `/help`, `/h`    | Show help            |
| `/status`, `/s`  | Show pending URLs    |
| `/clear`, `/c`   | Clear pending URLs   |
| `/process`, `/p` | Process pending URLs |
| `/quit`, `/q`    | Exit                 |

### Options

| Flag                  | Description                              | Default                 |
| --------------------- | ---------------------------------------- | ----------------------- |
| `-o`, `--output-dir`  | Output directory for transcript files    | `.` (current directory) |
| `--format`           | File representation: `text` or `json`    | `text`                  |
| `-l`, `--lang`        | Language code (e.g., `en`, `es`)         | auto-detect             |
| `-q`, `--quiet`       | Suppress progress; keep batch paths      | off                     |
| `-d`, `--delay`       | Seconds between requests (rate limiting) | `1.5`                   |
| `-f`, `--file`        | Read URLs from a file                    | -                       |
| `-i`, `--interactive` | Force interactive REPL mode              | -                       |

### Supported URL formats

- `https://www.youtube.com/watch?v=VIDEO_ID`
- `https://youtu.be/VIDEO_ID`
- `https://youtube.com/shorts/VIDEO_ID`
- `https://youtube.com/embed/VIDEO_ID`
- `https://www.youtube.com/playlist?list=PLAYLIST_ID`
- Plain video ID (11 characters)

### Behavior

- Files use `transcript_{VIDEO_ID}.txt` for text or `transcript_{VIDEO_ID}.json` for JSON in the output directory.
- Existing files for the selected format are reused without fetching or rewriting.
- Each saved or reused file's path is printed once to stdout, including with `--quiet`.
- Paths follow `--output-dir`: relative directories produce relative paths; absolute directories produce absolute paths.
- Playlists are expanded to individual videos. Repeated video occurrences produce repeated paths in processing order.
- A rate limit delay is applied between requests (configurable with `-d`), except after cached or final results.
- Text files contain one continuous block of text. JSON files contain timestamped segments.

### Paths for automation

In batch mode, use `--quiet` for one nonempty path line per saved or cached video occurrence:

```bash
yt-transcript-cli --format json --quiet --output-dir transcripts "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

Both the first successful run and a matching cached rerun print:

```text
transcripts/transcript_dQw4w9WgXcQ.json
```

Stdout reports the file path; read the JSON from that file. Failed videos emit no path.
Errors remain on stderr; without `--quiet`, progress, skip notices, and batch summaries
also go to stderr, while stdout includes separator blank lines. Interactive mode keeps
its human-facing prompts and summaries.

Batch exit statuses are `0` for success (including an all-cached batch), `1` when
nothing succeeds or is cached, and `2` for partial success.

### Cache limitations

Text and JSON have separate cache files. Requesting JSON when only text is cached
requires a new fetch from YouTube; text lacks the original timing data. The same
applies to requesting text when only JSON is cached.

Cache reuse trusts file existence and does not validate contents or distinguish requested
languages. Use a different output directory or remove the matching file to fetch again
with a different language. Python callers of the CLI helper can retain the existing
`process_video(..., skip_existing=False)` behavior to force a rewrite.

## Use as a library

```python
from yt_transcript import fetch_transcript, to_text, parse_youtube_url

video_id = parse_youtube_url("https://www.youtube.com/watch?v=VIDEO_ID")
segments = fetch_transcript(video_id)
text = to_text(segments)
```

`fetch_transcript()` already returns the original timestamped segment dictionaries,
including `text`, `start`, and `duration`. Use those segments directly for research or
JSON serialization; `to_text()` joins their text for callers that need continuous prose.
The CLI's `--format` option does not change this library API.

### Available functions

| Function                                | Description                         |
| --------------------------------------- | ----------------------------------- |
| `parse_youtube_url(url)`                | Extract video ID from a YouTube URL |
| `fetch_transcript(video_id, lang=None)` | Fetch transcript segments           |
| `to_text(segments)`                     | Convert segments to plain text      |
| `is_playlist_url(url)`                  | Check if a URL contains a playlist  |
| `fetch_playlist_video_ids(url)`         | Get all video IDs from a playlist   |
