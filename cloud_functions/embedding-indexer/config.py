"""
User Configuration
"""

EMBEDDING_MODEL = "text-embedding-ada-002"  # Name of OpenAI embedding model
PINECONE_INDEX_NAME = "openai-embedding-index"  # Get in Pinecone console
PINECONE_ENV_NAME = "us-east1-gcp"  # Get next to API key in Pinecone console
MAX_TOKENS_PER_EMBEDDING_REQUEST = 380  # Max number of tokens per OpenAI embedding, max is 8191 from https://platform.openai.com/docs/guides/embeddings/what-are-embeddings  # NOQA
