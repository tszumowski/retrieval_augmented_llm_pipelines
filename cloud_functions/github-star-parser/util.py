"""
Util functions for the GitHub Star Parser Cloud Function.
"""
import re


def clean_text(input_text: str) -> str:
    """
    Cleans the text by removing HTML tags and replacing any double \ with single \.

    Args:
        input_text: The text to clean.

    Returns:
        text: The cleaned text.

    """
    # Remove HTML tags
    text = re.sub(r"<.*?>", "", input_text)

    # Remove any funny characters
    text = text.encode("ascii", "ignore").decode()

    # replace any double \ with single \
    text = text.replace("\\t", "\t").replace("\t", " ")
    text = text.replace("\\n", "\n").replace("\n", " ")

    # Replace all duplicate spaces with single space
    text = " ".join(text.split())

    # Remove any leading or trailing spaces
    text = text.strip()

    return text
