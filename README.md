# personal_semantic_search_pipelines
Serverless OpenAI+ChatGPT+Pinecone cloud-based pipelines to embed and index all the things for a personal semantic search engine

TODO: Fill in

# Gradio Application

The `scripts/app` directory contains code to deploy this as a Gradio application.

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