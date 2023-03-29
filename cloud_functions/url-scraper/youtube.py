"""
YouTube utility functions
"""
import re
import logging

from pytube import YouTube
from typing import Any, Dict, List, Optional
from youtube_transcript_api import YouTubeTranscriptApi
from retry import retry
from retry.api import retry_call
from tokenization import split_by_tokenization, tiktoken_len, CHUNK_OVERLAP, CHUNK_SIZE

DEFAULT_RETRY_BACKOFF = 2
DEFAULT_RETRY_DELAY = 1
DEFAULT_RETRY_TRIES = 5


def is_youtube_url(url):
    # Regex from https://stackoverflow.com/a/7936523
    youtube_pattern = re.compile(
        r"(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})"
    )  # noqa: E501

    return youtube_pattern.match(url)


def get_transcript_by_time(
    video_id: str, chunk_size: float
) -> Optional[List[Dict[str, Any]]]:
    """
    Gets the transcript from a YouTube video ID. It also returns video information.
    It chunks the transcript by the time in each chunk.

    Args:
        video_id: The YouTube video ID.
        chunk_size: The chunk size in seconds for each text snippet

    Returns:
        The transcript as a list of dicts where each dict is a chunk of text
            defined as: {"text": [TEXT], "start": [START_TIME], "duration": [DURATION]}
    """
    try:
        response = retry_call(
            YouTubeTranscriptApi.get_transcript,
            fargs=[video_id],
            tries=DEFAULT_RETRY_TRIES,
            delay=DEFAULT_RETRY_DELAY,
            backoff=DEFAULT_RETRY_BACKOFF,
        )
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
            # determine actual duration of text
            duration = int(entry["start"] - start)
            transcript.append({"text": text, "start": int(start), "duration": duration})
            start = end
            end += int(entry["start"])
            text = entry["text"]
    # If there is any text left over, add it to the transcript
    if text:
        end_time = response[-1]["start"] + response[-1]["duration"]
        duration = int(end_time - start)
        transcript.append({"text": text, "start": int(start), "duration": duration})

    return transcript


def get_transcript_by_tokens(
    video_id: str, chunk_size: int = CHUNK_SIZE, chunk_overlap: int = CHUNK_OVERLAP
) -> Optional[List[Dict[str, Any]]]:
    """
    Gets the transcript from a YouTube video ID. It also returns video information.
    It chunks the transcript by the number of tokens in each chunk.

    Args:
        video_id: The YouTube video ID.
        chunk_size: The chunk size in tokens for each text snippet
        chunk_overlap: The number of tokens to overlap between chunks

    Returns:
        The transcript as a list of dicts where each dict is a chunk of text
            defined as: {"text": [TEXT], "start": [START_TIME], "duration": [DURATION]}
    """
    try:
        response = retry_call(
            YouTubeTranscriptApi.get_transcript,
            fargs=[video_id],
            tries=DEFAULT_RETRY_TRIES,
            delay=DEFAULT_RETRY_DELAY,
            backoff=DEFAULT_RETRY_BACKOFF,
        )
    except Exception as e:
        print(f"Error getting transcript for YouTube Video ID {video_id}: {e}")
        return None

    # Loop through until we have enough tokens, then add to output and repeat
    start = 0.0
    text = ""
    transcript = list()
    token_cnt = 0
    for entry in response:
        # Tokenize
        records = split_by_tokenization(
            entry["text"], chunk_size=chunk_size, chunk_overlap=chunk_overlap
        )

        # Keep adding records based on n_tokens until we have enoug
        for record in records:
            if token_cnt < chunk_size:
                # When less than chunk_size, add to text and increment token_cnt
                text += " "
                text += record["text"]
                token_cnt += record["n_tokens"]
            else:
                # When we've reached chunk_size, add to output and reset
                duration = int(entry["start"] - start)
                transcript.append(
                    {"text": text, "start": int(start), "duration": duration}
                )
                start = start + duration
                token_cnt = 0
                text = record["text"]

    # If there is any text left over, add it to the transcript
    if text:
        end_time = response[-1]["start"] + response[-1]["duration"]
        duration = int(end_time - start)
        transcript.append({"text": text, "start": int(start), "duration": duration})

    return transcript


