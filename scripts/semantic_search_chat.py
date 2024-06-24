"""

This script is an example of how to use llama-index library
to have a vector-store index backed chat agent.

The chat agent defaults to ReACT type using gpt-3.5-turbo model.
It does NOT provide sources like query_engine.

See https://gpt-index.readthedocs.io/en/latest/core_modules/query_modules/chat_engines/usage_pattern.html#available-chat-modes.

Setup:

Set OPENAI_API_KEY and PINECONE_API_KEY env variables

Usage:

Basically same as query_semantic_search_llm.py without the --query argument.
Try first with --help

"""  # noqa

import argparse
import os
from pinecone import Pinecone

from llama_index.vector_stores.pinecone import PineconeVectorStore
from llama_index.core import VectorStoreIndex
from llama_index.llms.openai import OpenAI

if __name__ == "__main__":
    # parse arguments
    parser = argparse.ArgumentParser(
        description="Script to test the chat engine with vector store index"
    )
    parser.add_argument(
        "--pinecone_index_name",
        type=str,
        required=True,
        help="Name of pinecone index",
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
    # add optional language_model, defaulting to gpt-3.5-turbo
    parser.add_argument(
        "--language_model",
        type=str,
        default="gpt-3.5-turbo",
        help="Name of language model to use, e.g. gpt-3.5-turbo",
    )
    args = parser.parse_args()
    pinecone_index_name = args.pinecone_index_name
    namespace = args.pinecone_namespace
    top_k = args.top_k
    max_text_print = args.max_text_print
    language_model = args.language_model

    # Get API Keys from env
    pinecone_api_key = os.environ.get("PINECONE_API_KEY")

    # Initialize Pinecone
    pc = Pinecone(api_key=pinecone_api_key)
    pinecone_index = pc.Index(pinecone_index_name)

    # Initialize vector store
    vector_store = PineconeVectorStore(
        pinecone_index=pinecone_index, namespace=namespace
    )

    # Build index from existing vector store
    index = VectorStoreIndex.from_vector_store(
        vector_store,  # vector_store_info=metadata_fields
    )

    # Create language model and bind to service context
    gpt_model = OpenAI(temperature=0, model=language_model)

    # Create engine
    chat_engine = index.as_chat_engine(llm=gpt_model, verbose=True)

    # Start interactive chat
    chat_engine.chat_repl()
