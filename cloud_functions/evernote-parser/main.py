"""
Cloud Function to parse Evernote notes and any ones not already flagged as processed
in Cloud Firestore over to Cloud Pub/Sub.

**WARNING: See README.md for important information about this script.**

"""
import config
import evernote.edam.notestore.ttypes as NoteStoreTypes
import evernote.edam.type.ttypes as EvernoteTypes
import functions_framework
import json
import os

from datetime import datetime
from evernote.api.client import EvernoteClient
from evernote.edam.notestore import NoteStore
from google.cloud import firestore
from google.cloud import pubsub_v1
from retry import retry
from typing import Any, Dict, List, Optional, Sequence, Tuple
from util import clean_text


# Get env vars
ACCESS_TOKEN_EVERNOTE = os.environ["ACCESS_TOKEN_EVERNOTE"]
PROJECT_ID = os.environ["PROJECT_ID"]

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
def process_note(
    note: NoteStoreTypes.NoteMetadata,
    note_store: NoteStore,
    collection_name: str,
    client: firestore.Client,
    notebook: EvernoteTypes.Notebook,
    min_chars: int = 300,
) -> Optional[Dict[str, Any]]:
    """
    Process Evernote note object with retries and returns the note content.

    Args:
        note: The Evernote note object.
        note_store: The Evernote note store.
        collection_name: The Firestore collection name.
        client: The Firestore client.
        notebook: The notebook name.
        min_chars: Minimum number of characters in a note to be considered a record

    Returns:
        record: Record dict with the note content and attributes.
    """
    record = None

    # Get creation time
    created_time = note.created
    created_time = datetime.fromtimestamp(created_time / 1000).isoformat()

    # Define a clean document name
    doc_name = f"{notebook.name}-{note.title}"
    doc_name = doc_name.replace(" ", "_").replace("/", "_")

    # Check if the document name already exists in Firestore
    doc_exists, doc_ref = check_doc_exists(doc_name, collection_name, client)
    if doc_exists:
        # Skip if already exists in Firestore
        return record

    # If not, get the note content
    note_content = note_store.getNoteContent(note.guid)
    note_content = clean_text(note_content)

    # Build the record
    print_label = f"{notebook.name} - {note.title} - ({created_time}"
    if len(note_content) >= min_chars:
        print(
            f"Saving content of note: {print_label}).\n"
            f"\tSnippet: {note_content[:100]}."
        )
        record = {
            "text": note_content,
            "attributes": {
                "notebook": notebook.name,
                "title": note.title,
                "created_time": created_time,
                "source": "evernote",
                "doc_name": doc_name,
            },
        }
    else:
        print(f"Skipping note {print_label} " f"because it is too short.")

    # Save the record to Firestore no matter what
    doc_ref.set({"title": doc_name})

    return record


@retry(
    tries=DEFAULT_RETRY_TRIES, delay=DEFAULT_RETRY_DELAY, backoff=DEFAULT_RETRY_BACKOFF
)
def process_notebook(
    notebook: EvernoteTypes.Notebook,
    note_store: NoteStore,
    collection_name: str,
    client: firestore.Client,
    limit: int = 200,
    **kwargs,
) -> Optional[List[Dict[str, Any]]]:
    """
        Process Evernote note object with retries and returns the note content.

        Args:
            notebook: The notebook name.
            note_store: The Evernote note store.
            collection_name: The Firestore collection name.
            client: The Firestore client.
            limit: The number of notes to return per page.

        Returns:
            records: A list of records in the form of
                {"text": <note_content>, "attributes": ...}
    ):
    """
    # Paginate through the notes in the notebook, 100 at a time
    offset = 0
    n_notes = 0
    while True:
        note_filter = NoteStoreTypes.NoteFilter(notebookGuid=notebook.guid)
        result_spec = NoteStoreTypes.NotesMetadataResultSpec(
            includeTitle=True, includeCreated=True
        )
        note_list = note_store.findNotesMetadata(
            note_filter, offset, limit, result_spec
        )
        notes = note_list.notes
        n_notes += len(notes)

        # If there are no more notes, break
        if not notes:
            break

        print(f"Found {n_notes} notes in {notebook.name} so far.")
        for note in notes:
            record = process_note(
                note, note_store, collection_name, client, notebook, **kwargs
            )
            if record:
                records.append(record)

        # Increment the offset
        offset += limit


def scrape_evernote(
    access_token: str,
    notebooks: Sequence[str],
    sandbox: bool = False,
    china: bool = False,
    min_chars: int = 300,
) -> List[Dict[str, Any]]:
    """
    Scrape the README files of all the repositories starred by a GitHub user.
    Save the URLs of the README files in a Google Cloud Datastore.
    For any new ones found, save as a {"text": <readme_content>, "attributes": ...}
    record in a JSONlines file.

    Args:
        access_token: The Evernote API token.
        notebooks: The Evernote notebooks to scrape.
        sandbox: Whether to use the Evernote sandbox.
        china: Whether to use the Evernote China API.
        min_chars: The minimum number of characters in a note to save.

    Returns:
        records: A list of records in the form of
            {"text": <notebook page text>, "attributes": ...}

    """
    # Init
    records = list()
    n_notebooks_found = 0
    notebooks_to_match = [notebook.lower() for notebook in notebooks]

    # Initialize the Datastore client
    firestore_client = firestore.Client()

    # Connect to evernote
    client = EvernoteClient(token=access_token, sandbox=sandbox, china=china)

    # List all of the notebooks in the user's account
    note_store = client.get_note_store()
    notebooks_all = note_store.listNotebooks()
    print(f"Found {len(notebooks_all)} notebooks.")
    for nb in notebooks_all:
        if nb.name.lower() not in notebooks_to_match:
            continue
        print(f"Processing notebook {nb.name}...")
        n_notebooks_found += 1

        notebook_records = process_notebook(
            nb,
            note_store,
            config.COLLECTION_NAME,
            firestore_client,
            min_chars=min_chars,
        )
        if notebook_records:
            records.extend(notebook_records)

    print(
        f"Processed {n_notebooks_found} matching Evernote notebooks out of "
        f"{len(notebooks_all)} total."
    )
    print(f"Extracted {len(records)} records total.")
    return records


@functions_framework.cloud_event
def process_pubsub(cloud_event):
    """
    Entry point for the Cloud Function.

    Args:
        cloud_event: The Cloud Event.

    Returns:
        None
    """
    print(f"Received event: {cloud_event}.")

    # Call the function
    records = scrape_evernote(ACCESS_TOKEN_EVERNOTE, config.NOTEBOOKS)

    # Send the records to the Pub/Sub topic
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(PROJECT_ID, config.PUBSUB_TOPIC)

    for record in records:
        message = record["text"].encode("utf-8")
        attributes = record["attributes"]
        # Cast all to strings
        attributes = {k: str(v) for k, v in attributes.items()}
        # Publish the message
        publisher.publish(topic_path, data=message, **attributes)


if __name__ == "__main__":
    # Main function saves them all to a file rather than pushing to Pub/Sub
    output_file = "evernote_notes.jsonl"
    sandbox = config.EVERNOTE_SANDBOX

    # Scrape the README files of all the repositories starred by a GitHub user
    records = scrape_evernote(ACCESS_TOKEN_EVERNOTE, config.NOTEBOOKS, sandbox=sandbox)

    # Save the records to a JSONlines file
    print(f"Saving {len(records)} records to {output_file}.")
    with open(output_file, "w") as file:
        # write each record as a JSON line
        for record in records:
            file.write(json.dumps(record, default=str))
            file.write("\n")
