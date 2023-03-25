"""
Unit tests for text cleaning functions.
"""
from util_scrape import clean_text


def test_remove_html_tags():
    test_input = "<html><head></head><body><p>Hello, World!</p></body></html>"
    expected_output = "Hello, World!"
    assert clean_text(test_input) == expected_output


def test_replace_double_slash():
    test_input = "This is a\\ttest with\\nslashes."
    expected_output = "This is a test with slashes."
    assert clean_text(test_input) == expected_output


def test_remove_duplicate_spaces():
    test_input = "This  is   a    test     with      multiple spaces."
    expected_output = "This is a test with multiple spaces."
    assert clean_text(test_input) == expected_output


def test_remove_leading_trailing_spaces():
    test_input = "   This is a test with spaces.   "
    expected_output = "This is a test with spaces."
    assert clean_text(test_input) == expected_output


def test_remove_funny_characters():
    test_input = "îø This is a test with funny characters!: åçîøü"
    expected_output = "This is a test with funny characters!:"
    cleaned = clean_text(test_input)
    assert cleaned == expected_output


def test_full_clean():
    test_input = "<html>  This  is\\ta\\nfull test\\n   with <p>HTML tags</p> and \\tspecial characters: åçîøü  </html>"
    expected_output = "This is a full test with HTML tags and special characters:"
    assert clean_text(test_input) == expected_output
