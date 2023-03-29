"""
This script scrapes your Liked Videos playlist and adds them to the database after
transcribing, clipping, and embedding.

Usage:
1. Go to: https://www.youtube.com/playlist?list=LL
2. Scroll to bottom.
3. Save page as HTML. **Specifically as MHT type so it is fully rendered.**
4. Create a CSV file with single column entries any keywords in the title or account
    name you want to exclude from the scrape.
5. Run the script. Example Usage:
        python3 scripts/backfill/backfill_youtube.py \
            --input_file=youtube_video_likes.mht \
            --output_file=youtube_video_likes-parsed.jsonl \
            --skip_file=skip.csv \
            --min_tokens=100

    Note: The min_date and max_date are optional. If not provided, the script will
    scrape all videos in the playlist. See the --help flag for more details.
"""

import argparse
from bs4 import BeautifulSoup
import datetime
import json
import logging
import os
import quopri
import sys
from concurrent import futures
from google.cloud import pubsub_v1
from tqdm import tqdm
from typing import Any, Dict, List, Optional

# add ../cloud_functions to path to access youtube utils
sys.path.append(
    os.path.join(os.path.dirname(__file__), "../../cloud_functions/url-scraper")
)

# import get_transcript_from_url from youtube utils
from youtube import (
    create_snippets,
    get_transcript_by_tokens,
    get_video_info_with_error_handling,
)

# Static variables
DEFAULT_N_THREADS = int(os.cpu_count() * 2)


def extract_video_links_from_likes_mht(mht_file: str) -> List[str]:
    """
    Extracts video links from a YouTube likes mht file.

    Args:
        mht_file: The path to the mht file.

    Returns:
        videos: A list of video URLs
    """
    # open the HTML file in read mode
    with open(mht_file, "r") as file:
        # read the contents of the file
        html = file.read()

        # Decode to get rid of spurious stuff coming from mht file
        html = quopri.decodestring(html).decode("utf-8")

    # Load the HTML file into a BeautifulSoup object
    soup = BeautifulSoup(html, "html.parser")

    link_objs = soup.find_all("a", {"id": "video-title"})

    # parse out videos one by one
    video_links = list()
    for obj in link_objs:
        try:
            video_links.append(obj["href"].split("&")[0])
        except Exception as e:
            logging.error(f"Error parsing video link: {e}")

    logging.info(
        f"Successfully parsed {len(video_links)} video URLs out of {len(link_objs)} candidates."
    )

    return video_links


def publish_video_snippets(
    project_id: str,
    topic_name: str,
    records: List[Dict[str, Any]],
) -> List[futures.Future]:
    """
    Publishes video snippets to a Pub/Sub topic.

    Args:
        project_id: The GCP project ID.
        topic_name: The name of the Pub/Sub topic.
        records: A list of records to publish.

    Returns:
        publish_futures: A list of futures for the publish events.

    """
    # Initialize a Publisher client.
    publisher = pubsub_v1.PublisherClient()

    # Define the topic path.
    topic_path = publisher.topic_path(project_id, topic_name)
    logging.info(f"Topic path: {topic_path}")

    # Publish messages to the topic, extracting the main body text from the
    # HTML file.
    logging.info(f"Publishing {len(records)} records to Pub/Sub...")
    total_processed = 0
    publish_futures = list()
    for record in tqdm(records):
        text = record["text"]
        attributes = record["attributes"]
        future = publisher.publish(topic_path, data=text.encode("utf-8"), **attributes)
        publish_futures.append(future)
        total_processed += 1

    # Wait for all the publish futures to resolve before reporting complete.
    print(f"Waiting for {len(publish_futures)} publish events to complete ...")
    futures.wait(publish_futures, return_when=futures.ALL_COMPLETED)

    print(f"Done! Published {total_processed} / {len(records)} video snippets.")

    return publish_futures


