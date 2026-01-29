#!/usr/bin/env python3
"""
CLI tool to fetch YouTube transcripts and save to text files.

Usage:
    # Single URL
    yt-transcript "https://www.youtube.com/watch?v=VIDEO_ID"

    # Multiple URLs
    yt-transcript "URL1" "URL2" "URL3"

    # Playlist URL
    yt-transcript "https://www.youtube.com/playlist?list=PLAYLIST_ID"

    # From file (one URL per line)
    yt-transcript -f urls.txt

    # Interactive REPL mode
    yt-transcript -i
"""
import argparse
import sys
import time
from pathlib import Path

from yt_transcript import (
    parse_youtube_url,
    fetch_transcript,
    to_text,
    is_playlist_url,
    fetch_playlist_video_ids,
)

# Default output directory (current working directory)
DEFAULT_OUTPUT_DIR = "."

# Default delay between fetches (seconds) to avoid rate limiting
DEFAULT_DELAY = 1.5

REPL_HELP = """
YouTube Transcript Fetcher - Commands
=====================================

Paste URLs:
  - Paste YouTube video URLs or playlist URLs (one per line)
  - Playlists are automatically expanded to individual videos

Commands:
  /help, /h     Show this help message
  /status, /s   Show pending URLs
  /clear, /c    Clear all pending URLs
  /process, /p  Process all pending URLs now
  /quit, /q     Exit the program

Processing:
  - Press Enter on an empty line to process all pending URLs
  - Or use /process to process immediately

Supported URL formats:
  - youtube.com/watch?v=VIDEO_ID
  - youtu.be/VIDEO_ID
  - youtube.com/shorts/VIDEO_ID
  - youtube.com/embed/VIDEO_ID
  - youtube.com/playlist?list=PLAYLIST_ID
  - Plain video ID (11 characters)
"""


def process_video(video_id: str, lang: str | None, output_dir: Path, quiet: bool, skip_existing: bool = True) -> str:
    """
    Process a single video ID and save transcript to file.
    Returns 'success', 'skipped', or 'failed'.
    """
    def log(msg: str):
        if not quiet:
            print(msg, file=sys.stderr)

    def progress(msg: str):
        """Print progress update on same line."""
        if not quiet:
            print(f"\r  {msg}", end="", flush=True, file=sys.stderr)

    def progress_done():
        """Clear progress line."""
        if not quiet:
            print("\r" + " " * 60 + "\r", end="", file=sys.stderr)

    output_path = output_dir / f"transcript_{video_id}.txt"

    # Check if transcript already exists
    if skip_existing and output_path.exists():
        log(f"Video ID: {video_id}")
        log(f"Skipped (already exists): {output_path}")
        return 'skipped'

    log(f"Video ID: {video_id}")
    progress("Fetching transcript...")

    try:
        segments = fetch_transcript(video_id, lang)
    except Exception as e:
        progress_done()
        print(f"Error fetching transcript for {video_id}: {type(e).__name__}: {e}", file=sys.stderr)
        return 'failed'

    progress("Processing transcript...")
    text = to_text(segments)

    if not text:
        progress_done()
        print(f"Error: Transcript is empty for {video_id}", file=sys.stderr)
        return 'failed'

    progress("Saving file...")
    output_path.write_text(text, encoding="utf-8")
    progress_done()
    log(f"Saved to: {output_path}")
    print(str(output_path))

    return 'success'


def expand_url(url: str, quiet: bool) -> list[str]:
    """
    Expand a URL to a list of video IDs.
    For playlists, returns all video IDs in the playlist.
    For single videos, returns a single-item list.
    """
    def log(msg: str):
        if not quiet:
            print(msg, file=sys.stderr)

    if is_playlist_url(url):
        # Check if it's a video URL with a playlist parameter
        has_video_id = '&v=' in url or '?v=' in url

        if has_video_id:
            log(f"URL contains playlist parameter, checking for playlist videos...")
        else:
            log(f"Checking playlist...")

        try:
            video_ids = fetch_playlist_video_ids(url)
            log(f"Found {len(video_ids)} videos in playlist")
            return video_ids
        except Exception as e:
            # If playlist fetch fails but URL has a video ID, fall back to single video
            if has_video_id:
                log(f"Playlist not accessible, falling back to single video")
                try:
                    return [parse_youtube_url(url)]
                except ValueError:
                    pass
            else:
                print(f"Error: Could not fetch playlist (may be private or invalid): {e}", file=sys.stderr)
            return []
    else:
        try:
            return [parse_youtube_url(url)]
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return []


def process_urls(
    urls: list[str],
    lang: str | None,
    output_dir: Path,
    quiet: bool,
    delay: float = DEFAULT_DELAY
) -> tuple[int, int, int, int]:
    """
    Process a list of URLs (expanding playlists).
    Returns (success_count, skipped_count, total_videos, failed_urls).
    """
    def log(msg: str):
        if not quiet:
            print(msg, file=sys.stderr)

    # Expand all URLs to video IDs, tracking failures
    all_video_ids: list[str] = []
    failed_urls = 0
    for url in urls:
        video_ids = expand_url(url, quiet)
        if video_ids:
            all_video_ids.extend(video_ids)
        else:
            failed_urls += 1

    if not all_video_ids:
        return 0, 0, 0, failed_urls

    total = len(all_video_ids)
    success_count = 0
    skipped_count = 0

    for i, video_id in enumerate(all_video_ids, 1):
        # Show progress for multiple videos
        if total > 1:
            log(f"[{i}/{total}]")

        result = process_video(video_id, lang, output_dir, quiet)
        if result == 'success':
            success_count += 1
        elif result == 'skipped':
            skipped_count += 1

        if not quiet:
            print()

        # Add delay between requests to avoid rate limiting (skip after last one)
        # Don't delay after skipped videos
        if i < total and delay > 0 and result != 'skipped':
            for remaining in range(int(delay * 10), 0, -1):
                if not quiet:
                    print(f"\r  Rate limit delay: {remaining / 10:.1f}s remaining...", end="", flush=True, file=sys.stderr)
                time.sleep(0.1)
            if not quiet:
                print("\r" + " " * 50 + "\r", end="", file=sys.stderr)

    return success_count, skipped_count, total, failed_urls


