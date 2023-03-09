import base64
import functions_framework
import config  # Update user config in this file
import hashlib
import openai
import os
import pinecone

"""
Initialization
"""

# Fetch the secret key from the environment variable
API_KEY_OPENAI = os.environ.get("API_KEY_OPENAI")
API_KEY_PINECONE = os.environ.get("API_KEY_PINECONE")

if not API_KEY_OPENAI:
    raise ValueError("API_KEY_OPENAI environment variable is not set")
if not API_KEY_PINECONE:
    raise ValueError("API_KEY_PINECONE environment variable  is not set")

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
    print(f"Received message with attributes: {msg_attributes}")
    print(f"Found {len(msg_text)} characters in input text.")
    print(f"Text Snippet: {msg_text[:300]}")
    default_max_chars = (
        config.N_CHARS_PER_TOKEN * config.MAX_TOKENS_PER_EMBEDDING_REQUEST
    )
    texts = [
        msg_text[i : i + default_max_chars]
        for i in range(0, len(msg_text), default_max_chars)
    ]
    print(f"Split into {len(texts)} chunks of text to batch.")

    # Create an embedding from input in batches of BATCH_SIZE
    embedding_batches = []
    text_batches = []
    for i in range(0, len(texts), config.BATCH_SIZE):
        max_chars = default_max_chars  # Reset max_chars
        text_batch = texts[i : i + config.BATCH_SIZE]
        # Try to embed text. If we get an error, try to split the text into
        # smaller chunks.
        try_cnt = 0
        while try_cnt < config.MAX_SPLIT_TRIES:
            try:
                res = openai.Embedding.create(
                    input=text_batch, engine=config.EMBEDDING_MODEL
                )
                break  # Break out of while loop if successful
            except openai.error.InvalidRequestError as e:
                if "reduce your prompt" in str(e):
                    print(
                        f"One of texts in batch were too long, splitting into "
                        f"smaller chunks. max_chars was {max_chars}"
                    )

                    # Reduce max_chars by half
                    max_chars = max_chars // 2
                    print(f"New max_chars is {max_chars}.")

                    # Break up text into smaller chunks
                    print(f"text_batch length was: {len(text_batch)}")
                    text_batch = [
                        text_batch[i][j : j + max_chars]
                        for i in range(len(text_batch))
                        for j in range(0, len(text_batch[i]), max_chars)
                    ]
                    print(f"text_batch length now: {len(text_batch)}")

                    try_cnt += 1
                else:
                    print(
                        f"Unable to embed even after {config.MAX_SPLIT_TRIES} "
                        f"reductions. Failing with error: {e}."
                    )
                    raise e
        embeddings = [x["embedding"] for x in res["data"]]

        # Check that we got the right number of embeddings
        if len(embeddings) != len(text_batch):
            raise ValueError(
                f"Number of embeddings ({len(embeddings)}) does not match number of "
                f"text chunks ({len(text_batch)})."
            )

        # Append to list
        embedding_batches.append(embeddings)
        text_batches.append(text_batch)

    print(f"Created {len(embedding_batches)} batches of embeddings.")

    """
    Batch Insert into Pinecone Index
    """

    # Create Pinecone index, if it doesn't exist. And connect.
    if config.PINECONE_INDEX_NAME not in pinecone.list_indexes():
        pinecone.create_index(
            config.PINECONE_INDEX_NAME, dimension=len(embedding_batches[0][0])
        )
    index = pinecone.Index(config.PINECONE_INDEX_NAME)

    # Add to index in batches
    vector_cnt = 0
    for i in range(len(embedding_batches)):
        # Select batch
        embeddings = embedding_batches[i]
        texts = text_batches[i]

        # Create vector objects
        vectors = list()
        for embedding, text in zip(embeddings, texts):
            # Hash the text to get a unique vector ID
            vector_id = hashlib.shake_256(text.encode()).hexdigest(5)
            metadata = {"text": text}
            metadata.update(msg_attributes)  # add pubsub attributes too (e.g. source)
            vectors.append((vector_id, embedding, metadata))
            vector_cnt += 1

        # Upsert this batch
        index.upsert(vectors=vectors)
    print(
        f"Inserted {vector_cnt} vectors into Pinecone index: "
        f"{config.PINECONE_INDEX_NAME}."
    )
