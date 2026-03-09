# Test for compilation error reporting:
# This test uses LanguageDummy to force generate a compilation error,
# thus, we can check if the step actually fails and collects the compilation error string.
import pathlib
import pytest

from internal.context import TMTContext
from internal.formatting.terminal import TerminalFormatter

from internal.outcomes import (
    CompilationOutcome,
    CompilationResult,
)
from internal.commands import command_clean
from internal.commands.gen import command_gen

from tests.languages.dummy import LanguageDummy
import internal.compilation.languages


@pytest.fixture()
def with_dummy_language():
    original = internal.compilation.languages.languages[:]
    internal.compilation.languages.languages.append(LanguageDummy)
    yield
    internal.compilation.languages.languages = original


class ExpectedCompilation:
    def __init__(self, *, gen=None, val=None, sol=None, check=None, interact=None):
        self.gen = gen
        self.val = val
        self.sol = sol
        self.check = check
        self.interact = interact


OK = CompilationOutcome.SUCCESS
TLE = CompilationOutcome.TIMEDOUT
FAIL = CompilationOutcome.FAILED
SKIP = CompilationOutcome.SKIPPED


@pytest.mark.parametrize(
    "problem_path, expected_results",
    [
        # fmt: off
        ("problems/compile-error/generator", ExpectedCompilation(gen=FAIL)),
        ("problems/compile-error/validator", ExpectedCompilation(gen=OK, val=FAIL)),
        (
            "problems/compile-error/solution",
            ExpectedCompilation(gen=OK, val=OK, sol=FAIL),
        ),
        (
            "problems/compile-error/checker-icpc",
            ExpectedCompilation(gen=OK, val=OK, sol=OK, check=FAIL),
        ),
        (
            "problems/compile-error/interactor-icpc",
            ExpectedCompilation(gen=OK, val=OK, sol=OK, interact=FAIL),
        ),
        # fmt: on
    ],
)
def test_compilation(
    with_dummy_language,
    problem_path: str,
    expected_results: ExpectedCompilation,
):
    script_dir = pathlib.Path(__file__).parent.parent.resolve()
    problem_dir = pathlib.Path(__file__).parent.resolve() / problem_path
    formatter = TerminalFormatter()
    context = TMTContext(str(problem_dir), str(script_dir))

    command_clean(formatter=formatter, context=context, skip_confirm=True)
    command_result = command_gen(
        formatter=formatter, context=context, verify_hash=False, show_reason=False
    )

    # Check for compilation
    def check_compilation(
        expected: CompilationOutcome | None, found: CompilationResult | None
    ):
        if expected is None:
            assert found is None
            return

        assert isinstance(found, CompilationResult)
        assert found.verdict == expected
        if found.verdict == FAIL:
            assert "DUMMY_COMPILATION_ERROR" in found.standard_error

    check_compilation(expected_results.gen, command_result.generation_compilation)
    check_compilation(expected_results.val, command_result.validation_compilation)
    check_compilation(expected_results.sol, command_result.solution_compilation)
    check_compilation(expected_results.check, command_result.checker_compilation)
    check_compilation(expected_results.interact, command_result.interactor_compilation)