def run_repl(lang: str | None, output_dir: Path, quiet: bool, delay: float = DEFAULT_DELAY):
    """
    Run interactive REPL mode for pasting URLs.
    """
    print("YouTube Transcript Fetcher - Interactive Mode")
    print("=" * 50)
    print("Paste YouTube URLs (one per line). Playlists supported.")
    print(f"Rate limit delay: {delay}s between requests")
    print("Type /help for commands, empty line to process.")
    print("=" * 50)
    print()

    pending_urls: list[str] = []

    while True:
        try:
            if pending_urls:
                count = len(pending_urls)
                prompt = f"{count} URL(s) pending - add more or press Enter to process\n> "
            else:
                prompt = "> "
            line = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        # Handle commands
        cmd = line.lower()

        if cmd in ('/q', '/quit', 'q', 'quit', 'exit'):
            break

        if cmd in ('/h', '/help', 'help'):
            print(REPL_HELP)
            continue

        if cmd in ('/s', '/status', 'status'):
            if pending_urls:
                print(f"\nPending URLs ({len(pending_urls)}):")
                for i, url in enumerate(pending_urls, 1):
                    print(f"  {i}. {url}")
                print()
            else:
                print("No pending URLs.")
            continue

        if cmd in ('/c', '/clear', 'clear'):
            pending_urls.clear()
            print("Cleared pending URLs.")
            continue

        if cmd in ('/p', '/process', 'process'):
            line = ''  # Fall through to processing

        # Empty line or /process triggers processing
        if not line:
            if not pending_urls:
                continue

            print(f"\nProcessing {len(pending_urls)} URL(s)...")
            print("-" * 30)

            success, skipped, total, failed_urls = process_urls(pending_urls, lang, output_dir, quiet, delay)

            print("-" * 30)
            parts = []
            if success > 0:
                parts.append(f"{success} fetched")
            if skipped > 0:
                parts.append(f"{skipped} skipped")
            if total - success - skipped > 0:
                parts.append(f"{total - success - skipped} failed")
            if failed_urls > 0:
                parts.append(f"{failed_urls} URL(s) could not resolve")

            if parts:
                print(f"Completed: {', '.join(parts)}")
            else:
                print("Completed: nothing to process")
            print()

            pending_urls.clear()
            continue

        # Skip if it looks like an unknown command
        if line.startswith('/'):
            print(f"Unknown command: {line}. Type /help for available commands.")
            continue

        # Add URL to pending list
        pending_urls.append(line)
        print(f"  Added: {line}")


def main():
    parser = argparse.ArgumentParser(
        description="Fetch YouTube video transcripts and save to text files.",
        epilog="Supports video URLs, playlist URLs, and plain video IDs."
    )
    parser.add_argument(
        "urls",
        nargs="*",
        help="YouTube video/playlist URL(s) or video ID(s)"
    )
    parser.add_argument(
        "-i", "--interactive",
        action="store_true",
        help="Run in interactive REPL mode"
    )
    parser.add_argument(
        "-f", "--file",
        help="Read URLs from a file (one per line)"
    )
    parser.add_argument(
        "-o", "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory for transcripts (default: {DEFAULT_OUTPUT_DIR})"
    )
    parser.add_argument(
        "-l", "--lang",
        help="Language code for transcript (e.g., 'en', 'es')"
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress progress messages"
    )
    parser.add_argument(
        "-d", "--delay",
        type=float,
        default=DEFAULT_DELAY,
        help=f"Delay between requests in seconds (default: {DEFAULT_DELAY})"
    )

    args = parser.parse_args()

    # Ensure output directory exists
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Collect URLs from all sources
    urls: list[str] = list(args.urls) if args.urls else []

    # Read URLs from file if specified
    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"Error: File not found: {args.file}", file=sys.stderr)
            sys.exit(1)
        with open(file_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    urls.append(line)

    # Determine mode
    if args.interactive or (not urls and not args.file):
        run_repl(args.lang, output_dir, args.quiet, args.delay)
    elif not urls:
        print("Error: No URLs provided. Use -i for interactive mode.", file=sys.stderr)
        sys.exit(1)
    else:
        # Batch mode
        success, skipped, total, failed_urls = process_urls(urls, args.lang, output_dir, args.quiet, args.delay)

        if (total > 1 or failed_urls > 0 or skipped > 0) and not args.quiet:
            parts = []
            if success > 0:
                parts.append(f"{success} fetched")
            if skipped > 0:
                parts.append(f"{skipped} skipped")
            if total - success - skipped > 0:
                parts.append(f"{total - success - skipped} failed")
            if failed_urls > 0:
                parts.append(f"{failed_urls} URL(s) could not resolve")
            if parts:
                print(f"Completed: {', '.join(parts)}", file=sys.stderr)

        if success == 0 and skipped == 0:
            sys.exit(1)
        elif success < total - skipped or failed_urls > 0:
            sys.exit(2)  # Partial success


if __name__ == "__main__":
    main()
