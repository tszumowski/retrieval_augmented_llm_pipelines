"""
Script to backfill HTML

"""

import argparse
import jsonlines
import os
import requests
import sys

from pathlib import Path
from tqdm import tqdm
from typing import Dict, List, Optional
from uuid import uuid4

# add ../cloud_functions to path to access utils
sys.path.append(
    os.path.join(os.path.dirname(__file__), "../cloud_functions/url-scraper")
)

from tokenization import tiktoken_len
from util_scrape import get_main_text, clean_text


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
    html_paths: List[str],
    output_file: str,
    attributes: Optional[Dict[str, str]] = None,
    min_tokens: Optional[int] = None,
    chunk_size: Optional[int] = None,
) -> None:
    """
    Parse a list of HTML files and write the extracted text to a JSONL file.

    Args:
        html_paths: List of any of: HTML file path, URL.
        output_file: File to write to.
        attributes: Dictionary of attributes to add to the Pub/Sub message.
        min_tokens: Minimum number of tokens in a file required to be indexed.
        chunk_size: Number of tokens per chunk
    """
    # Default to None if min_tokens is not a positive integer.
    if min_tokens is not None and min_tokens < 1:
        min_tokens = None

    # Publish messages to the topic, extracting the main body text from the
    # HTML file.
    records = list()
    for tfile in tqdm(html_paths):
        with open(tfile, "r") as f:
            html = f.read()

        # Extract the test
        extracted_text = get_main_text(html)

        # Clean the text
        extracted_text = clean_text(extracted_text)

        # If chunk_size is specified, split the text into chunks.
        n_tokens = tiktoken_len(extracted_text)
        if min_tokens is not None:
            if n_tokens < min_tokens:
                print(
                    f"Skipping {tfile} because it has {n_tokens} tokens, which is less "
                    f"than the minimum of {min_tokens}."
                )
                continue
        print(
            f"Extracted {len(extracted_text)} characters, or {n_tokens} "
            f"tokens, from {tfile}."
        )
        print(f"Snippet:\n\t{extracted_text[0:300]}\n\n")  # Prints a sample

        # Build attributes, adding the title
        cur_attributes = attributes.copy()
        title = Path(tfile)
        title = title.stem
        cur_attributes["title"] = title

        record = {
            "text": extracted_text,
            "attributes": cur_attributes,
        }
        records.append(record)

    print(f"Writing {len(records)} / {len(html_paths)} files to {output_file}")
    with jsonlines.open(output_file, "w") as writer:
        writer.write_all(records)

    # TODO: save off the above in loop with some source info, and write to jsonl file output_file


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--html_path",
        type=str,
        required=True,
        help="""
        Comma separated list of html sources to process. Can be any combo of: HTML "
        "file path, directory of HTML files, or URL
        """,
    )
    parser.add_argument(
        "--output_file", help="File to write to", type=str, required=True
    )
    # Add an argument for Minimum number of tokens in a file required
    # to be indexed.
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
        help="Number of tokens per chunk",
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
        html_paths=html_paths,
        output_file=args.output_file,
        min_tokens=args.min_tokens,
        attributes=attributes,
        chunk_size=args.chunk_size,
    )
