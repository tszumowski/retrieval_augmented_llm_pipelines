"""
TODO: MISSING METADATA FROM PINECONE!

This script is an example of how to use llama-index library
to run a retrieval augmented language model (RALM) on a query and return the results.

It leverages the OpenAI API to embed the query and the Pinecone API
to query the index. It also uses the llama-index library to run the
question answering chain on the results using the OpenAI API and the Pinecone
search results for context.

Setup:

Set OPENAI_API_KEY and PINECONE_API_KEY env variables

Usage:

python scripts/query_semantic_search_llm.py \
    --query "What are some ways to protect from Quantum Computer decryption?" \
    --pinecone_index_name "openai-embedding-index" \
    --pinecone_env_name "us-east1-gcp"

"""
import argparse
import os
import pinecone

from llama_index.vector_stores import PineconeVectorStore
from llama_index import VectorStoreIndex


if __name__ == "__main__":
    # parse arguments
    parser = argparse.ArgumentParser(
        description="Script to test querying pinecone index"
    )
    parser.add_argument(
        "--query",
        type=str,
        required=True,
        help="Query to search, e.g. 'What are some ways to protect from Quantum Computer decryption?'",
    )
    parser.add_argument("--embedding_model", type=str, help="text-embedding-ada-002")
    parser.add_argument(
        "--pinecone_index_name",
        type=str,
        required=True,
        help="Name of pinecone index",
    )
    parser.add_argument(
        "--pinecone_env_name",
        type=str,
        required=True,
        help="Name of pinecone environment",
    )
    parser.add_argument(
        "--pinecone_namespace",
        type=str,
        default=None,
        help="Namespace of pinecone index",
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
        default=500,
        help="Max number of characters to print from each returned text, e.g. 1000",
    )
    args = parser.parse_args()
    query = args.query
    pinecone_index_name = args.pinecone_index_name
    pinecone_env_name = args.pinecone_env_name
    namespace = args.pinecone_namespace
    top_k = args.top_k
    max_text_print = args.max_text_print

    print(f"\nQuery:\n---\n{query}")

    # Get API Keys from env
    pinecone_api_key = os.environ.get("PINECONE_API_KEY")

    # Initialize Pinecone
    pinecone.init(environment=pinecone_env_name, api_key=pinecone_api_key)
    pinecone_index = pinecone.Index(pinecone_index_name)

    # Initialize vector store
    vector_store = PineconeVectorStore(
        pinecone_index=pinecone_index, namespace=namespace
    )

    # Build index from existing vector store
    index = VectorStoreIndex.from_vector_store(
        vector_store,  # vector_store_info=metadata_fields
    )

    # Create engine
    query_engine = index.as_query_engine(similarity_top_k=top_k)

    response = query_engine.query(query)

    print("\nResponse:\n---\n")
    print(response)

    # Get sources
    print("\nSources:\n---\n")
    nodes = response.source_nodes
    for i, node in enumerate(nodes, 1):
        # Get shortened source text
        source_text = node.node.text[2:max_text_print]

        # Get metadata
        metadata = node.node.extra_info
        metadata.pop("url_base", None)
        metadata.pop("n_tokens", None)
        metadata.pop("duration", None)

        # pretty print
        print(f"Source {i}:\n")
        print(f"Text: {source_text}")
        print("Metadata:")
        for k, v in metadata.items():
            print(f"\t{k}: {v}")
        print("\n")
