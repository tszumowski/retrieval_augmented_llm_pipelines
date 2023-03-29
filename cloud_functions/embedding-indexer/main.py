"""
Cloud Function to generate embeddings from text and index them in Pinecone.
This function is triggered by a Pub/Sub message containing contents to embed.

Note: This assumes you already have the Pinecone index defined in `config.py` created.
If you do not, run something like the following:

```
    # Create Pinecone index, if it doesn't exist. And connect.
    if config.PINECONE_INDEX_NAME not in pinecone.list_indexes():
        pinecone.create_index(
            config.PINECONE_INDEX_NAME, dimension=len(embedding_batches[0][0])
        )
```


"""

import base64
import functions_framework
import config  # Update user config in this file
import hashlib
import openai
import os
import pinecone
from tokenization import tiktoken_len, split_by_tokenization

"""
Initialization
"""

# Fetch the secret key from the environment variable
API_KEY_OPENAI = os.environ["API_KEY_OPENAI"]
API_KEY_PINECONE = os.environ["API_KEY_PINECONE"]

# Initialize OpenAI
openai.api_key = API_KEY_OPENAI

# Initialize Pinecone
pinecone.init(api_key=API_KEY_PINECONE, environment=config.PINECONE_ENV_NAME)


# Triggered from a message on a Cloud Pub/Sub topic.
@functions_framework.cloud_event
def process_pubsub(cloud_event):
    # Extract text and metadata from the Pub/Sub message
    msg_text = str(base64.b64decode(cloud_event.data["message"]["data"]))
    msg_attributes = cloud_event.data["message"]["attributes"]
    # Add attribute "title" if doesn't exist
    if "title" not in msg_attributes:
        msg_attributes["title"] = "None"

    print(f"Received message with attributes: {msg_attributes}")
    msg_token_len = tiktoken_len(msg_text)
    print(f"Found {msg_token_len} tokens in input text.")
    print(f"Text chunk: {msg_text[:300]}")

    chunks = [{"text": msg_text, "n_tokens": msg_token_len}]
    if msg_token_len > config.MAX_TOKENS_INPUT:
        # Split into chunks based on tokenization
        chunks = split_by_tokenization(msg_text, config.TOKEN_CHUNK_SIZE)
        print(
            f"Split into {len(chunks)} chunks of text. Chunk sizes: "
            f"[{[s['n_tokens'] for s in chunks]}]"
        )

    # Run embedding one by one just in case there is an error we can catch
    processed_chunks = list()
    for i, chunk in enumerate(chunks, 1):
        text = chunk["text"]
        error_str = None
        res = list()

        try:
            res = openai.Embedding.create(input=text, engine=config.EMBEDDING_MODEL)
        except Exception as e:
            error_str = str(e)

        if len(res) == 0:
            print(f"Unable to embed text chunk #{i}: {error_str}. Skipping.")
            continue

        embedding = res["data"][0]["embedding"]

        # Append to list
        processed_chunks.append((chunk, embedding))

    print(f"Processed {len(processed_chunks)} of {len(chunks)} possible embeddings.")

    """
    Batch Insert into Pinecone Index
    """

    # Connect to index
    index = pinecone.Index(config.PINECONE_INDEX_NAME)

    # Add to index in batches
    processed_vector_cnt = 0
    for i, cur_record in enumerate(processed_chunks, 1):
        # Select batch
        data, embedding = cur_record
        text = data["text"]
        n_tokens = data["n_tokens"]

        # Create vector objects
        # Hash the text to get a unique vector ID
        vector_id = hashlib.shake_256(text.encode()).hexdigest(5)

        # add attributes that came from Pub/Sub
        metadata = {"text": text, "n_tokens": str(n_tokens)}
        metadata.update(msg_attributes)

        # Add incrementor to title
        metadata["title"] = f"{metadata['title']} - {i:03d}"

        # Create final vector object
        vector = (vector_id, embedding, metadata)

        # Upsert this vector
        try:
            index.upsert(vectors=[vector])
        except Exception as e:
            print(f"Unable to upsert vector {vector_id}: {e}. Skipping")
            continue
        processed_vector_cnt += 1
    print(
        f"Inserted {processed_vector_cnt} of {len(processed_chunks)} candidate vectors "
        f"into Pinecone index: {config.PINECONE_INDEX_NAME}."
    )
