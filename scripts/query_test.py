"""
Simple script to test querying pinecone index
"""
# add embedding-indexer to pythonpath
import openai
import os
import pinecone
import sys

path = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(path, "..", "cloud_functions", "embedding-indexer"))
import config  # NOQA

TOP_K = 5  # Number of results to return
MAX_TEXT_PRINT = 1000  # Max number of characters to print from text

if __name__ == "__main__":
    sample_query = (
        "How does Spotify augment training data using session user click history?"
    )
    print("Query:", sample_query)

    # Get API Keys from env
    API_KEY_OPENAI = os.environ.get("API_KEY_OPENAI")
    API_KEY_PINECONE = os.environ.get("API_KEY_PINECONE")

    # Embed query
    openai.api_key = API_KEY_OPENAI
    res = openai.Embedding.create(input=[sample_query], engine=config.EMBEDDING_MODEL)
    query_embedding = res["data"][0]["embedding"]

    print("Query embedding length:", len(query_embedding))

    # Query Pinecone
    pinecone.init(api_key=API_KEY_PINECONE, environment=config.PINECONE_ENV_NAME)
    index = pinecone.Index(config.PINECONE_INDEX_NAME)
    print("\n\n")
    print(f"Index Stats:")
    print(index.describe_index_stats())
    print("\n\n")
    res = index.query([query_embedding], top_k=TOP_K, include_metadata=True)

    # Print
    matches = res["matches"]
    for i, r in enumerate(matches, 1):
        metadata = r["metadata"]
        score = r["score"]
        record_text = metadata.pop("text", None)
        record_text = str(record_text[:MAX_TEXT_PRINT])

        print(f"Match {i}:")
        print(f"\tScore: {score}")
        print(f"\tMetadata: {metadata}")
        print(f"\tText:\n\t\t{record_text}")
        print("\n\n")
