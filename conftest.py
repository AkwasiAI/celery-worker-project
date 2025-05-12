import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--gemini-api-key",
        action="store",
        default=None,
        help="Gemini API key for integration tests."
    )


@pytest.fixture
def gemini_api_key(request):
    return request.config.getoption("--gemini-api-key")
