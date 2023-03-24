import main
import os

os.environ["PROJECT_ID"] = "test-project-id"
os.environ["DESTINATION_TOPIC"] = "test-destination-topic"


def test_parse_hyperlinks():
    input_text = """
    <html>
        <body>
            <a href="https://example.com">Example</a>
            <a href="https://example.com/unsubscribe">Unsubscribe</a>
            <a href="https://example.com/privacy-policy">Privacy Policy</a>
            <a href="https://example.com/terms-of-service">Terms of Service</a>
        </body>
    </html>
    """

    expected_output = [
        "https://example.com",
    ]

    result = main.parse_hyperlinks(input_text)
    assert result == expected_output


def test_parse_hyperlinks_with_plain_text_links():
    input_text = """
    Check out this cool site: https://example.com
    Do not forget to read our Privacy Policy: https://example.com/privacy-policy
    Terms of Service: https://example.com/terms-of-service
    Unsubscribe: https://example.com/unsubscribe
    And another link: http://example.net
    """

    expected_output = [
        "https://example.com",
        "http://example.net",
    ]

    result = main.parse_hyperlinks(input_text)
    assert result == expected_output


def test_is_youtube_url():
    youtube_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    non_youtube_url = "https://www.example.com"

    assert main.is_youtube_url(youtube_url)
    assert not main.is_youtube_url(non_youtube_url)
