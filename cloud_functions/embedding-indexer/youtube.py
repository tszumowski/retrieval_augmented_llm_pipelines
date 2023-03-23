"""
YouTube utility functions
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
            "video_id": video_id,
            "title": title,
            "description": description,
            "channel_name": channel_name,
            "publish_date": publish_date,
        }

        return video_info
    except Exception as e:
        logging.error(f"Error getting publish date for {url}: {e}")
        return None
