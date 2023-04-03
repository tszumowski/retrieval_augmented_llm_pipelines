"""
Script to confirm the Evernote access token is valid.
Type `python confirm_access_token.py --help` for more information.
"""
import argparse
import evernote.edam.userstore.constants as UserStoreConstants

from evernote.api.client import EvernoteClient


def confirm_evernote_access_token(
    access_token: str,
    sandbox: bool,
    china: bool = False,
) -> bool:
    """
    Confirms that the Evernote access token is valid by
    connecting and listing notebooks.

    Args:
        access_token: Evernote access token
        sandbox: Use sandbox.evernote.com
        china: Use app.yinxiang.com

    Returns:
        valid: True if token is valid
    """
    # Create client
    client = EvernoteClient(token=access_token, sandbox=sandbox, china=china)

    # Check that the version is up to date
    user_store = client.get_user_store()
    version_ok = user_store.checkVersion(
        "Evernote EDAMTest (Python)",
        UserStoreConstants.EDAM_VERSION_MAJOR,
        UserStoreConstants.EDAM_VERSION_MINOR,
    )
    print(f"Is my Evernote API version up to date? {version_ok}\n")
    if not version_ok:
        return False

    # List all of the notebooks in the user's account
    note_store = client.get_note_store()
    notebooks = note_store.listNotebooks()
    print("Found ", len(notebooks), " notebooks:")
    for notebook in notebooks:
        print(f"  * {notebook.name}")

    return True


if __name__ == "__main__":
    # Parse args
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--access_token",
        type=str,
        required=True,
        help="Evernote access token",
    )
    parser.add_argument(
        "--sandbox",
        type=bool,
        required=True,
        help="Use sandbox.evernote.com",
    )
    parser.add_argument(
        "--china",
        type=bool,
        required=False,
        help="Use app.yinxiang.com",
    )
    args = parser.parse_args()

    # Confirm access token
    confirm_evernote_access_token(
        access_token=args.access_token,
        sandbox=args.sandbox,
        china=args.china,
    )
