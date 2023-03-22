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
    python backfill_youtube.py \
        --input_file=[PATH_TO_HTML_FILE] \
        --project_id=[PROJECT_ID] \
        --topic_name=[TOPIC_NAME] \
        --output_file=[PATH_TO_OUTPUT_FILE] \
        --min_date=[YYYY-MM-DD] \
        --max_date=[YiYY-MM-DD] \

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
from pytube import YouTube
import logging
import quopri
import json

import sys

# add ../cloud_functions/embedding-indexer to path to access youtube utils
sys.path.append(
    os.path.join(os.path.dirname(__file__), "../../cloud_functions/embedding-indexer")
)

# import get_transcript_from_url from youtube utils
from youtube import get_transcript_from_id

# Static variables
DEFAULT_N_THREADS = int(os.cpu_count() * 2)


def get_video_publish_date(url: str) -> Optional[datetime.datetime]:
    """Get the publish date of a YouTube video.

    Args:
        url (str): The URL of the YouTube video.

    Returns:
        Optional[datetime.datetime]: The publish date of the video.
    """
    try:
        # Initialize the YouTube object with the video URL
        yt = YouTube(url)

        # Get the publish date of the video
        publish_date = yt.publish_date

        return publish_date
    except Exception as e:
        logging.error(f"Error getting publish date for {url}: {e}")
        return None


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


def main(
    input_file: str,
    project_id: str,
    topic_name: str,
    output_file: Optional[str] = None,
    min_date: Optional[datetime.datetime] = None,
    max_date: Optional[datetime.datetime] = None,
    min_words: int = 0,
    n_threads: int = DEFAULT_N_THREADS,
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
    """
    # extract videos from mht file
    logging.info(f"Extracting videos from {input_file}...")
    videos = extract_videos_from_likes_mht(input_file)
    logging.info(f"Found {len(videos)} videos in mht file.")
    if len(videos) == 0:
        logging.info("None found. Exiting.")
        return

    # TODO, TMP: sample 20 videos randomly
    import random

    videos = random.sample(videos, 20)

    # Get publish date in parallel for all videos using joblib threads
    logging.info("Getting publish dates for videos...")
    with futures.ThreadPoolExecutor(max_workers=n_threads) as executor:
        publish_dates = executor.map(get_video_publish_date, [v["url"] for v in videos])
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
    logging.info(f"Filtering videos by date...")
    videos = [v for v in videos if min_date <= v["publish_date"] <= max_date]
    logging.info(f"Found {len(videos)} videos between {min_date} and {max_date}.")

    # Transcribe, in parallel, using get_transcript_from_url
    logging.info("Transcribing videos...")
    with futures.ThreadPoolExecutor(max_workers=n_threads) as executor:
        transcripts = executor.map(get_transcript_from_id, [v["id"] for v in videos])
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
        # create a record for each transcript line
        for snippet in video["transcript"]:
            attributes = {
                "source": "youtube",
                "video_id": video["id"],
                "title": video["title"],
                "url_base": video["url"],
                "url": f"{video['url']}&t={snippet['start']}",
                "start": snippet["start"],
                "end": snippet["end"],
                "channel": video["channel"],
                "publish_date": video["publish_date"].strftime("%Y-%m-%d"),
            }
            text = snippet["text"]
            record = {"attributes": attributes, "text": text}
            records.append(record)

    # Publish to Pub/Sub
    logging.info(f"Publishing {len(records)} records to Pub/Sub...")
    publish_video_snippets(project_id, topic_name, records)


def publish_video_snippets(
        project_id: str,
        topic_name: str,
        records: List[Dict[str, Any]],
):
    """
    Publishes video snippets to a Pub/Sub topic.

    Args:
        project_id: The GCP project ID.
        topic_name: The name of the Pub/Sub topic.
        records: A list of records to publish.

    Returns:
        None

    """
    # Initialize a Publisher client.
    publisher = pubsub_v1.PublisherClient()

    # Define the topic path.
    topic_path = publisher.topic_path(project_id, topic_name)
    logging.info(f"Topic path: {topic_path}")

    # Publish messages to the topic, extracting the main body text from the
    # HTML file.
    total_processed = 0
    publish_futures = list()
    for record in tqdm(records):
        text = record["text"]
        attributes = record["attributes"]
        future = publisher.publish(
            topic_path, data=text.encode("utf-8"), **attributes
        )
        publish_futures.append(future)
        total_processed += 1

    # Wait for all the publish futures to resolve before reporting complete.
    print(f"Waiting for {len(publish_futures)} publish events to complete ...")
    futures.wait(publish_futures, return_when=futures.ALL_COMPLETED)

    print(f"Done! Processed {total_processed} / {len(records)} video snippets.")


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
        required=True,
        help="Google Cloud Project ID",
    )
    parser.add_argument(
        "--topic_name",
        type=str,
        required=True,
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
        default=0,
        help="Minimum number of words in a file required to be indexed",
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
    )
