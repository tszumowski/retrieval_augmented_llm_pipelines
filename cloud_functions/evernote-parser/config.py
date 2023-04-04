"""
User Configuration
"""

COLLECTION_NAME = "SandboxEvernoteNotesProcessed"  # Remove "Sandbox" for production
NOTEBOOKS = [
    "Software",
    "Recommenders",
    "Economics",
    "Deep Learning",
    "Embeddings",
    "Machine Learning",
    "Deployment / Data Pipelines",
    "Data Science",
    "Math/Stats",
    "RL/Bandits/BayesOpt",
    "Causal Inference / Counterfactuals",
    "Forecasting",
    "Marketing",
    "Indexer",
]  # List of Evernote notebooks to scrape
PUBSUB_TOPIC = "url-scraper"  # Pub/Sub topic to send records to
EVERNOTE_SANDBOX = True  # Set to False for production
EVERNOTE_CHINA = False
