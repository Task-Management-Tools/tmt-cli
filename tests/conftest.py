# conftest.py
import _pytest.terminal
import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests; requires vagrant environment",
    )
    parser.addoption("--integration-backend", default="vagrant")


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


_SKIP_NOT_APPLICABLE_MAGIC = "TMT-PYTEST-SKIP-NOT-APPLICABLE"


def skip_not_applicable(reason=""):
    pytest.skip(_SKIP_NOT_APPLICABLE_MAGIC + reason)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()

    if report.skipped and isinstance(report.longrepr, tuple):
        path, lineno, reason = report.longrepr
        if _SKIP_NOT_APPLICABLE_MAGIC in reason:
            reason = reason.replace(_SKIP_NOT_APPLICABLE_MAGIC, "")
            report.longrepr = (path, lineno, reason)
            report.na_marker = True


# Hack, see https://github.com/pytest-dev/pytest/issues/9961
_pytest.terminal._color_for_type["not appcliable"] = "white"
_pytest.terminal.KNOWN_TYPES = (*_pytest.terminal.KNOWN_TYPES, "not appcliable")


def pytest_report_teststatus(report, config):
    if getattr(report, "na_marker", False):
        # return "", "", ""
        return "not appcliable", "-", ("SKIPPED (NOT APPLICABLE)", {"white": True})
