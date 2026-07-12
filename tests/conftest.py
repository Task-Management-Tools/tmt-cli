# conftest.py
import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests; requires vagrant environment",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: mark test as integration. Will not run by default, usually requiring external environment setup.",
    )


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--run-integration"):
        skip = pytest.mark.skip(reason="Use --run-integration to run")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip)
