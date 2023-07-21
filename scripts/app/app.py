"""
gradio app for interacting with Retrieval-Augmented LLM

Setup:

- Set OPENAI_API_KEY and PINECONE_API_KEY env variables
- Configure the parameters in USER CONFIG below

"""
import gradio as gr
import os
import pinecone
from typing import Any, Sequence

from llama_index.vector_stores import PineconeVectorStore
from llama_index import VectorStoreIndex

"""
USER CONFIG
"""

# Pinecone index to use
PINECONE_INDEX_NAME = "openai-embedding-index"

# Pinecone namespace to use
PINECONE_NAMESPACE = None

# Pinecone environment to use
PINECONE_ENV_NAME = "us-east1-gcp"

# Embedding model to use, must match that used in index
EMBEDDING_MODEL = "text-embedding-ada-002"

# Number of retrieved sources to pass in to the LLM
TOP_K = 5

# Max number of characters to print for each source shown
MAX_TEXT_PRINT = 1000

# Flag to show sources or not
SHOW_SOURCES = True

"""
INITIALIZE
"""

# Get API Keys from env
pinecone_api_key = os.environ.get("PINECONE_API_KEY")

# Initialize Pinecone
pinecone.init(environment=PINECONE_ENV_NAME, api_key=pinecone_api_key)
pinecone_index = pinecone.Index(PINECONE_INDEX_NAME)

# Initialize vector store
vector_store = PineconeVectorStore(
    pinecone_index=pinecone_index, namespace=PINECONE_NAMESPACE
)

# Build index from existing vector store
index = VectorStoreIndex.from_vector_store(
    vector_store,  # vector_store_info=metadata_fields
)

# Create engine
query_engine = index.as_query_engine(similarity_top_k=TOP_K)

"""
FUNCTIONS AND START
"""


def ask_question(message: str, history: Sequence[Any]) -> str:
    """
    Ask a question and return the response

    Args:
        message (str): The question to ask
        history (Sequence[Any]): The history of the conversation

    Returns:
        str: The formatted response
    """
    response = query_engine.query(message)

    output = "\nResponse:\n---\n"
    output += str(response)

    # Get sources
    output += "\nSources:\n---\n"
    nodes = response.source_nodes
    for i, node in enumerate(nodes, 1):
        # Get shortened source text
        source_text = node.node.text[2:MAX_TEXT_PRINT]

        # Get metadata
        metadata = node.node.extra_info
        metadata.pop("url_base", None)
        metadata.pop("n_tokens", None)
        metadata.pop("duration", None)

        # pretty print
        output += f"Source {i}:\n"
        output += f"Text: {source_text}\n"
        output += "Metadata:\n"
        for k, v in metadata.items():
            output += f"\t{k}: {v}\n"
        output += "\n"

    # append history
    history.append((message, output))

    return output


with gr.Blocks() as demo:
    chatbot = gr.Chatbot()
    msg = gr.Textbox()
    clear = gr.ClearButton([msg, chatbot])

    msg.submit(ask_question, [msg, chatbot], [msg, chatbot])

if __name__ == "__main__":
    demo.launch()


# Start the app
gr.ChatInterface(ask_question).launch()
