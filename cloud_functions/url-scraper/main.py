"""
Cloud Function to scrape a HTML text and extract hyperlinks and YouTube videos.
It then publishes the extracted text to another Pub/Sub topic, the `embedding-indexer`
to be indexed by the embedding model.

Example deployment:

gcloud functions deploy parse_and_publish \
    --runtime python310 \
    --trigger-topic [YOUR_TOPIC_NAME] \
    --entry-point parse_and_publish \
    --project [YOUR_PROJECT] \
    --region us-east1 \
    --memory 256Mi \
    --timeout 540s \
    --max-instances 1
    --set-env-vars=PROJECT_ID=[YOUR_PROJECT],DESTINATION_TOPIC_NAME=[YOUR_TOPIC_NAME]

"""

import base64
import functions_framework
import os
import json
import logging
import requests
from bs4 import BeautifulSoup
from google.cloud import pubsub_v1
from typing import Any, Dict, List
from util_scrape import get_main_text
from youtube import extract_transcript_snippets_from_url
import re


def parse_hyperlinks(text):
    # Parse the text for hyperlinks
    soup = BeautifulSoup(text, "html.parser")
    ignore_terms = ["unsubscribe", "privacy policy", "terms of service"]

    def should_ignore(link):
        href = link.get("href").lower()
        text = link.get_text().lower()
        return any(term in href or term in text for term in ignore_terms)

    # Get all links that don't contain any of the ignore terms
    links = [a["href"] for a in soup.find_all("a", href=True) if not should_ignore(a)]

    return links


def is_youtube_url(url):
    # Regex from https://stackoverflow.com/a/7936523
    youtube_pattern = re.compile(
        r"(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})"
    )  # noqa: E501

    return youtube_pattern.match(url)


def process_url(url, attributes):
    # Process the URL to generate records to publish
    if is_youtube_url(url):
        # If the URL is a YouTube video, extract the transcript snippets
        records = extract_transcript_snippets_from_url(url)
    else:
        # Otherwise, just get the main text from the URL
        response = requests.get(url)
        html_body = get_main_text(response.text)
        records = [{"text": html_body, "attributes": attributes}]
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
    logging.info(f"Received message with attributes: {attributes}")
    logging.info(f"Found {len(text)} characters in input text.")
    logging.info(f"Text Snippet: {text[:300]}")

    # Parse hyperlinks from the text
    hyperlinks = parse_hyperlinks(text)
    if not hyperlinks:
        logging.error("No hyperlinks found in body")
    all_records = []

    # Process each hyperlink to generate records to publish
    for link in hyperlinks:
        records = None
        try:
            records = process_url(link, attributes)
        except Exception as e:
            logging.error(f"Error processing {link}: {e}")
        if records and len(records) > 0:
            all_records.extend(records)

    # Publish the records
    if len(all_records) > 0:
        publish_records(all_records, project_id, destination_topic_name)
    else:
        logging.error("No records to publish")


if __name__ == "__main__":
    from cloudevents.http import CloudEvent

    # Initialize logging with timestamp
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s",
        level=logging.INFO,
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    example_message = """
        <html>
            <body>
                <a href="https://www.youtube.com/watch?v=dQw4w9WgXcQ">YouTube Video</a>
                <a href="https://example.com">Example Website</a>
            </body>
        </html>
    """

    # Convert the example_message to a Pub/Sub message format
    pubsub_message = {
        "data": base64.b64encode(example_message.encode("utf-8")),
        "attributes": {"source": "example-source"},
    }

    # Create a CloudEvent object
    cloud_event = CloudEvent(
        {
            "source": "test",
            "type": "com.example.test",
            "subject": "Test",
            "id": "12345",
            "time": "2023-03-23T12:34:56.789Z",
            "specversion": "1.0",
        },
        {"message": pubsub_message},
    )

    # Call the parse_and_publish function with the example cloud_event)
    parse_and_publish(cloud_event)
