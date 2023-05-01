"""
This script is a simple example of how to use the langchain library
to run a question answering chain on a query and return the results.
It is an example of using LLMs for semantic search.
It is meant to be run from the root of the repo as:
python scripts/try_langchain.py

It leverages the OpenAI API to embed the query and the Pinecone API
to query the index. It also uses the langchain library to run the
question answering chain on the results using the OpenAI API and the Pinecone
search results for context.

"""
import os
import pinecone
import sys

from langchain import OpenAI
from langchain.chains.question_answering import load_qa_chain
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.vectorstores import Pinecone

# add embedding-indexer to pythonpath for config
path = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(path, "..", "cloud_functions", "embedding-indexer"))
import config  # NOQA

"""
INSERT QUERY HERE
"""

QUERY = "What are some ways to protect from Quantum Computer decryption?"

"""
END INSERT QUERY
"""

# Get API Keys from env
API_KEY_OPENAI = os.environ.get("API_KEY_OPENAI")
os.environ["OPENAI_API_KEY"] = API_KEY_OPENAI
API_KEY_PINECONE = os.environ.get("API_KEY_PINECONE")

# Static Config
model_name = "text-embedding-ada-002"

# Create embedder
embed = OpenAIEmbeddings(
    document_model_name=model_name,
    query_model_name=model_name,
    openai_api_key=API_KEY_OPENAI,
)

# Initialize Pinecone VectorStore
pinecone.init(api_key=API_KEY_PINECONE, environment=config.PINECONE_ENV_NAME)
index = pinecone.Index(config.PINECONE_INDEX_NAME)
text_field = "text"
vectorstore = Pinecone(index, embed.embed_query, text_field)

# Set up chain
chain = load_qa_chain(
    OpenAI(), chain_type="stuff"
)  # we are going to stuff all the docs in at once

# Fetch relevant  docs
print(f"\n\nAsking Third Brain:\n{QUERY}\n...\n")
docs = vectorstore.similarity_search(QUERY, top_k=5)

# Run chain with relevant docs
# NOTE: Future release should enrich as part of the system message prompting. TODO.
enriched_query = f"""
You are given a question and a set of documents.
Answer the question in at least four sentences.
Provide specific examples when possible.
Cite when possible.
Prioritize the documents you are provided for context.
But you otherwise may use other knowledge you have.

This is the question: {QUERY}
"""
response = chain.run(input_documents=docs, question=enriched_query)

# Print response
print("Answer:\n")
print(response)
print("\n\nSources:\n")

for i, doc in enumerate(docs, 1):
    metadata = doc.metadata
    print(f"\n{i}:")
    if "source" in metadata:
        print(f"\tSource: {metadata['source']}")
    if "title" in metadata:
        print(f"\tTitle: {metadata['title']}")
    if "url" in metadata:
        print(f"\tURL: {metadata['url']}")
    print("\n")
