"""
YouTube utility functions

TODO: Fix wrapepr function and parse out the backfill a bit
"""
import logging

from pytube import YouTube
from typing import Any, Dict, List, Optional
from youtube_transcript_api import YouTubeTranscriptApi


def get_transcript_from_id(
    video_id: str, chunk_size: float
) -> Optional[List[Dict[str, Any]]]:
    """
    Gets the transcript from a YouTube video ID. It also returns video information

    Args:
        video_id: The YouTube video ID.
        chunk_size: The chunk size in seconds for each text snippet

    Returns:
        The transcript as a list of dicts where each dict is a chunk of text
            defined as: {"text": [TEXT], "start": [START_TIME], "duration": [DURATION]}
    """
    try:
        response = YouTubeTranscriptApi.get_transcript(video_id)
    except Exception as e:
        print(f"Error getting transcript for YouTube Video ID {video_id}: {e}")
        return None

    # Join the transcript into chunks of chunk_size seconds.
    # Must look at "start" of each entry in transcript and join
    # together until the next entry is greater than chunk_size.
    start = 0.0
    end = chunk_size
    text = ""
    transcript = list()
    for entry in response:
        if entry["start"] < end:
            text += " "
            text += entry["text"]
        else:
            transcript.append({"text": text, "start": start, "duration": chunk_size})
            start = end
            end += chunk_size
            text = entry["text"]

    return transcript


def get_video_info(url: str) -> Optional[Dict[str, Any]]:
    """Get information about  a YouTube video.

    Args:
        url (str): The URL of the YouTube video.

    Returns:
        video_info
    """
    try:
        # Initialize the YouTube object with the video URL
        yt = YouTube(url)

        publish_date = yt.publish_date
        video_id = yt.video_id
        title = yt.title
        description = yt.description
        channel_name = yt.author

        # Return object
        video_info = {
            "url": url,
            "id": video_id,
            "title": title,
            "description": description,
            "channel_name": channel_name,
            "publish_date": publish_date,
        }

        return video_info
    except Exception as e:
        logging.error(f"Error getting publish date for {url}: {e}")
        return None


def create_snippets(
    videos: List[Dict[str, Any]], min_words: int = 0
) -> List[Dict[str, Any]]:
    """
    Create publishable snippets from a list of videos. Each video containts a list of
    transcript snippets. This function will create a record for each snippet.

    Args:
        videos: A list of videos. Each video is a dict with at least `transcript` key.
        min_words: The minimum number of words in a snippet to be included.

    Returns:
        records: A list of generic records. Each record is a dict with `attributes`
            and `text` keys.
    """
    records = list()
    for video in videos:
        if not video["transcript"]:
            continue
        # create a record for each transcript line
        for snippet in video["transcript"]:
            n_words = len(snippet["text"].split())
            if n_words < min_words:
                continue
            attributes = {
                "source": "youtube",
                "video_id": video["id"],
                "title": video["title"],
                "url_base": video["url"],
                "url": f"{video['url']}&t={snippet['start']}",
                "start": str(snippet["start"]),
                "duration": str(snippet["duration"]),
                "channel": video["channel"],
                "publish_date": video["publish_date"].strftime("%Y-%m-%d"),
            }
            text = snippet["text"]
            record = {"attributes": attributes, "text": text}
            records.append(record)

    return records


def extract_transcript_snippets_from_url(
    url: str, min_words: int = 0, chunk_size: float = 300.0
) -> List[Dict[str, Any]]:
    """
    Parse a YouTube video from a URL. By:
    1. Getting video information / metadata
    2. Getting the transcript
    3. Explode the transcript into chunks of text

    Return a list of dicts with the video information and the transcript snippets.

    Args:
        url: The URL of the YouTube video.
        min_words: The minimum number of words in a snippet to be included.
        chunk_size: The chunk size in seconds for each text snippet

    Returns:
        video_snippets: A list of dicts containing each transcript snippet
    """
    video_info = get_video_info(url)
    if not video_info:
        logging.error(f"Error getting video info for {url}")
        return None

    # Get the transcript
    try:
        transcript = get_transcript_from_id(video_info["video_id"], chunk_size)
    except Exception as e:
        logging.error(f"Error getting transcript for {url}: {e}")
        return None

    if not transcript:
        logging.error(f"No transcript found for {url}")
        return None

    # Add the transcript to the video info
    video_info["transcript"] = transcript

    # Create a record for each transcript snippet
    video_snippets = create_snippets([video_info], min_words=min_words)

    return video_snippets
