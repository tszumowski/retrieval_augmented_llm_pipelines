"""
utilities for url-scraper
"""
from bs4 import BeautifulSoup


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
    return main_text.strip()
