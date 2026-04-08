import pytest
from io import StringIO, BytesIO
from textwrap import dedent

from internal.commands.make_public import filter_secret


@pytest.mark.parametrize(
    "input, expected",
    [
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
        (
            "ends echo",
            "ends echo",
        ),
    ],
)
def test_grader_filter_normal(input: str, expected: str):
    in_stream = StringIO(input)
    out_stream = BytesIO()

    filter_secret(out_stream, in_stream, "testfile")

    assert expected == out_stream.getvalue().decode()


@pytest.mark.parametrize(
    "input",
    [
        "// BEGIN SECRT",
        "grader content: BEGIN - SECRET",
        "en secret",
        "wHAT iS bEGiN sEReCT ??????",
        "BEND SECRET",
        "being secretary",
        "this  makes  both  ends     created",
    ],
)
def test_grader_filter_error(input: str):
    in_stream = StringIO(input)
    out_stream = BytesIO()

    with pytest.raises(RuntimeError):
        filter_secret(out_stream, in_stream, "testfile")
