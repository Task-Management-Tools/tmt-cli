import pathlib
from zipfile import ZipFile
import pytest

from internal.commands.make_public import command_make_public
from internal.context import TMTContext
from internal.formatting.terminal import TerminalFormatter

from internal.commands import command_clean
from internal.commands.gen import command_gen


expected_results_communication_2_proc_grader_stdio = {
    "cpp/compile.sh": "_expected_public/compile.sh",
    "cpp/run.sh": "_expected_public/run.sh",
    "cpp/grader.cpp": None,
    "cpp/accumulate.h": None,
    "cpp/accumulate.cpp": None,
}


@pytest.mark.parametrize(
    "problem_path, expected",
    [
        (
            "problems/communication/2-proc-grader-stdio",
            expected_results_communication_2_proc_grader_stdio,
        ),
    ],
)
# fmt: on
def test_make_public(
    problem_path: str,
    expected: dict[str, str | None],
):
    script_dir = pathlib.Path(__file__).parent.parent.resolve()
    problem_dir = pathlib.Path(__file__).parent.resolve() / problem_path
    formatter = TerminalFormatter()
    context = TMTContext(str(problem_dir), str(script_dir))

    command_clean(formatter=formatter, context=context, skip_confirm=True)
    command_gen(
        formatter=formatter, context=context, verify_hash=False, show_reason=False
    )
    command_make_public(formatter=formatter, context=context)

    with ZipFile(problem_dir / "public" / f"{context.config.short_name}.zip", "r") as z:
        for filename, golden_path in expected.items():
            assert filename in z.namelist(), (
                f"Missing file in attachment archive: {filename}"
            )

            if golden_path is not None:
                with z.open(filename) as f:
                    assert f.read() == (problem_dir / golden_path).read_bytes(), (
                        f"Content mismatch: {filename}"
                    )
