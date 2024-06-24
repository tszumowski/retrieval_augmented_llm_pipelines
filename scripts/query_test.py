"""
Simple script to test querying pinecone index

Setup:

Set OPENAI_API_KEY and PINECONE_API_KEY env variables

Usage:

python scripts/query_test.py \
    --query "What are some ways to protect from Quantum Computer decryption?" \
    --embedding_model "text-embedding-ada-002" \
    --pinecone_index_name "openai-embedding-index2"
"""

# add embedding-indexer to pythonpath
import argparse
import openai
import os
from pinecone import Pinecone

if __name__ == "__main__":
    # parse arguments
    parser = argparse.ArgumentParser(
        description="Script to test querying pinecone index"
    )
    parser.add_argument(
        "--query",
        type=str,
        required=True,
        help=(
            "Query to search, e.g. 'What are some ways to protect from Quantum "
            "Computer decryption?'"
        ),
    )
    parser.add_argument(
        "--embedding_model",
        type=str,
        help="text-embedding-ada-002",
        default="text-embedding-ada-002",
    )
    parser.add_argument(
        "--pinecone_index_name",
        type=str,
        required=True,
        help="Name of pinecone index",
    )
    # top_k, max_text_print
    parser.add_argument(
        "--top_k",
        type=int,
        default=5,
        help="Number of results to return, e.g. 5",
    )
    parser.add_argument(
        "--max_text_print",
        type=int,
        default=1000,
        help="Max number of characters to print from each returned text, e.g. 1000",
    )
    args = parser.parse_args()
    query = args.query
    embedding_model = args.embedding_model
    pinecone_index_name = args.pinecone_index_name
    top_k = args.top_k
    max_text_print = args.max_text_print

    print(f"\nQuery:\n{query}")

    # Get API Keys from env
    API_KEY_OPENAI = os.environ.get("OPENAI_API_KEY")
    API_KEY_PINECONE = os.environ.get("PINECONE_API_KEY")

    # Embed query
    openai.api_key = API_KEY_OPENAI
    client = openai.Client()
    res = client.embeddings.create(input=[query], model=embedding_model)
    query_embedding = res.data[0].embedding

    # Query Pinecone
    pc = Pinecone(api_key=API_KEY_PINECONE)
    index = pc.Index(pinecone_index_name)
    print("\n\n")
    print(f"Index Stats:")
    print(index.describe_index_stats())
    print("\n\n")
    res = index.query(vector=[query_embedding], top_k=top_k, include_metadata=True)

    # Print
    matches = res["matches"]
    for i, r in enumerate(matches, 1):
        metadata = r["metadata"]
        score = r["score"]
        record_text = metadata.pop("text", None)
        record_text = str(record_text[:max_text_print])

        print(f"Match {i}:")
        print(f"\tScore: {score}")
        print(f"\tMetadata: {metadata}")
        print(f"\tText:\n\t\t{record_text}")
        print("\n\n")
