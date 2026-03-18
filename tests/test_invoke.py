import pathlib
import pytest

from internal.commands.invoke import command_invoke
from internal.context import TMTContext
from internal.formatting.terminal import TerminalFormatter

from internal.outcomes import (
    EvaluationOutcome,
    GenerationResult,
)
from internal.commands import command_clean
from internal.commands.gen import command_gen

AC = EvaluationOutcome.ACCEPTED
PC = EvaluationOutcome.PARTIAL
WA = EvaluationOutcome.WRONG
NO_FILE = EvaluationOutcome.NO_FILE
NO_OUTPUT = EvaluationOutcome.NO_OUTPUT
TLE_CPU = EvaluationOutcome.TIMEOUT
TLE_WALL = EvaluationOutcome.TIMEOUT_WALL
# TODO: think a better name for that
# OLE = EvaluationOutcome.OUTPUT_LIMIT
# RTE_OUTPUT = EvaluationOutcome.RUNERROR_OUTPUT
RTE_OUTPUT = EvaluationOutcome.RUNERROR_OUTPUT
RTE_SIG = EvaluationOutcome.RUNERROR_SIGNAL
MLE = EvaluationOutcome.RUNERROR_MEMORY
RTE_EXIT = EvaluationOutcome.RUNERROR_EXITCODE
MANAGER_CRASH = EvaluationOutcome.MANAGER_CRASHED
MANAGER_FAIL = EvaluationOutcome.MANAGER_FAILED
MANAGER_TLE = EvaluationOutcome.MANAGER_TIMEOUT
CHECKER_CRASH = EvaluationOutcome.CHECKER_CRASHED
CHECKER_FAIL = EvaluationOutcome.CHECKER_FAILED
CHECKER_TLE = EvaluationOutcome.CHECKER_TIMEDOUT

# fmt: off
expected_results_batch_cms_whitediff = {
    "extra_line.py":          { "1_full_1": (WA, 0.0) },
    "extra_space.py":         { "1_full_1": (AC, 1.0) },
    "extra_token.py":         { "1_full_1": (WA, 0.0) },
    "extra_trailing_line.py": { "1_full_1": (AC, 1.0) },
    "less_line.py":           { "1_full_1": (WA, 0.0) },
    "less_space.py":          { "1_full_1": (AC, 1.0) },
    "less_token.py":          { "1_full_1": (WA, 0.0) },
    "missing_token.py":       { "1_full_1": (WA, 0.0) },
    "model_solution.py":      { "1_full_1": (AC, 1.0) },
    "without_last_eol.py":    { "1_full_1": (AC, 1.0) },
}

@pytest.mark.parametrize(
    "problem_path, expected_results",
    [
        ("problems/batch/cms-whitediff", expected_results_batch_cms_whitediff),
    ],
)
# fmt: on
def test_gen(
    problem_path: str,
    expected_results: dict[str, dict[str, GenerationResult]],
):
    script_dir = pathlib.Path(__file__).parent.parent.resolve()
    problem_dir = pathlib.Path(__file__).parent.resolve() / problem_path
    formatter = TerminalFormatter()
    context = TMTContext(str(problem_dir), str(script_dir))

    command_clean(formatter=formatter, context=context, skip_confirm=True)
    command_gen(formatter=formatter, context=context, verify_hash=False, show_reason=False)

    for submission, expected_result in expected_results.items():
        invoke_summary = command_invoke(formatter=formatter,
                                        context=context,
                                        show_reason=False,
                                        submission_files=[str(problem_dir / "solutions" / submission)])

        for codename, expected_invoke_result in expected_result.items():
            expected_verdict, score_predicate = expected_invoke_result
            invoke_result = invoke_summary.testcase_results[codename]
            assert invoke_result is not None
            assert invoke_result.verdict == expected_verdict
            if isinstance(score_predicate, float):
                assert invoke_result.score == score_predicate
            else:
                assert score_predicate(invoke_result.score)
