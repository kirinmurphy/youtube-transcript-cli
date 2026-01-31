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
| `-l`, `--lang`        | Language code (e.g., `en`, `es`)         | auto-detect             |
| `-q`, `--quiet`       | Suppress progress messages               | off                     |
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

- Transcripts are saved as `transcript_{VIDEO_ID}.txt` in the output directory
- Existing transcripts are skipped automatically (won't re-download)
- Playlists are expanded to individual videos
- A rate limit delay is applied between requests (configurable with `-d`)
- Output is a single continuous block of text (no line breaks between segments)

## Use as a library

```python
from yt_transcript import fetch_transcript, to_text, parse_youtube_url

video_id = parse_youtube_url("https://www.youtube.com/watch?v=VIDEO_ID")
segments = fetch_transcript(video_id)
text = to_text(segments)
```

### Available functions

| Function                                | Description                         |
| --------------------------------------- | ----------------------------------- |
| `parse_youtube_url(url)`                | Extract video ID from a YouTube URL |
| `fetch_transcript(video_id, lang=None)` | Fetch transcript segments           |
| `to_text(segments)`                     | Convert segments to plain text      |
| `is_playlist_url(url)`                  | Check if a URL contains a playlist  |
| `fetch_playlist_video_ids(url)`         | Get all video IDs from a playlist   |
