# personal_semantic_search_pipelines

Serverless OpenAI+ChatGPT+Pinecone cloud-based pipelines to embed and index all the
things for a personal semantic search engine. AKA Retrieval-Augmented
Language Model (RaLM).

\*\*Check out the [(DRAFT) Medium articles](https://medium.com/@tszumowski/dddd-6abda7f3c6e1) for a full walkthrough!

# What Is It?

This repository is a collection of scripts and modules that:

- create pipelines to embed and store content from various sources for LLM usage
  - Specifically, it:
    - fetches documents
    - embeds them
    - Stores in a Pinecone Vector Store
- various scripts to experiment with retrieval and chat capabilities using the built
  Pinecone vector store

The scripts serve as pipelines that can execute in a serverless manner using
Google Cloud Platform (GCP) products.

# How is this Different from Other LLM Apps / Tutorials?

The majority of LLM / ChatGPT articles and repos out there (to-date) tend to focus on
how to use the LLM. They often assume you already have a static corpus of documents that
you wish to index and chat with. While this repo has scripts that demonstrate LLMs,
the focus is rather around how to build a serverless streaming architecture that
automatically ingests new content relevant to you over time. Specifically, this aggregates
various sources like: email newsletters, Evernote, GitHub starred repos, Liked YouTube
videos, etc. It auto-indexes them so you can chat with your content as it flows in.

# Navigation

- `appsscript`:
  - a Google Apps Script that connects content from GMail to Pub/Sub so that downstream
    functions can process it.
- `cloud_functions`:
  - Multiple Cloud Functions hooked into schedules or Pub/Sub to extract document text,
    embed it, and insert into Pinecone Vector Store. These serve as the building blocks
    that are connected together to create the Serverless pipes. More context in the Medium
    articles!
    - `url-scraper`: Connects to Pub/Sub to catch emails or docs sent to it. It scrapes
      all URLs in it and then sends the text from those URLs to Pub/Sub for indexing.
      - Note: this also has the ability to parse YouTube URLs! It transcribes them and then
        sends the transcription text off to Pub/Sub.
    - `evernote-parser`: Scheduled Cloud Function that periodically looks for new Evernote
      notes, extracts text, an sends it to the embedding indexer via Pub/Sub
    - `github-star-parser`: Scheduled Cloud Function that periodically looks for new
      starred GitHub repositories in your account, extracts text, and sends to the
      embedding indexer via Pub/Sub
    - `embedding-indexer`: Catches text from Pub/Sub, chunks it, embeds it, and stores
      with metadata in Pinecone.
- `scripts`:
  - Various scripts to chat with your data, test retrieval
  - See `Gradio Application` below for an end-to-end UI experience in chatting with your
    data. See the Medium articles posted at the top for more context.

# Gradio Application

The `scripts/app` directory contains code to deploy this as a Gradio application.
For details on using gradio with applications like this, check out my Medium article:
[Vocaltales: Going the Extra Mile](https://medium.com/@tszumowski/vocaltales-going-the-extra-mile-adventures-in-deploying-a-chatgpt-openai-app-the-hard-way-b566d1bbc6fa).

## Local Run

You can run locally by creating a virtual environment, installing the pip requirements
and then running with `python scripts/app/app.py`. See the header of the script
for setup. Once running, navigate to `http://127.0.0.1:7860/`

You can also build the Dockerfile and run that way:

```
cd scripts/app
docker build -t ralm-app .
docker run -it --rm \
    -e OPENAI_API_KEY=<openai-api-key> \
    -e PINECONE_API_KEY=<pinecone-api-key> \
    -p 7860:7860 \
    ralm-app \
    python app.py \
    --address=0.0.0.0 \
    --port=7860 \
    --username=<username> \
    --password=<password>
```

Fill in `<>` field as desired. Run. Then navigate to `http://127.0.0.1:<port>`.

## Deploying

You can follow the guide [here](https://medium.com/@tszumowski/vocaltales-going-the-extra-mile-adventures-in-deploying-a-chatgpt-openai-app-the-hard-way-b566d1bbc6fa)
for multiple ways of deploying.

In this example we will push to GCP and deploy via Cloud Build via authentication.

First, build with:

```
docker tag ralm-app gcr.io/<project-id>/ralm-app
docker push gcr.io/<project-id>/ralm-app
```

(Here, ralm stands for "retrieval augmented language model")

Then deploy with:

```
gcloud run deploy ralm-app \
    --image gcr.io/<project-id>/ralm-app \
    --platform managed \
    --set-env-vars=OPENAI_API_KEY=<openai-key-string>,PINECONE_API_KEY=<pinecone-api-key> \
    --allow-unauthenticated \
    --port=7860 \
    --cpu=1 \
    --memory=512Mi \
    --min-instances=0 \
    --max-instances=3 \
    --command="python" \
    --args="app.py,--address=0.0.0.0,--port=7860,--username=<username>,--password=<password>"
```

Don't forget to fill in the `<>` fields.
