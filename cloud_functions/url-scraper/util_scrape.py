"""
utilities for url-scraper
"""
import re
from bs4 import BeautifulSoup
from typing import List

IGNORE_TERMS = ("unsubscribe", "privacy-policy", "terms", "subscribe", "contact")


def get_main_text(html: str) -> str:
    """
    Get the main text from an HTML document.

    Args:
        html: The HTML document.

    Returns:
        main_text: The main text from the HTML document.
    """
    soup = BeautifulSoup(html, "html.parser")
    main_text = ""
    # Note: en-note is the evernote html export tag that sometimes has the text
    for tag in soup.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6", "en-note"]):
        main_text += tag.get_text() + " "

    # Clean it
    main_text = main_text.strip()
    main_text = clean_text(main_text)

    return main_text


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


def parse_hyperlinks(text: str) -> List[str]:
    """
    Parse hyperlinks from the text.
    The links can be in the form of HTML anchor tags or plain text URLs.

    Args:
        text: The text to parse.

    Returns
        links: A list of links extracted from the text.
    """
    # Define the regex for matching URLs
    url_regex = re.compile(
        r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
    )

    # Extract all links from the text
    html_links = re.findall(
        r'<a [^>]*href=[\'"]?([^\'" >]+)[\'"]?[^>]*>(.*?)</a>', text
    )

    # Extract all links from the text
    text_links = url_regex.findall(text)

    # Filter out links that contain any of the ignore terms
    links = []
    for link, text in html_links:
        if not any(
            term.lower() in link.lower() or term.lower() in text.lower()
            for term in IGNORE_TERMS
        ):
            links.append(link)

    for link in text_links:
        if link not in links and not any(
            term.lower() in link.lower() for term in IGNORE_TERMS
        ):
            links.append(link)

    # strip all variants of \r and \n from each link
    for i, link in enumerate(links):
        link = link.replace("\r", "").replace("\n", "")
        link = link.replace("\\r", "").replace("\\n", "")
        link = link.replace("\\", "")
        link = link.replace("'", "")
        link = link.strip()
        links[i] = link

    return links
