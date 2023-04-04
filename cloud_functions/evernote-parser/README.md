# Evernote Notes Parser Cloud Function

---

This directory contains a script to parse any pre-defined Evernote Notebooks and push new notes to Google
Cloud Pub/Sub. It uses Google Cloud Firestore as a database to maintain which notes it already processed.

It uses the Evernote SDK to parse notebook data. That requires some setup.

## WARNING

**WARNING: The Evernote API has an hourly rate-limit! Do not backfill directly. Rather,
export your notebooks as HTML files and use the `parse_html_files.py` function in this
repository to backfill Evernote first. It is what they recommend as well.**

## Environment Setup

- Enable Google Cloud Pub/Sub + API
- Enable Google Cloud Firestore + API
- If running locally:
  - Install and configure Google Cloud SDK
  - Create virtual env and install requirements: `pip install -r requirements-dev.txt`

## Evernote SDK + Token Setup

### Create a Developer Account

Follow directions on the [Evernote Developer page](https://dev.evernote.com/doc/articles/dev_tokens.php)
and generate an app / API key. Note: you'll also need to request production access. Sandbox
access is instant. Production access requires manual approval which can take a few days.

### Generating a Token

Note: This [authentication documentation](https://dev.evernote.com/doc/articles/authentication.php/)
describes the authentication procedure.

Generate an access token with the `cloud_functions/evernote-parser/generate_access_token.py` script.
Type `-h` for usage. It will prompt you to visit a page, authenticate, and paste the URL
into the console.

Save that token key. You will need to place it in your environment variables as `ACCESS_TOKEN_EVERNOTE`.

Note: There is a different token for sandbox and production. They can last up to one year. Set a
reminder to refresh it.

### Test Token

Confirm the token works with the `cloud_functions/evernote-parser/confirm_access_token.py` script.
Type `-h` for usage. Be sure to set or unset `--sandbox` based on the token you generated.

### Add Token to Cloud Function

When you are deploying the cloud function, add the token as `ACCESS_TOKEN_EVERNOTE` and your
google project as `PROJECT_ID` to the cloud function's environment variables.
