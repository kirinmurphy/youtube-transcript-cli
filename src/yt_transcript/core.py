"""
Core transcript fetching logic.
"""
import re
import requests
from youtube_transcript_api import YouTubeTranscriptApi


def is_playlist_url(url: str) -> bool:
    """Check if URL is a YouTube playlist."""
    return 'list=' in url or '/playlist' in url


def extract_playlist_id(url: str) -> str | None:
    """Extract playlist ID from a YouTube URL."""
    match = re.search(r'[?&]list=([a-zA-Z0-9_-]+)', url)
    return match.group(1) if match else None


def fetch_playlist_video_ids(playlist_url: str) -> list[str]:
    """
    Fetch all video IDs from a YouTube playlist.

    Args:
        playlist_url: YouTube playlist URL

    Returns:
        List of video IDs in the playlist.
    """
    playlist_id = extract_playlist_id(playlist_url)
    if not playlist_id:
        raise ValueError(f"Could not extract playlist ID from: {playlist_url}")

    # Fetch the playlist page
    url = f"https://www.youtube.com/playlist?list={playlist_id}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    # Extract video IDs from the page
    # YouTube embeds video IDs in the HTML in various places
    video_ids = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', response.text)

    # Remove duplicates while preserving order
    seen = set()
    unique_ids = []
    for vid in video_ids:
        if vid not in seen:
            seen.add(vid)
            unique_ids.append(vid)

    if not unique_ids:
        raise ValueError(f"No videos found in playlist: {playlist_id}")

    return unique_ids


def parse_youtube_url(url: str) -> str:
    """
    Extract video_id from various YouTube URL formats.

    Supported formats:
    - https://www.youtube.com/watch?v=VIDEO_ID
    - https://youtu.be/VIDEO_ID
    - https://youtube.com/shorts/VIDEO_ID
    - https://youtube.com/embed/VIDEO_ID
    - VIDEO_ID (plain video ID)

    Returns the video_id string.
    Raises ValueError if URL format is not recognized.

    Note: For playlist URLs, use fetch_playlist_video_ids() instead.
    """
    url = url.strip()

    # Pattern for standard watch URLs: youtube.com/watch?v=VIDEO_ID
    watch_match = re.search(r'[?&]v=([a-zA-Z0-9_-]{11})', url)
    if watch_match:
        return watch_match.group(1)

    # Pattern for youtu.be/VIDEO_ID
    short_match = re.search(r'youtu\.be/([a-zA-Z0-9_-]{11})', url)
    if short_match:
        return short_match.group(1)

    # Pattern for youtube.com/shorts/VIDEO_ID or youtube.com/embed/VIDEO_ID
    path_match = re.search(r'youtube\.com/(?:shorts|embed)/([a-zA-Z0-9_-]{11})', url)
    if path_match:
        return path_match.group(1)

    # Check if input is already a plain video ID (11 chars, alphanumeric with _ and -)
    if re.match(r'^[a-zA-Z0-9_-]{11}$', url):
        return url

    raise ValueError(f"Could not extract video ID from: {url}")


def fetch_transcript(video_id: str, lang: str | None = None) -> list[dict]:
    """
    Fetch transcript segments from YouTube.

    Args:
        video_id: YouTube video ID
        lang: Optional language code (e.g., 'en', 'es')

    Returns:
        List of segment dictionaries with 'text', 'start', 'duration' keys.
    """
    if lang:
        fetched = YouTubeTranscriptApi().fetch(video_id, languages=[lang])
    else:
        fetched = YouTubeTranscriptApi().fetch(video_id)
    return fetched.to_raw_data()


def to_text(segments: list[dict]) -> str:
    """
    Convert transcript segments to plain text.

    Args:
        segments: List of segment dictionaries with 'text' key

    Returns:
        Continuous transcript text (single block for LLM processing).
    """
    return " ".join(s.get("text", "") for s in segments).strip()
