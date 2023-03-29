"""
This script takes any JSONlines file with text and attributes field, and publishes
them all in parallel to pubsub.

It assumes the JSON payload is already split properly to appropriate lengths.
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


def publish_records(
    project_id: str,
    topic_name: str,
    records: List[Dict[str, Any]],
) -> List[futures.Future]:
    """
    Publishes records to a Pub/Sub topic.

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


def main(input_file: str, project_id: str, topic_name: str):
    """
    Main function.

    Args:
        input_file: The path to the mht file.
        project_id: The GCP project ID.
        topic_name: The name of the Pub/Sub topic.
    """
    # load all into memory via jsonlines
    records = list()
    with open(input_file, "r") as f:
        for line in f:
            record = json.loads(line)
            records.append(record)

    # publish records to pubsub
    _ = publish_records(project_id, topic_name, records)


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

    # cast min_date and max_date to datetime objects
    args = parser.parse_args()
    # call main function
    main(args.input_file, args.project_id, args.topic_name)