@retry(
    tries=DEFAULT_RETRY_TRIES, delay=DEFAULT_RETRY_DELAY, backoff=DEFAULT_RETRY_BACKOFF
)
def get_video_info(url: str) -> Optional[Dict[str, Any]]:
    """Get information about  a YouTube video.

    Args:
        url (str): The URL of the YouTube video.

    Returns:
        video_info
    """
    # Initialize the YouTube object with the video URL
    yt = YouTube(url)

    # Parse the video information
    publish_date = yt.publish_date
    video_id = yt.video_id
    title = yt.title
    description = yt.description
    channel_name = yt.author

    # Format as object
    video_info = {
        "url": url,
        "id": video_id,
        "title": title,
        "description": description,
        "channel": channel_name,
        "publish_date": publish_date,
    }

    return video_info


# Function to handle retries and errors when fetching video info
def get_video_info_with_error_handling(video_link):
    try:
        return get_video_info(video_link)
    except Exception as e:
        logging.error(f"Error fetching video info for {video_link}: {e}")
        return None


def create_snippets(
    videos: List[Dict[str, Any]], min_tokens: int = 0
) -> List[Dict[str, Any]]:
    """
    Create publishable snippets from a list of videos. Each video containts a list of
    transcript snippets. This function will create a record for each snippet.

    Args:
        videos: A list of videos. Each video is a dict with at least `transcript` key.
        min_tokens: The minimum number of tokens in a snippet to be included.

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
            text = snippet["text"]
            n_tokens = tiktoken_len(text)
            if n_tokens < min_tokens:
                continue
            publish_date = video["publish_date"].strftime("%Y-%m-%d")
            attributes = {
                "source": "youtube",
                "video_id": video["id"],
                "title": video["title"],
                "url_base": video["url"],
                "url": f"{video['url']}&t={snippet['start']}",
                "start": str(snippet["start"]),
                "duration": str(snippet["duration"]),
                "channel": video["channel"],
                "publish_date": publish_date,
                "date": publish_date,
                "n_tokens": n_tokens,
            }
            record = {"attributes": attributes, "text": text}
            records.append(record)

    return records


def extract_transcript_snippets_from_url(
    url: str,
    min_tokens: int = 0,
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> List[Dict[str, Any]]:
    """
    Parse a YouTube video from a URL. By:
    1. Getting video information / metadata
    2. Getting the transcript
    3. Explode the transcript into chunks of text

    Return a list of dicts with the video information and the transcript snippets.

    Args:
        url: The URL of the YouTube video.
        min_tokens: The minimum number of tokens in a snippet to be included.
        chunk_size: The chunk size in number of tokens.
        chunk_overlap: The chunk overlap in number of tokens.

    Returns:
        video_snippets: A list of dicts containing each transcript snippet
    """
    video_info = get_video_info(url)
    if not video_info:
        logging.error(f"Error getting video info for {url}")
        return None

    # Get the transcript
    try:
        transcript = get_transcript_by_tokens(
            video_info["id"], chunk_size=chunk_size, chunk_overlap=chunk_overlap
        )
    except Exception as e:
        logging.error(f"Error getting transcript for {url}: {e}")
        return None

    if not transcript:
        logging.error(f"No transcript found for {url}")
        return None

    # Add the transcript to the video info
    video_info["transcript"] = transcript

    # Create a record for each transcript snippet
    video_snippets = create_snippets([video_info], min_tokens=min_tokens)

    return video_snippets


if __name__ == "__main__":
    url = "https://www.youtube.com/watch?v=eqOfr4AGLk8"
    video_snippets = extract_transcript_snippets_from_url(url, min_tokens=0)

    # Enrich with token counts using tiktoken_len
    from tokenization import tiktoken_len
    from pprint import pprint

    for snippet in video_snippets:
        snippet["n_tokens"] = tiktoken_len(snippet["text"])

    for i, v in enumerate(video_snippets, 1):
        print(f"Snippet {i}:\n----------------\n")
        pprint(v)
        print("\n\n")
