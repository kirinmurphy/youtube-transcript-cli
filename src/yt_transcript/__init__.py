"""
yt-transcript - Fetch YouTube video transcripts.
"""
__version__ = "0.1.2"

from .core import (
    parse_youtube_url,
    fetch_transcript,
    to_text,
    is_playlist_url,
    fetch_playlist_video_ids,
)

__all__ = [
    "parse_youtube_url",
    "fetch_transcript",
    "to_text",
    "is_playlist_url",
    "fetch_playlist_video_ids",
]