def filter_videos_by_skip_file(
    videos: List[Dict[str, Any]], skip_file: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Filters out videos that are in the skip file.

    Args:
        videos: A list of videos.
        skip_file: The path to the CSV skip file

    Returns:
        videos: A list of videos.
    """
    if skip_file is None:
        logging.warning("No skip file provided. Skipping filtering.")
        return videos

    # Load the skip file
    with open(skip_file, "r") as file:
        skip_ids = [line.strip() for line in file.readlines()]

    # Make all IDs lowercase
    skip_ids = [id.lower() for id in skip_ids]

    # look for any skip_id in title or channel of video
    # the skip_id can be in any part of the title or any part of the channel
    keep_videos = list()
    for video in videos:
        # check if video["title"] or video["channel"] contains any of the skip_ids
        if any(skip_id in video["title"].lower() for skip_id in skip_ids) or any(
            skip_id in video["channel"].lower() for skip_id in skip_ids
        ):
            continue
        keep_videos.append(video)

    return keep_videos


def main(
    input_file: str,
    output_file: str,
    min_date: Optional[datetime.datetime] = None,
    max_date: Optional[datetime.datetime] = None,
    min_tokens: int = 0,
    n_threads: int = DEFAULT_N_THREADS,
    chunk_size: int = 300,
    skip_file: Optional[str] = None,
):
    """
    Main function.

    Args:
        input_file: The path to the mht file.
        output_file: The path to the output file.
        min_date: The minimum date to scrape.
        max_date: The maximum date to scrape.
        min_tokens: The minimum number of tokens in the transcript snippet needed to publish
        n_threads: The number of threads to use.
        chunk_size: The number of tokens per chunk in transcript.
        skip_file: The path to CSV file, single column, listing keywords from channel
            or titles to skip (case insensitive).
    """
    # extract videos from mht file
    logging.info(f"Extracting videos from {input_file}...")
    video_links = extract_video_links_from_likes_mht(input_file)
    logging.info(f"Found {len(video_links)} videos in mht file.")
    if len(video_links) == 0:
        logging.info("None found. Exiting.")
        return

    # Get video info in parallel for all videos using joblib threads
    logging.info(f"Getting video info for {len(video_links)} video candidates...")
    with futures.ThreadPoolExecutor(max_workers=n_threads) as executor:
        results = executor.map(get_video_info_with_error_handling, video_links)

    # Filter out any failed results and create the final list of videos
    videos = [video for video in results if video is not None]
    logging.info(
        f"Successfully extracted information for {len(videos)}/{len(video_links)} videos candidates."
    )

    # Filter videos that match any entry in the skip file
    if skip_file:
        logging.info(f"Filtering videos that match keywords in {skip_file}...")
        videos = filter_videos_by_skip_file(videos, skip_file)
        logging.info(f"Found {len(videos)} videos after filtering.")

    # filter out videos that don't meet date criteria
    logging.info("Filtering videos by date...")
    if min_date:
        videos = [v for v in videos if min_date <= v["publish_date"]]
    if max_date:
        videos = [v for v in videos if v["publish_date"] <= max_date]
    if min_date and max_date:
        logging.info(f"Found {len(videos)} videos between {min_date} and {max_date}.")

    # Transcribe, in parallel, using get_transcript_by_tokens, passing in chunk_size argument
    logging.info(f"Transcribing {len(videos)} videos...")
    with futures.ThreadPoolExecutor(max_workers=n_threads) as executor:
        transcripts = executor.map(
            get_transcript_by_tokens,
            [v["id"] for v in videos],
            [chunk_size] * len(videos),
        )
    logging.info("Done transcribing")

    # Add transcripts to videos
    valid_transcript_cnt = 0
    for video, transcript in zip(videos, transcripts):
        video["transcript"] = None
        if transcript is None:
            logging.warning(f"Transcript for {video['id']} is None.")
        else:
            video["transcript"] = transcript
            valid_transcript_cnt += 1
    logging.info(
        f"Found transcripts for {valid_transcript_cnt} of {len(videos)} videos."
    )
    # remove videos without transcripts
    videos = [v for v in videos if v["transcript"] is not None]

    # Need to take each transcript record and create a unique publish record
    records = create_snippets(videos, min_tokens)

    # write to JSONlines output file, casting all datetime objects to strings
    logging.info(f"Writing to {output_file}...")
    with open(output_file, "w") as file:
        # write each record as a JSON line
        for record in records:
            file.write(json.dumps(record, default=str))
            file.write("\n")
    logging.info("Done.")


# Main script part
if __name__ == "__main__":
    # initialize logging with INFO level and a timestamp
    logging.basicConfig(
        format="%(asctime)s %(levelname)s: %(message)s", level=logging.INFO
    )

    parser = argparse.ArgumentParser()
    parser.add_argument("--input_file", help="File to parse", required=True)
    parser.add_argument(
        "--output_file", help="File to write to", type=str, required=True
    )
    parser.add_argument(
        "--min_date", help="Minimum date to scrape (YYYY-MM-DD)", type=str, default=None
    )
    parser.add_argument(
        "--max_date", help="Maximum date to scrape (YYYY-MM-DD)", type=str, default=None
    )
    parser.add_argument(
        "--min_tokens",
        type=int,
        default=30,
        help="Minimum number of tokens in a file required to be indexed",
    )
    # add chunk_size argument
    parser.add_argument(
        "--chunk_size",
        type=int,
        default=375,
        help="Number of tokens per chunk in transcript",
    )
    parser.add_argument(
        "--skip_file",
        type=str,
        default=None,
        help="Single column CSV file with channels and title keywords to skip",
    )

    # cast min_date and max_date to datetime objects
    args = parser.parse_args()
    min_date = max_date = None
    if args.min_date:
        min_date = datetime.datetime.strptime(args.min_date, "%Y-%m-%d")
    if args.max_date:
        max_date = datetime.datetime.strptime(args.max_date, "%Y-%m-%d")

    # call main function
    main(
        args.input_file,
        args.output_file,
        min_date=min_date,
        max_date=max_date,
        min_tokens=args.min_tokens,
        chunk_size=args.chunk_size,
        skip_file=args.skip_file,
    )
