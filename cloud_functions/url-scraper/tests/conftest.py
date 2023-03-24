import os
import pytest


@pytest.fixture(autouse=True)
def env_setup():
    os.environ["PROJECT_ID"] = "test-project-id"
    os.environ["DESTINATION_TOPIC_ID"] = "test-destination-topic-id"
    yield
    # Clean up after the test
    del os.environ["PROJECT_ID"]
    del os.environ["DESTINATION_TOPIC_ID"]
