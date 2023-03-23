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
            --output_file=youtube_video_likes-parsed.json \
            --skip_file=skip.csv \
            --project_id=liquid-champion-195421 \
            --topic_name=embedding-indexer \
            --min_words=100

    Note: The min_date and max_date are optional. If not provided, the script will
    scrape all videos in the playlist. See the --help flag for more details.
"""

import argparse
from bs4 import BeautifulSoup
import datetime
import os
import re
import sys
from typing import Any, Dict, List, Optional
from concurrent import futures
from google.cloud import pubsub_v1
from tqdm import tqdm
import logging
import quopri
import json

# add ../cloud_functions/embedding-indexer to path to access youtube utils
sys.path.append(
    os.path.join(os.path.dirname(__file__), "../../cloud_functions/embedding-indexer")
)

# import get_transcript_from_url from youtube utils
from youtube import get_transcript_from_id, get_video_info

# Static variables
DEFAULT_N_THREADS = int(os.cpu_count() * 2)


def extract_videos_from_likes_mht(mht_file: str) -> List[Dict[str, Any]]:
    """
    Extracts videos from a YouTube likes mht file.

    Args:
        mht_file: The path to the mht file.

    Returns:
        videos: A list of videos.
    """
    # open the HTML file in read mode
    with open(mht_file, "r") as file:
        # read the contents of the file
        html = file.read()

        # Decode to get rid of spurious stuff coming from mht file
        html = quopri.decodestring(html).decode("utf-8")

    # Load the HTML file into a BeautifulSoup object
    soup = BeautifulSoup(html, "html.parser")

    # find all div id "content" with class containing "ytd-playlist-video-renderer"
    # this is the div that contains the video title, channel, and date
    contents = soup.find_all(
        "div", {"id": "content", "class": re.compile("ytd-playlist-video-renderer")}
    )

    # parse out videos one by one
    videos = list()
    for content in contents:
        # extract the video-title a tag
        title = content.find("a", {"id": "video-title"})

        # get the href which is the url with split on &
        url = title.get("href").split("&")[0]

        # get the video id which is the last part of the url
        id = url.split("=")[1]

        # extract the video title text
        title = title.text.strip()

        # look in div class containing ytd-channel-name tag for channel name
        channel = content.find("div", {"class": re.compile("ytd-channel-name")})

        # Look for "a" tag with class containing "yt-simple-endpoint". Take href and split on @ to right to get channel ID
        channel_id = (
            channel.find("a", {"class": re.compile("yt-simple-endpoint")})
            .get("href")
            .split("/")[-1]
        )

        # create video object
        video = dict(url=url, title=title, id=id, channel=channel_id)

        # append to videos list
        videos.append(video)

    return videos


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
    project_id: str,
    topic_name: str,
    output_file: Optional[str] = None,
    min_date: Optional[datetime.datetime] = None,
    max_date: Optional[datetime.datetime] = None,
    min_words: int = 0,
    n_threads: int = DEFAULT_N_THREADS,
    chunk_size: int = 300,
    skip_file: Optional[str] = None,
):
    """
    Main function.

    Args:
        input_file: The path to the mht file.
        project_id: The GCP project ID.
        topic_name: The name of the Pub/Sub topic.
        output_file: The path to the output file.
        min_date: The minimum date to scrape.
        max_date: The maximum date to scrape.
        min_words: The minimum number of words in the transcript snippet needed to publish
        n_threads: The number of threads to use.
        chunk_size: The number of seconds per chunk in transcript.
        skip_file: The path to CSV file, single column, listing keywords from channel
            or titles to skip (case insensitive).
    """
    # extract videos from mht file
    logging.info(f"Extracting videos from {input_file}...")
    videos = extract_videos_from_likes_mht(input_file)
    logging.info(f"Found {len(videos)} videos in mht file.")
    if len(videos) == 0:
        logging.info("None found. Exiting.")
        return

    # Filter videos that match any entry in the skip file
    if skip_file:
        logging.info(f"Filtering videos that match keywords in {skip_file}...")
        videos = filter_videos_by_skip_file(videos, skip_file)
        logging.info(f"Found {len(videos)} videos after filtering.")

    import random

    videos = random.sample(videos, 3)

    # Get publish date in parallel for all videos using joblib threads
    logging.info("Getting publish dates for videos...")
    with futures.ThreadPoolExecutor(max_workers=n_threads) as executor:
        video_infos = executor.map(get_video_info, [v["url"] for v in videos])
    video_infos = list(video_infos)
    publish_dates = [v["publish_date"] for v in video_infos]
    logging.info("Done. Filtering videos without publish dates...")

    # Add publish dates to videos
    for video, publish_date in zip(videos, publish_dates):
        video["publish_date"] = publish_date

    # Find videos that don't have publish dates and log a warning for each
    for video in videos:
        if not video["publish_date"]:
            logging.warning(f"Could not get publish date for {video['url']}")

    # Remove videos that don't have publish dates
    orig_len = len(videos)
    videos = [v for v in videos if v["publish_date"]]
    logging.info(f"Found {len(videos)}/{orig_len} videos with publish dates")

    # filter out videos that don't meet date criteria
    logging.info("Filtering videos by date...")
    if min_date:
        videos = [v for v in videos if min_date <= v["publish_date"]]
    if max_date:
        videos = [v for v in videos if v["publish_date"] <= max_date]
    if min_date and max_date:
        logging.info(f"Found {len(videos)} videos between {min_date} and {max_date}.")

    # Transcribe, in parallel, using get_transcript_from_id, passing in chunk_size argument
    logging.info("Transcribing videos...")
    with futures.ThreadPoolExecutor(max_workers=n_threads) as executor:
        transcripts = executor.map(
            get_transcript_from_id,
            [v["id"] for v in videos],
            [chunk_size] * len(videos),
        )
    logging.info("Done transcribing")

    # Add transcripts to videos
    for video, transcript in zip(videos, transcripts):
        video["transcript"] = transcript

    # optionally write to output file, casting all datetime objects to strings
    if output_file:
        logging.info(f"Writing to {output_file}...")
        with open(output_file, "w") as file:
            json.dump(videos, file, default=str)
        logging.info("Done.")

    # Need to take each transcript record and create a unique publish record
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

    # Publish to Pub/Sub
    if project_id and topic_name:
        logging.info(f"Publishing {len(records)} records to Pub/Sub...")
        publish_video_snippets(project_id, topic_name, records)
    else:
        logging.info("No project_id or topic_name provided. Not publishing.")


# Main script part
if __name__ == "__main__":
    # initialize logging with INFO level and a timestamp
    logging.basicConfig(
        format="%(asctime)s %(levelname)s: %(message)s", level=logging.INFO
    )

    parser = argparse.ArgumentParser()
    parser.add_argument("--input_file", help="File to parse", required=True)
    parser.add_argument(
        "--project_id",
        type=str,
        required=False,
        help="Google Cloud Project ID",
    )
    parser.add_argument(
        "--topic_name",
        type=str,
        required=False,
        help="Google Pub/Sub topic name",
    )
    parser.add_argument(
        "--min_date", help="Minimum date to scrape (YYYY-MM-DD)", type=str, default=None
    )
    parser.add_argument(
        "--max_date", help="Maximum date to scrape (YYYY-MM-DD)", type=str, default=None
    )
    # add optional output file argument
    parser.add_argument(
        "--output_file", help="File to write to", type=str, default=None
    )
    # Add an argument for minimum number of words in a file required
    # to be indexed.
    parser.add_argument(
        "--min_words",
        type=int,
        default=30,
        help="Minimum number of words in a file required to be indexed",
    )
    # add chunk_size
    parser.add_argument(
        "--transcript_chunk_size",
        type=int,
        default=300,
        help="Number of seconds for each chunk out of transcript",
    )
    # add a csv file that contains a list of channels and title keywords to skip
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
        args.project_id,
        args.topic_name,
        output_file=args.output_file,
        min_date=min_date,
        max_date=max_date,
        min_words=args.min_words,
        chunk_size=args.transcript_chunk_size,
        skip_file=args.skip_file,
    )
