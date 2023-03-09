"""
Script to backfill HTML

"""

import argparse
import os
import requests

from bs4 import BeautifulSoup
from concurrent import futures
from google.cloud import pubsub_v1
from tqdm import tqdm
from typing import Dict, List, Optional
from uuid import uuid4


def get_main_text(html):
    soup = BeautifulSoup(html, "html.parser")
    main_text = ""
    for tag in soup.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6"]):
        main_text += tag.get_text() + " "
    return main_text.strip()


def parse_html_input(html_path: str) -> List[str]:
    """
    Input can be any combination of: file, directory of files, or a URL.
    This parses that out so that the main function can process it as a list of local
    HTML files.

    Args:
        html_path: User input of HTML file, directory of HTML files, or URL.
            Can be a comma-separated list of any combo of these as well.

    Returns:
        files_to_parse: List of HTML files to parse.
    """
    # First string-split on comma in the event they are passing a list of items
    html_path = html_path.split(",")

    # We now have a list of items where each item is either a file, directory, or URL
    files_to_parse = list()
    for h in html_path:
        # Determine if html_path is a file or directory. Cast to
        if os.path.isfile(h):
            # Just add the single file
            files_to_parse.append(h)
        elif os.path.isdir(h):
            # If it's a HTML directory, find all HTML files.
            for root, _, files in os.walk(h):
                for file in files:
                    if file.endswith(".html") or file.endswith(".htm"):
                        files_to_parse.append(os.path.join(root, file))
        # if it is a URL
        elif h.startswith("http") or h.startswith("www"):
            # Fetch the URL and save to a temporary file.
            r = requests.get(h)
            downloaded_file = os.path.join("/tmp", f"temp-{str(uuid4())[0:7]}.html")
            with open(downloaded_file, "w") as f:
                f.write(r.text)
            files_to_parse.append(downloaded_file)
        else:
            raise ValueError(f"Invalid html_path element: {h}")
    return files_to_parse


def parse_attributes(attributes_str: str) -> Dict[str, str]:
    """
    Parse attributes from string to dict.

    Args:
        attributes_str: String of attributes to parse, in form of "key1:value1,key2:value2"

    Returns:
        attributes: Dictionary of attributes
    """
    # Parse attributes
    attributes_list = attributes_str.split(",")
    attributes_list = [a.split(":") for a in attributes_list]
    attributes = {a[0]: a[1] for a in attributes_list}
    return attributes


def main(
    project_id: str,
    topic_name: str,
    html_paths: List[str],
    attributes: Optional[Dict[str, str]] = None,
    min_words: Optional[int] = None,
) -> None:
    """
    Backfill HTML to Google Pub/Sub topic.

    Args:
        project_id: Google Cloud Project ID
        topic_name: Google Pub/Sub topic name
        html_paths: List of any of: HTML file path, URL.
        attributes: Dictionary of attributes to add to the Pub/Sub message.
        min_words: Minimum number of words in a file required to be indexed.
    """
    # Default to None if min_words is not a positive integer.
    if min_words is not None and min_words < 1:
        min_words = None

    # Initialize a Publisher client.
    publisher = pubsub_v1.PublisherClient()

    # Define the topic path.
    topic_path = publisher.topic_path(project_id, topic_name)
    print(f"Topic path: {topic_path}")

    # Publish messages to the topic, extracting the main body text from the
    # HTML file.
    total_processed = 0
    publish_futures = list()
    for tfile in tqdm(html_paths):
        with open(tfile, "r") as f:
            html = f.read()
        extracted_text = get_main_text(html)
        if min_words is not None:
            n_words = len(extracted_text.split())
            if n_words < min_words:
                print(
                    f"Skipping {tfile} because it has {n_words} words, which is less "
                    f"than the minimum of {min_words}."
                )
                continue
        print(
            f"Extracted {len(extracted_text)} characters, or approximately {n_words} "
            f"words, from {tfile}."
        )
        print(f"Snippet:\n\t{extracted_text[0:500]}\n\n")  # Prints a sample
        future = publisher.publish(
            topic_path, data=extracted_text.encode("utf-8"), **attributes
        )
        publish_futures.append(future)
        total_processed += 1

    # Wait for all the publish futures to resolve before reporting complete.
    print(f"Waiting for {len(publish_futures)} publish events to complete ...")
    futures.wait(publish_futures, return_when=futures.ALL_COMPLETED)

    print(f"Done! Processed {total_processed} / {len(html_paths)} files.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
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
        "--html_path",
        type=str,
        required=True,
        help="""
        Comma separated list of html sources to process. Can be any combo of: HTML "
        "file path, directory of HTML files, or URL
        """,
    )
    # Add an argument for minimum number of words in a file required
    # to be indexed.
    parser.add_argument(
        "--min_words",
        type=int,
        default=0,
        help="Minimum number of words in a file required to be indexed",
    )
    # Add attrs to parser which is a string of comma-separated key-value pairs
    # using colons to separate the key and value. For example, "key1:value1,key2:value2"
    parser.add_argument(
        "--attrs",
        type=str,
        default="",
        help="""
        Comma-separated key-value colon pairs to add as attributes to the message.
        e.g. 'key1:value1,key2:value2'
        """,
    )

    args = parser.parse_args()

    # Parse files
    html_paths = parse_html_input(args.html_path)
    print(f"Found {len(html_paths)} files to parse.")

    # Parse attributes
    attributes = parse_attributes(args.attrs)
    print(f"Attributes: {attributes}")

    # Run main
    main(
        project_id=args.project_id,
        topic_name=args.topic_name,
        html_paths=html_paths,
        min_words=args.min_words,
        attributes=attributes,
    )
