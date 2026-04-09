import pytest
from io import StringIO, BytesIO
from textwrap import dedent

from internal.commands.make_public import filter_secret

from enum import Enum


class FilterResult(Enum):
    WARNING = "warning"
    ERROR = "error"


@pytest.mark.parametrize(
    "input, expected",
    [
        # normal strings
        (
            dedent("""
            // BEGIN SECRET
            this is redacted
            // END SECRET
            public visible, not a secret!
            # BEGIN\tSECRET
            still not visible
            /* END         SECRET */
            """),
            dedent("""
            public visible, not a secret!
            """),
        ),
        ("ends echo", "ends echo"),
        # too similar to begin/end secret -> warning
        ("// BEGIN SECRT", FilterResult.WARNING),
        ("grader content: BEGIN - SECRET", FilterResult.WARNING),
        ("en secret", FilterResult.WARNING),
        ("wHAT iS bEGiN sEReCT ??????", FilterResult.WARNING),
        ("BEND SECRET", FilterResult.WARNING),
        ("being secretary", FilterResult.WARNING),
        ("this  makes  both  ends     created", FilterResult.WARNING),
        # begin/end secret unmatched -> error
        ("BEGIN SECRET\na\nBEGIN SECRET\nEND SECRET", FilterResult.ERROR),
        ("BEGIN SECRET\nEND SECRET\nb\nEND SECRET", FilterResult.ERROR),
        ("END SECRET", FilterResult.ERROR),
        # unclosed begin secret -> error
        ("BEGIN SECRET", FilterResult.ERROR),
        # both begin secret -> error
        ("BEGIN SECRET END SECRET", FilterResult.ERROR),
        # error + warning = error
        ("begin secret\nBEGIN SECRET\na\nBEGIN SECRET\nEND SECRET", FilterResult.ERROR),
    ],
)
def test_grader_filter_normal(input: str, expected: str | FilterResult):
    in_stream = StringIO(input)
    out_stream = BytesIO()

    issues = filter_secret(out_stream, in_stream, "testfile")

    if expected is FilterResult.WARNING:
        assert any(i.warning for i in issues)
    elif expected is FilterResult.ERROR:
        assert any(i.error for i in issues)
        assert issues[0].error  # make sure that reported issue is also an error
    else:
        assert issues == []
        assert expected == out_stream.getvalue().decode()
