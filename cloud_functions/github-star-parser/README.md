# GitHub Stars Parser Cloud Function
---

This directory contains a script to parse all of your GitHub Starred repository READMEs and push new notes to  Google Cloud Pub/Sub. It uses Google Cloud Firestore as a database to maintain which notes it already processed. 

## Environment Setup
- Enable Google Cloud Pub/Sub + API
- Enable Google Cloud Firestore + API
- If running locally:
    - Install and configure Google Cloud SDK
    - Create virtual env and install requirements: `pip install -r requirements-dev.txt`

## GitHub Token Setup

### Create a Token

Go to [your GitHub tokens page](https://github.com/settings/tokens) and add a Personal access
token. Provide it `public_repo` access.

### Test Token 

Set the following environment variables:
- `GITHUB_USERNAME`
- `GITHUB_TOKEN`
- `PROJECT_ID`

And try running `main.py` directly, configuring arguments accordingly by viewing them with `-h`.

### Add Token to Cloud Function

When you are deploying the cloud function, add the environment variables listed above to the cloud function's environment variables.