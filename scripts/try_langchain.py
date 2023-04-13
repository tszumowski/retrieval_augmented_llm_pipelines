"""
pip install tiktoken langchain pinecone-client

TODO: Migrate to the retrieval model langchain uses now. Also, perhaps
no agent needed. Just do direct since then I can return cited sources which the
agent doesn't do yet.
"""
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.vectorstores import Pinecone
from langchain import OpenAI
import os
import sys

from langchain.agents.agent_toolkits import (
    create_vectorstore_agent,
    VectorStoreToolkit,
    VectorStoreInfo,
)

import pinecone

path = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(path, "..", "cloud_functions", "embedding-indexer"))
import config  # NOQA

# Get API Keys from env
API_KEY_OPENAI = os.environ.get("API_KEY_OPENAI")
os.environ["OPENAI_API_KEY"] = API_KEY_OPENAI
API_KEY_PINECONE = os.environ.get("API_KEY_PINECONE")


model_name = "text-embedding-ada-002"

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

# Initialize a vectorestore tookit
vectorstore_info = VectorStoreInfo(
    name="personal_recent_knowledgebase",
    description="""
    personal knowledgebase that can be used for recent information or current
    events for any query
    """,
    vectorstore=vectorstore,
)
toolkit = VectorStoreToolkit(vectorstore_info=vectorstore_info)

# Define an LLM to use
model_name = "text-davinci-003"
llm = OpenAI(temperature=0, model_name=model_name)

# Create vectorstore agent
agent_executor = create_vectorstore_agent(
    llm=llm,
    toolkit=toolkit,
    verbose=True,
)

# query = """
# What is the latest ways to stop the effect of quantum decryption and how is
# government involved?

# Describe in at least two paragraphs. Provide full raw source info including full
# title, date, author, source, and URL where applicable"
# """

query = """
What happened to Samsung regarding leaking data secrets using ChatGPT?
Describe some ways to mitigate that as a bulleted list for others to learn a lesson
from this.

Describe in at least two paragraphs. Provide full raw source info including full
title, date, author, source, and URL where applicable"
"""

agent_executor.run(query)
