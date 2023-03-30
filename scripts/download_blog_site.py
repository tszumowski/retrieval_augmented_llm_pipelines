"""
Example of how to scrape a blog site for all posts in html form.

Specifically, it downloads the HTML for each blog post on https://ofdollarsanddata.com/,
and saves each blog post found to a file named after the page number and the url.
This can be used for any blog site that has a list of blog posts in a paginated format.

This can be useful for this repository as it provides a way to get the HTML for each
blog post. Then the HTML can be parsed to get the text, and then the text can be
indexed. It serves as one input to `backfill_html.py`.

"""

import requests
import os
from bs4 import BeautifulSoup
from tqdm import tqdm


def get_page(url):
    """
    Get the HTML for the given url.
    """
    response = requests.get(url)
    return response.text


def get_links(page, link_match_text):
    """
    Get the links from the given page.
    """
    soup = BeautifulSoup(page, "html.parser")
    links = soup.find_all("a", text=link_match_text)
    return links


def get_link_text(link):
    """
    Get the text of the given link.
    """
    return link.text


def get_link_url(link):
    """
    Get the url of the given link.
    """
    return link["href"]


def get_link_html(link):
    """
    Get the HTML for the page the given link links to.
    """
    link_url = get_link_url(link)
    return get_page(link_url)


def write_html_to_file(html, filename):
    """
    Write the given HTML to a file with the given filename.
    """
    with open(filename, "w") as file:
        file.write(html)


def main(
    base_url: str, start_page: int, end_page: int, link_match_text: str, output_dir: str
):
    """
    Scrape the pages from start_page to end_page.
    Find matching text, and then download the HTML for the page it links to.

    Args:
        base_url (str): The base url to scrape.
        start_page (int): The first page to scrape.
        end_page (int): The last page to scrape.
        link_match_text (str): The text to match in the link.
        output_dir (str): The directory to save the files to.
    """
    # Make output dir
    os.makedirs(output_dir, exist_ok=True)

    for page_number in range(start_page, end_page + 1):
        page_url = f"{base_url}/{page_number}"
        page = get_page(page_url)
        links = get_links(page, link_match_text)
        for link in tqdm(links):
            link_url = get_link_url(link)
            # Get last part of url, which is the slug.
            if link_url.endswith("/"):
                link_url = link_url[:-1]
            link_url = link_url.split("/")[-1]
            link_html = get_link_html(link)
            filename = f"{output_dir}/{page_number:02}-{link_url}.html"
            write_html_to_file(link_html, filename)


if __name__ == "__main__":
    # custom variables
    base_url = "https://ofdollarsanddata.com/page/"
    start_page = 1
    end_page = 35
    link_match_text = "Read More"
    output_dir = "ofdollarsanddata"

    main(base_url, start_page, end_page, link_match_text, output_dir)
