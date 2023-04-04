"""
This script loads keys into Cloud Firestore. It reads each record of a JSONL file
and creates a document in the specified collection. The document name matches how
it is looked up and written in `main.py`.

This script is useful for backfilling notebooks since Evernote rate limits hourly.

To generate a JSONL file, export your evernote notebook to HTML. Then run
`scripts/parse_html_files.py` to generate a JSONL file. Then run this script to
load the keys into Firestore.

"""
import argparse
import json

from google.cloud import firestore
from retry import retry
from tqdm import tqdm
from typing import Tuple


# Static Defaults
DEFAULT_RETRY_BACKOFF = 2
DEFAULT_RETRY_DELAY = 1
DEFAULT_RETRY_TRIES = 5


def check_doc_exists(
    doc_name: str, collection_name: str, client: firestore.Client
) -> Tuple[bool, firestore.DocumentReference]:
    """
    Check if a document exists in Firestore.

    Args:
        doc_name: The document name.
        collection_name: The collection name.
        client: The Firestore client.

    Returns:
        exists: True if the document exists.
        doc_ref: The document reference.
    """
    doc_ref = client.collection(collection_name).document(doc_name)
    doc = doc_ref.get()
    return doc.exists, doc_ref


@retry(
    tries=DEFAULT_RETRY_TRIES, delay=DEFAULT_RETRY_DELAY, backoff=DEFAULT_RETRY_BACKOFF
)
def write_key_to_filestore(
    notebook_name: str, note_title: str, collection_name: str, client: firestore.Client
) -> None:
    """
    Process Evernote note object with retries and returns the note content.

    Args:
        notebook_name: The notebook name.
        note_title: The notebook title.
        collection_name: The Firestore collection name.
        client: The Firestore client.

    Returns:
        None
    """
    record = None

    # Define a clean document name
    doc_name = f"{notebook_name}-{note_title}"
    doc_name = doc_name.replace(" ", "_").replace("/", "_")

    # Check if the document name already exists in Firestore
    doc_exists, doc_ref = check_doc_exists(doc_name, collection_name, client)
    if doc_exists:
        # Skip if already exists in Firestore
        return None

    # Save the key to Firestore
    doc_ref.set({"title": doc_name})

    return record


if __name__ == "__main__":
    # parse: input_file, collection_name, project_id
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input_file",
        type=str,
        required=True,
        help="The JSONL file to read from.",
    )
    parser.add_argument(
        "--collection_name",
        type=str,
        required=True,
        help="The Firestore collection name.",
    )
    parser.add_argument(
        "--project_id",
        type=str,
        required=True,
        help="The GCP project ID.",
    )

    args = parser.parse_args()

    # Read the JSONL file
    with open(args.input_file, "r") as f:
        records = f.readlines()

    # Initialize Firestore client
    client = firestore.Client(project=args.project_id)

    # Loop through each record
    for record in tqdm(records):
        record = json.loads(record)
        attributes = record["attributes"]
        notebook_name = attributes["notebook"]
        note_title = attributes["title"]

        # Write the key to Firestore
        write_key_to_filestore(notebook_name, note_title, args.collection_name, client)
