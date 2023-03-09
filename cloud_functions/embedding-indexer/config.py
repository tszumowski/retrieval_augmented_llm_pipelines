"""
User Configuration
"""

BATCH_SIZE = 32  # Batch size for inserting indices and
EMBEDDING_MODEL = "text-embedding-ada-002"  # Name of OpenAI embedding model
PINECONE_INDEX_NAME = "openai-embedding-index"  # Get in Pinecone console
PINECONE_ENV_NAME = "us-east1-gcp"  # Get next to API key in Pinecone console
MAX_TOKENS_PER_EMBEDDING_REQUEST = 6500  # Max number of tokens per OpenAI embedding, max is 8191 from https://platform.openai.com/docs/guides/embeddings/what-are-embeddings  # NOQA
N_CHARS_PER_TOKEN = 4  # Number of characters per token, from https://help.openai.com/en/articles/4936856-what-are-tokens-and-how-to-count-them # NOQA
MAX_SPLIT_TRIES = 5  # Max number of times to try to split text into smaller chunks
