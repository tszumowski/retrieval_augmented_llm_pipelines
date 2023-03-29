"""
User Configuration
"""

EMBEDDING_MODEL = "text-embedding-ada-002"  # Name of OpenAI embedding model
PINECONE_INDEX_NAME = "openai-embedding-index"  # Get in Pinecone console
PINECONE_ENV_NAME = "us-east1-gcp"  # Get next to API key in Pinecone console
MAX_TOKENS_INPUT = 450  # Max number of tokens from input before chunking
TOKEN_CHUNK_SIZE = 375  # Number of tokens to chunk if input is too long
