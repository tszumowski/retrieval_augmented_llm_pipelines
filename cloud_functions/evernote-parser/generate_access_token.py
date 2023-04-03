"""
This generates a token for the Evernote API so that it can be used in a script in the future
without requiring user authorization every time.
"""

# https://github.com/Evernote/evernote-sdk-python3/blob/master/sample/client/EDAMTest.py

import argparse
from datetime import datetime
import evernote.edam.userstore.constants as UserStoreConstants
import evernote.edam.notestore.ttypes as NoteStoreTypes

import os

from evernote.api.client import EvernoteClient
from typing import Optional

def get_evernote_access_token(
    consumer_key: str, 
    consumer_secret: str, 
    sandbox: bool = False, 
    china: bool = False
    ) -> str:
    """
    Get an Evernote token for use in a script.
    This access token can be used to access the Evernote API without requiring user authorization.

    This sincludes:
    - Creating an Evernote client
    - Getting a request token, including oauth token and secret
    - Getting the authorization URL
    - Opening the URL in a browser
    - Getting the verifier code from the user
    - Getting the access token


    Args:
        consumer_key: Evernote consumer key
        consumer_secret: Evernote consumer secret
        sandbox: Use sandbox.evernote.com
        china: Use app.yinxiang.com

    Returns:
        token: Evernote token
    """
    access_token = ""

    # Create Client
    client = EvernoteClient(consumer_key=consumer_key, consumer_secret=consumer_secret, sandbox=sandbox, china=china)    

    # Get Request Token. Redirect to Localhost because we don't have a webserver
    request_token = client.get_request_token("http://localhost:8888")

    # Request token is a dict with keys oauth_token and oauth_token_secret
    oauth_token = request_token['oauth_token']
    oauth_token_secret = request_token['oauth_token_secret']    

    # Get the authorization URL
    auth_url = client.get_authorize_url(request_token)

    # Open the URL in a browser
    print("Opening URL in browser: ", auth_url)
    os.system("open " + auth_url)

    # Get the verifier code from the user
    print("Please visit this website to retrieve the oauth verification code after you have authorized:")
    print(auth_url)
    print()
    validated_url = input("Please enter the full URL of the verification page: ")
    oauth_verifier = validated_url.split("oauth_verifier=")[1].split("&")[0]

    # Get the access token
    access_token = client.get_access_token(oauth_token, oauth_token_secret, oauth_verifier)

    return access_token


# main function
if __name__ == "__main__":
    # parse arguments
    parser = argparse.ArgumentParser()
    # consuumer key and secret
    parser.add_argument("--consumer-key", help="Evernote consumer key", required=True)
    parser.add_argument("--consumer-secret", help="Evernote consumer secret", required=True)

    # sandbox or production
    parser.add_argument("--sandbox", help="Use sandbox.evernote.com", action="store_true")

    # output file
    parser.add_argument("--output", help="Output file", required=False)

    args = parser.parse_args()

    # get token
    print("Getting Evernote token...")
    token = get_evernote_access_token(
        consumer_key=args.consumer_key,
        consumer_secret=args.consumer_secret,
        sandbox=args.sandbox,
    )

    print(f"Evernote token: {token}")

    # write to file, optional
    if args.output:
        with open(args.output, "w") as f:
            f.write(token)
