"""
This module scrapes the README files of all the repositories starred by a GitHub user.
It then saves the URLs of the README files in a Google Cloud Datastore.
For any new ones found, it saves as a {"text": <readme_content>, "attributes": ...}
record in a JSONlines file.
"""
import config
import functions_framework
import json
import os
import requests
from google.cloud import firestore
from google.cloud import pubsub_v1
from urllib.parse import quote
from typing import Any, Dict, List
from util import clean_text

# Get env vars
GITHUB_USERNAME = os.environ["GITHUB_USERNAME"]
GITHUB_TOKEN = os.environ["API_KEY_GITHUB"]
PROJECT_ID = os.environ["PROJECT_ID"]


def get_next_link(headers):
    link_header = headers.get("Link", "")
    links = link_header.split(", ")
    for link in links:
        if 'rel="next"' in link:
            return link[link.index("<") + 1 : link.index(">")]
    return None


def scrape_and_save_readme(
    github_username: str, github_token: str
) -> List[Dict[str, Any]]:
    """
    Scrape the README files of all the repositories starred by a GitHub user.
    Save the URLs of the README files in a Google Cloud Datastore.
    For any new ones found, save as a {"text": <readme_content>, "attributes": ...}
    record in a JSONlines file.

    """
    # Init
    total_repos = 0
    page_count = 0
    records = list()

    # Initialize the Datastore client
    firestore_client = firestore.Client()

    # Define the GitHub API URL for fetching starred repositories
    url = f"https://api.github.com/users/{github_username}/starred"
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github+json",
    }

    while url:
        page_count += 1
        print(f"Processing page {page_count}...")

        # Fetch starred repositories from the current page
        response = requests.get(url, headers=headers)
        repos = response.json()
        print(f"Found {len(repos)} starred repositories on page {page_count}.")
        total_repos += len(repos)

        # Iterate over each repository
        for repo in repos:
            # Get the URL of the repository
            repo_url = repo["html_url"]

            # Encode the URL to create a valid document name
            doc_name = quote(repo_url, safe="")

            # Check if the URL already exists in Firestore
            doc_ref = firestore_client.collection(config.COLLECTION_NAME).document(
                doc_name
            )
            doc = doc_ref.get()
            if doc.exists:
                # Skip if the URL already exists in Firestore
                continue

            # Get the URL of the README file
            base_url = repo["html_url"]
            base_url = base_url.replace("github.com", "raw.githubusercontent.com")

            # Scrape the README content
            for branch in config.BRANCH_CANDIDATES:
                for file in config.FILE_CANDIDATES:
                    readme_url = f"{base_url}/{branch}/{file}"
                    readme_response = requests.get(readme_url)
                    if readme_response.status_code == 200:
                        break
                if readme_response.status_code == 200:
                    break
            if readme_response.status_code == 200:
                # Clean the README content
                readme_content = readme_response.text
                readme_content = clean_text(readme_content)

                # Build the record
                print(f"Saving README for {repo_url}. Snippet: {readme_content[:100]}.")
                record = {
                    "text": readme_content,
                    "attributes": {
                        "url": repo_url,
                        "readme_url": readme_url,
                        "source": "github",
                    },
                }
                records.append(record)

                # Add the URL to Firestore
                doc_ref.set({"url": doc_name})

            else:
                print(f"README not found for {repo_url}. ")

        # Get the URL for the next page from the Link header
        url = get_next_link(response.headers)

    print(f"Processed {len(records)} out of {total_repos} repositories.")
    return records



@functions_framework.cloud_event
def process_pubsub(cloud_event):
    """
    Entry point for the Cloud Function.
    """
    print(f"Received event: {cloud_event}.")

    # Call the function
    records = scrape_and_save_readme(GITHUB_USERNAME, GITHUB_TOKEN)

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


# Call the function
if __name__ == "__main__":
    output_file = "github_starred_repos.jsonl"

    # Scrape the README files of all the repositories starred by a GitHub user
    records = scrape_and_save_readme(GITHUB_USERNAME, GITHUB_TOKEN)

    # Save the records to a JSONlines file
    print(f"Saving {len(records)} records to {output_file}.")
    with open(output_file, "w") as file:
        # write each record as a JSON line
        for record in records:
            file.write(json.dumps(record, default=str))
            file.write("\n")
