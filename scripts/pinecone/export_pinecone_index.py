"""
Exports all IDs from Pinecone index to a CSV lines file, and vectors to jsonlines
Since at the time of writing there was no easy way to fetch all IDs, it needs
to query iteratively until **most** idS are found.
"""
import jsonlines
import os
import pinecone
import random
import time
from tqdm import tqdm

index_name = "openai-embedding-index"  # Replace INDEX_NAME with the name of the index you want to export vectors from
env_name = "us-east1-gcp"
max_attempts = 50  # Max number of attempts to find all IDs
top_k = 10000  # Max allowed by Pinecone
fetch_chunk_size = 500  # Max allowed by Pinecone is 1000 I believe
sleep_time = 0.5  # Time to sleep between queries

output_filename_ids = f"ids-{index_name}-2.csv"  # Output filename
output_filename_vectors = f"vectors-{index_name}.jsonl"  # Output filename

# Input filename. If not None, it skips the hunt and just uses this file
input_ids_filename = f"ids-{index_name}.csv"


# Initialize Pinecone
api_key = os.environ.get("API_KEY_PINECONE")
pinecone.init(api_key=api_key, environment=env_name)

# Connect to index
index = pinecone.Index(index_name)

# Print output
index_stats = index.describe_index_stats()
print(f"Index info ({index_name}):\n------")
print(index_stats)
print("\n")


# Find all IDs. There's no docs-defined way to fetch all IDs from the index.
# So we need to query it with different IDs until we find it.

# Start with a random embedding of proper length
dims = index_stats["dimension"]
query_embedding = [0.0] * dims
total_ids = index_stats["total_vector_count"]

if input_ids_filename:
    # Load IDs from file
    with open(input_ids_filename, "r") as f:
        ids_found = f.read().splitlines()
    print(f"Loaded {len(ids_found)}/{total_ids} IDs from {input_ids_filename}")
else:
    # Query until we find all IDs
    ids_found = list()
    attempts = 0
    while len(ids_found) < total_ids and attempts < max_attempts:
        # Fetch some IDs
        results = index.query([query_embedding], top_k=top_k, include_metadata=False)
        ids = [result["id"] for result in results["matches"]]

        # Add all unique IDs to the list that don't overlap
        ids_found = list(set(ids_found + ids))
        attempts += 1
        print(f"{attempts}: Found {len(ids_found)}/{total_ids} IDs so far...")
        time.sleep(sleep_time)

        # choose the next random embedding from this output
        rand_id = random.choice(ids_found)
        r = index.fetch([rand_id])
        query_embedding = r["vectors"][rand_id]["values"]

    print(f"Executed {attempts} attempts of {max_attempts} allowed to find all IDs")
    print(f"Found {len(ids_found)}/{total_ids} IDs in total")

    # Save IDs to CSV file
    with open(output_filename_ids, "w") as f:
        f.write("\n".join(ids_found))
    print(f"Saved IDs to {output_filename_ids}")

# Fetch all vectors using those IDs, chunked by fetch_chunk_size
print(f"Fetching {len(ids_found)} vectors in chunks of {fetch_chunk_size}...")
with jsonlines.open(output_filename_vectors, "w") as writer:
    for i in tqdm(range(0, len(ids_found), fetch_chunk_size)):
        ids_chunk = ids_found[i : i + fetch_chunk_size]
        results = index.fetch(
            ids_chunk,
        )
        vectors = results["vectors"]
        for id, vector in vectors.items():
            # write to jsonlines file the id, metadata and value fields verbatim
            payload = {
                "id": id,
                "metadata": vector["metadata"],
                "value": vector["values"],
            }
            # set metadata publish_date to string
            if "publish_date" in payload["metadata"]:
                payload["metadata"]["publish_date"] = str(
                    payload["metadata"]["publish_date"]
                )
            writer.write(payload)
        time.sleep(sleep_time)
