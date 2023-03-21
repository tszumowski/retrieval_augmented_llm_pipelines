"""
This script scrapes your Liked Videos playlist and adds them to the database after
transcribing, clipping, and embedding.

Usage:
1. Go to: https://www.youtube.com/playlist?list=LL
2. Scroll to bottom.
3. Save page as HTML.
4. Create a CSV file with single column entries any keywords in the title or account
    name you want to exclude from the scrape.
5. Run the script with the following command:
    python backfill_youtube.py \
        --min_date=[YYYY-MM-DD] \
        --max_date=[YYYY-MM-DD]

    Note: The min_date and max_date are optional. If not provided, the script will
    scrape all videos in the playlist.
"""

import argparse
from bs4 import BeautifulSoup
import csv
import datetime
import os
import re
import sys
import time
from typing import Any, Dict, List, Optional, Tuple
from concurrent import futures
from google.cloud import pubsub_v1
from tqdm import tqdm
from uuid import uuid4

from youtube_transcript_api import YouTubeTranscriptApi


def get_transcript_from_url(
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


# Main script part
if __name__ == "__main__":
    # parse command line arguments
    # parser = argparse.ArgumentParser()
    # parser.add_argument("--min_date", help="Minimum date to scrape (YYYY-MM-DD)", default=None)
    # parser.add_argument("--max_date", help="Maximum date to scrape (YYYY-MM-DD)", default=None)
    # parser.add_argument("--input", help="File to parse")

    # Simple test
    transcript = get_transcript_from_url("ok0SDdXdat8", 300.0)
    from pprint import pprint

    pprint(transcript)
