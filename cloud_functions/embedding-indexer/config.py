"""
User Configuration
"""

EMBEDDING_MODEL = "text-embedding-ada-002"  # Name of OpenAI embedding model
PINECONE_INDEX_NAME = "openai-embedding-index2"  # Get in Pinecone console
MAX_TOKENS_INPUT = 550  # Max number of tokens from input before chunking
TOKEN_CHUNK_SIZE = 450  # Number of tokens to chunk if input is too long
BUCKET_PATH = "gs://[BUCKET]/embedding-indexer"  # bucket path to backup vector
