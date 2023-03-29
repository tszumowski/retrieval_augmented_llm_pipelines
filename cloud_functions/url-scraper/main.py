"""
Cloud Function to scrape a HTML text and extract hyperlinks and YouTube videos.
It then publishes the extracted text to another Pub/Sub topic, the `embedding-indexer`
to be indexed by the embedding model.

"""

import base64
import functions_framework
import os
import requests
import sys
from google.cloud import pubsub_v1
from typing import Any, Dict, List
from util_scrape import clean_text, get_main_text, parse_hyperlinks
from youtube import extract_transcript_snippets_from_url, is_youtube_url

MIN_TOKENS = 30


def process_url(url: str, attributes: Dict[str, str]):
    """
    Process the URL to generate records to publish.

    Args:
        url: The URL to process.

    Returns:
        records: A list of records to publish. Each record is a dictionary with
            the following keys:
            - text: The text to publish
            - attributes: A dictionary of attributes to publish with the text

    """
    # Process the URL to generate records to publish
    records = None

    if is_youtube_url(url):
        # If the URL is a YouTube video, extract the transcript snippets
        records = extract_transcript_snippets_from_url(url, min_tokens=MIN_TOKENS)
    else:
        # Otherwise, just get the main text from the URL
        response = requests.get(url)
        html_body = get_main_text(response.text)
        if html_body and len(html_body) >= MIN_TOKENS:
            # If the text is long enough, publish it
            records = [{"text": html_body, "attributes": attributes}]

    # If there are records, clean the text field
    if records:
        for record in records:
            record["text"] = clean_text(record["text"])

    return records


def publish_records(
    records: List[Dict[str, Any]], project_id: str, destination_topic_name: str
) -> None:
    """
    Publishes the records to the destination topic.

    Args:
        records: A list of records to publish. Each record is a dictionary with
            the following keys:
            - text: The text to publish
            - attributes: A dictionary of attributes to publish with the text
        project_id: The project ID to publish to
        destination_topic_name: The name of the topic to publish to

    Returns:
        None
    """
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(project_id, destination_topic_name)

    for record in records:
        message = record["text"].encode("utf-8")
        attributes = record["attributes"]
        publisher.publish(topic_path, data=message, **attributes)


# Triggered from a message on a Cloud Pub/Sub topic.
@functions_framework.cloud_event
def parse_and_publish(cloud_event):
    # Fetch environment variables
    project_id = os.environ["PROJECT_ID"]
    destination_topic_name = os.environ["DESTINATION_TOPIC_NAME"]

    # Extract text and metadata from the Pub/Sub message
    text = str(base64.b64decode(cloud_event.data["message"]["data"]))
    attributes = cloud_event.data["message"]["attributes"]
    print(f"Received message with attributes: {attributes}")
    print(f"Found {len(text)} characters in input text.")
    print(f"Text Snippet: {text[:300]}")

    # Parse hyperlinks from the text
    hyperlinks = parse_hyperlinks(text)
    print(f"Found {len(hyperlinks)} hyperlinks in input text to scrape.")

    # Process each hyperlink to generate records to publish
    all_records = list()
    valid_links = list()
    for link in hyperlinks:
        records = None
        try:
            records = process_url(link, attributes)
        except Exception as e:
            print(f"Error processing {link}: {e}", file=sys.stderr)

        # Add the records to the list of records to publish
        if records and len(records) > 0:
            all_records.extend(records)
            valid_links.append(link)
    if len(valid_links) > 0:
        # Create list of tuples with link and number of characters in the text
        print(f"Processed {len(valid_links)} valid hyperlinks: [{valid_links}]")
        # print list of number of characters in all records
        print(
            f"Number of characters in all {len(all_records)} records: "
            f"[{[len(record['text']) for record in all_records]}]"
        )

    # Publish the records
    if len(all_records) > 0:
        print(
            f"Publishing {len(all_records)} scraped records from {len(valid_links)} links to "
            f"topic {destination_topic_name}."
        )
        publish_records(all_records, project_id, destination_topic_name)
    else:
        print("No records to publish", file=sys.stderr)
    print(f"Finished pubishing {len(all_records)} records.")
