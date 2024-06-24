"""
gradio app for interacting with Retrieval-Augmented LLM

Setup:

- Set OPENAI_API_KEY and PINECONE_API_KEY env variables
- Configure the parameters in USER CONFIG below

Notes:
- This is just a proof-of-concept. Some significant prompt-engineering would be
    needed to make this work well.
- This sends history in and out of the chatbot, but it is not a conversational agent,
    so it doesn't use it. The history is in there for potential future use.
- LlamaIndex is changing all the time. By the time you see this, there may be a better
    agent to insert. This is just using a simple VectorStore Query Engine. You may
    want to swap that out.

"""

import argparse
import gradio as gr
import os
import pandas as pd
from pinecone import Pinecone
from typing import Any, Sequence, Tuple

from llama_index.vector_stores.pinecone import PineconeVectorStore
from llama_index.core import VectorStoreIndex
from llama_index.llms.openai import OpenAI

"""
USER CONFIG
"""

# Pinecone index to use
PINECONE_INDEX_NAME = "openai-embedding-index2"

# Pinecone namespace to use
PINECONE_NAMESPACE = None

# Which language model to use. See OpenAPI docs for options
LANGUAGE_MODEL = "gpt-3.5-turbo"

# Number of retrieved sources to pass in to the LLM
TOP_K = 5

# Max number of characters to print for each source shown
MAX_TEXT_PRINT = 1000

# Flag to show sources or not
SHOW_SOURCES = True

# Table headers
TABLE_HEADERS = ("Source", "Channel", "Title", "URL", "Snippet")

# Base prompt to hack together conversational history
BASE_PROMPT = """
Given the following conversation history, what is the answer to the the question
posed at the bottom?

The history is in the format, starting at <HISTORY>:
Interaction #[i]:
Q: Question
A: Answer

<HISTORY>:

"""

"""
INITIALIZE
"""

# Get API Keys from env
pinecone_api_key = os.environ.get("PINECONE_API_KEY")

# Initialize Pinecone
pc = Pinecone(api_key=pinecone_api_key)
pinecone_index = pc.Index(PINECONE_INDEX_NAME)

# Initialize vector store
vector_store = PineconeVectorStore(
    pinecone_index=pinecone_index, namespace=PINECONE_NAMESPACE
)

# Build index from existing vector store
index = VectorStoreIndex.from_vector_store(vector_store)

# Create language model and bind to service context
gpt_model = OpenAI(temperature=0, model=LANGUAGE_MODEL)

# Create engine
query_engine = index.as_query_engine(llm=gpt_model, similarity_top_k=TOP_K)

"""
FUNCTIONS AND START
"""


def ask_question(
    message: str, history: Sequence[Any]
) -> Tuple[str, Sequence[str], pd.DataFrame]:
    """
    Ask a question and return the response

    Args:
        message (str): The question to ask
        history (Sequence[Any]): The history of the conversation

    Returns:
        response: The formatted response
        history: The updated history
        source_data: The dataframe of sources

    """
    # Build a single message to query using conversational history
    query = ""
    if history:
        query = BASE_PROMPT
        for i, (msg, resp) in enumerate(history, 1):
            query += f"Interaction #{i}:\nQ: {msg}\nA: {resp}\n\n"

    # Add the question to the end
    query += f"Q: {message}\nA:"

    # Ask the question
    query_response = query_engine.query(query)

    # Parse the raw reply
    response = str(query_response)

    # Extract the sources
    source_data = pd.DataFrame(columns=TABLE_HEADERS)
    nodes = query_response.source_nodes
    for i, node in enumerate(nodes, 1):
        # Get shortened source text
        source_text = node.node.text[2:MAX_TEXT_PRINT]

        # Get metadata
        metadata = node.node.extra_info

        # add a row to dataframe
        source_data.loc[i] = [
            metadata.get("source"),
            metadata.get("channel"),
            metadata.get("title"),
            metadata.get("url"),
            source_text,
        ]

    # append history
    history.append((message, response))

    # Print for logging purposes
    print(history)

    return response, history, source_data


with gr.Blocks() as ui:
    # Add input textbox
    msg = gr.Textbox()

    # Add a Chatbot like interface to make it look pretty.
    chatbot = gr.Chatbot()

    # add hidden textbox just to dump output
    msg_hidden = gr.Textbox(visible=False)

    # Create a row of buttons
    with gr.Row():
        submit = gr.Button("Submit")
        clear = gr.ClearButton([msg, chatbot])

    # Add a table to show sources after the query
    table = gr.DataFrame(headers=TABLE_HEADERS, row_count=(TOP_K, "fixed"), wrap=True)

    # Set up the click event for the submit button
    submit.click(
        ask_question, inputs=[msg, chatbot], outputs=[msg_hidden, chatbot, table]
    )

    # Alternately, allow pressing enter on textbox to submit too
    msg.submit(
        ask_question, inputs=[msg, chatbot], outputs=[msg_hidden, chatbot, table]
    )

if __name__ == "__main__":
    # Add a address string argument that defaults to 127.0.0.1
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--address",
        type=str,
        default="127.0.0.1",
        help="""
        Address to run the server on. 127.0.0.1 for local. 0.0.0.0 for "
        remote or docker
        """,
    )
    # add a port with None default
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port to run the server on",
    )
    parser.add_argument(
        "--username",
        type=str,
        default=None,
        help="Username for basic auth",
    )
    parser.add_argument(
        "--password",
        type=str,
        default=None,
        help="Password for basic auth",
    )
    args = parser.parse_args()

    # Configure auth
    if args.username and args.password:
        auth = (args.username, args.password)
    else:
        auth = None

    # Launch UI
    ui.launch(server_name=args.address, server_port=args.port, auth=auth)
