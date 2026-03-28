import pathlib
from typing import Callable
import pytest

from internal.commands.invoke import command_invoke
from internal.context import TMTContext
from internal.formatting.terminal import TerminalFormatter

from internal.outcomes import (
    EvaluationOutcome,
    EvaluationResult,
    GenerationResult,
)
from internal.commands import command_clean
from internal.commands.gen import command_gen


# fmt: off
def verdict(outcome: EvaluationOutcome):
    def predicate(result: EvaluationResult):
        assert result.verdict == outcome
    return predicate

def verdicts(*args: EvaluationOutcome):
    def predicate(result: EvaluationResult):
        assert result.verdict in args
    return predicate

CORRECT   = verdict(EvaluationOutcome.ACCEPTED)
PARTIAL   = verdict(EvaluationOutcome.PARTIAL)
WRONG     = verdict(EvaluationOutcome.WRONG)
NO_FILE   = verdict(EvaluationOutcome.NO_FILE)
NO_OUTPUT = verdict(EvaluationOutcome.NO_OUTPUT)
TLE_CPU   = verdict(EvaluationOutcome.TIMEOUT)
TLE_WALL  = verdict(EvaluationOutcome.TIMEOUT_WALL)
OLE       = verdicts(EvaluationOutcome.OUTPUT_LIMIT, EvaluationOutcome.RUNERROR_OUTPUT)
RTE       = verdicts(EvaluationOutcome.RUNERROR_MEMORY, EvaluationOutcome.RUNERROR_SIGNAL,
                     EvaluationOutcome.RUNERROR_EXITCODE, EvaluationOutcome.RUNERROR_OUTPUT)
MLE       = verdict(EvaluationOutcome.RUNERROR_MEMORY)
RTE_SIG   = verdict(EvaluationOutcome.RUNERROR_SIGNAL)
RTE_EXIT  = verdict(EvaluationOutcome.RUNERROR_EXITCODE)
MGR_CRASH = verdict(EvaluationOutcome.MANAGER_CRASHED)
MGR_FAIL  = verdict(EvaluationOutcome.MANAGER_FAILED)
MGR_TLE   = verdict(EvaluationOutcome.MANAGER_TIMEOUT)
CHK_CRASH = verdict(EvaluationOutcome.CHECKER_CRASHED)
CHK_FAIL  = verdict(EvaluationOutcome.CHECKER_FAILED)
CHK_TLE   = verdict(EvaluationOutcome.CHECKER_TIMEDOUT)
# fmt: on


def score_eq(score: float):
    def predicate(result: EvaluationResult):
        assert abs(result.score - score) <= 1e-6

    return predicate


def score_geq(score: float):
    def predicate(result: EvaluationResult):
        assert result.score >= score - 1e-6

    return predicate


def score_leq(score: float):
    def predicate(result: EvaluationResult):
        assert result.score <= score + 1e-6

    return predicate


def feedback(feedback: str):
    def predicate(result: EvaluationResult):
        assert result.override_verdict_display is not None
        assert feedback in result.override_verdict_display

    return predicate


def reason(reason: str):
    def predicate(result: EvaluationResult):
        assert reason in result.reason

    return predicate


full_score = score_eq(1.0)
zero_score = score_eq(0.0)

# fmt: off
expected_results_batch_cms_checker = {
    "model-solution.cpp":     { "1_full_1": (CORRECT,   full_score,
                                             reason("correct reason"), feedback("correct feedback")) },
    "wrong.cpp":              { "1_full_1": (WRONG,     zero_score,
                                             reason("wrong reason"), feedback("wrong feedback")) },
    "partial.cpp":            { "1_full_1": (PARTIAL,   score_eq(0.5),
                                             reason("partial reason"), feedback("partial feedback")) },
    "checker-crash.cpp":      { "1_full_1": (CHK_CRASH, zero_score) },
    "checker-utf8-crash.cpp": { "1_full_1": (CHK_FAIL,  zero_score) },
    "checker-fail.cpp":       { "1_full_1": (CHK_FAIL,  zero_score) },
    "checker-singal.cpp":     { "1_full_1": (CHK_CRASH, zero_score) },
    "checker-timeout.cpp":    { "1_full_1": (CHK_TLE,   zero_score) },
}

expected_results_batch_cms_whitediff = {
    "extra-line.py":          { "1_full_1": (WRONG,   zero_score) },
    "extra-space.py":         { "1_full_1": (CORRECT, full_score) },
    "extra-token.py":         { "1_full_1": (WRONG,   zero_score) },
    "extra-trailing-line.py": { "1_full_1": (CORRECT, full_score) },
    "less-line.py":           { "1_full_1": (WRONG,   zero_score) },
    "less-space.py":          { "1_full_1": (CORRECT, full_score) },
    "less-token.py":          { "1_full_1": (WRONG,   zero_score) },
    "missing-token.py":       { "1_full_1": (WRONG,   zero_score) },
    "model-solution.py":      { "1_full_1": (CORRECT, full_score) },
    "without-last-eol.py":    { "1_full_1": (CORRECT, full_score) },
}

expected_results_batch_cms_grader = {
    "model-solution.cpp": { "1_full_1": (CORRECT, full_score) },
    "model-solution.py":  { "1_full_1": (CORRECT, full_score) },
    "wrong.cpp":          { "1_full_1": (WRONG,   zero_score) },
    "wrong.py":           { "1_full_1": (WRONG,   zero_score) },
}

expected_results_batch_cms_verdict = {
    "cpp.cpp":     { "1_full_01": (CORRECT,  full_score),
                     "1_full_02": (WRONG,    zero_score),
                     "1_full_03": (WRONG,    zero_score), # CMS has no "no output" verdict
                     "1_full_04": (NO_FILE,  zero_score),
                     "1_full_05": (TLE_CPU,  zero_score),
                     "1_full_06": (TLE_WALL, zero_score),
                     "1_full_07": (RTE_EXIT, zero_score),
                     "1_full_08": (RTE_SIG,  zero_score),
                     "1_full_09": (RTE,      zero_score), # CMS has no explicit OLE signal, any RTE is fine here
                     "1_full_10": (RTE_SIG,  zero_score), # We don't send SIGXCPU anymore, just a normal signal
                     "1_full_11": (RTE,      zero_score),
                     "1_full_12": (MLE,      zero_score), },
    "python3.py":  { "1_full_01": (CORRECT,  full_score),
                     "1_full_02": (WRONG,    zero_score),
                     "1_full_03": (WRONG,    zero_score), # CMS has no "no output" verdict
                     "1_full_04": (WRONG,    zero_score), # Did not implement this in Python
                     "1_full_05": (TLE_CPU,  zero_score),
                     "1_full_06": (TLE_WALL, zero_score),
                     "1_full_07": (RTE_EXIT, zero_score),
                     "1_full_08": (RTE_SIG,  zero_score),
                     "1_full_09": (RTE,      zero_score), # CMS has no explicit OLE signal, any RTE is fine here
                     "1_full_10": (RTE_SIG,  zero_score), # We don't send SIGXCPU anymore, just a normal signal
                     "1_full_11": (RTE,      zero_score),
                     "1_full_12": (MLE,      zero_score), },
}

expected_results_batch_icpc_checker = {
    # Only test the first file because the second is the same
    "model-solution.cpp":  { "1_input_1": (CORRECT,   full_score, reason("correct feedback")) },
    "wrong.cpp":           { "1_input_1": (WRONG,     zero_score, reason("wrong feedback")) },
    "checker-crash.cpp":   { "1_input_1": (CHK_CRASH, zero_score) },
    "checker-timeout.cpp": { "1_input_1": (CHK_TLE,   zero_score) },
}

expected_results_batch_icpc_default_floatcmp = {
    "model-solution.cpp":   { "1_full_1": (CORRECT,   full_score) },
    "abs1e-4.cpp":          { "1_full_1": (WRONG,     zero_score) },
    "abs1e-6.cpp":          { "1_full_1": (CORRECT,   full_score) },
    "abs1e-7.cpp":          { "1_full_1": (CORRECT,   full_score) },
    "rel1e-4.cpp":          { "1_full_1": (WRONG,     zero_score) },
    "rel1e-6.cpp":          { "1_full_1": (CORRECT,   full_score) },
    "rel1e-7.cpp":          { "1_full_1": (CORRECT,   full_score) },
    "exact.cpp":            { "1_full_1": (CORRECT,   full_score) },
    "no-setprecision.cpp":  { "1_full_1": (WRONG,     zero_score) },
}

expected_results_communication_1_proc_grader_stdio = {
    "model-solution.cpp": { "1_full_1": (CORRECT,   full_score) },
    "exit-0.cpp":         { "1_full_1": (WRONG,     zero_score) },
    "exit-1.cpp":         { "1_full_1": (RTE_EXIT,  zero_score) },
    "sleep.cpp":          { "1_full_1": (TLE_WALL,  zero_score) },
}

expected_results_communication_2_proc_grader_stdio = {
    "model-solution.cpp":       { "1_full_1": (CORRECT,   full_score) },
    "first-proc-exit-0.cpp":    { "1_full_1": (WRONG,     zero_score) },
    "first-proc-exit-1.cpp":    { "1_full_1": (RTE_EXIT,  zero_score) },
    "second-proc-exit-0.cpp":   { "1_full_1": (WRONG,     zero_score) },
    "second-proc-exit-1.cpp":   { "1_full_1": (RTE_EXIT,  zero_score) },
    "one-side-cpu.cpp":         { "1_full_1": (CORRECT,   full_score) },
    "two-side-cpu.cpp":         { "1_full_1": (TLE_CPU,   zero_score) },
    "one-side-sleep-short.cpp": { "1_full_1": (CORRECT,   full_score) },
    "two-side-sleep-short.cpp": { "1_full_1": (CORRECT,   full_score) },
    "one-side-sleep-long.cpp":  { "1_full_1": (TLE_WALL,  zero_score) },
    "two-side-sleep-long.cpp":  { "1_full_1": (TLE_WALL,  zero_score) },
}

expected_results_outputonly_basic = {
    "dirtest":     { "0": (WRONG,   zero_score),
                     "1": (PARTIAL, score_eq(0.5)),
                     "2": (CORRECT, full_score),
                     "3": (NO_FILE,) },
    ("dirtest/0.out","dirtest/1.out","dirtest/2.out"):
                   { "0": (WRONG,   zero_score),
                     "1": (PARTIAL, score_eq(0.5)),
                     "2": (CORRECT, full_score),
                     "3": (NO_FILE,) },
    "ziptest.zip": { "1": (WRONG,   zero_score),
                     "2": (PARTIAL, score_eq(0.5)),
                     "3": (CORRECT, full_score),
                     "4": (NO_FILE,) },
}
@pytest.mark.parametrize(
    "problem_path, expected_results",
    [
        ("problems/batch/cms-checker",   expected_results_batch_cms_checker),
        ("problems/batch/cms-grader",    expected_results_batch_cms_grader),
        ("problems/batch/cms-verdict",   expected_results_batch_cms_verdict),
        ("problems/batch/cms-whitediff", expected_results_batch_cms_whitediff),
        ("problems/batch/icpc-checker",  expected_results_batch_icpc_checker),
        ("problems/batch/icpc-default-floatcmp", expected_results_batch_icpc_default_floatcmp),
        ("problems/communication/1-proc-grader-stdio", expected_results_communication_1_proc_grader_stdio),
        ("problems/communication/2-proc-grader-stdio", expected_results_communication_2_proc_grader_stdio),
        ("problems/outputonly/basic",    expected_results_outputonly_basic),
    ],
)
# fmt: on
def test_gen(
    problem_path: str,
    expected_results: dict[str | tuple[str], dict[str, tuple[Callable[[GenerationResult], None]]]],
):
    script_dir = pathlib.Path(__file__).parent.parent.resolve()
    problem_dir = pathlib.Path(__file__).parent.resolve() / problem_path
    formatter = TerminalFormatter()
    context = TMTContext(str(problem_dir), str(script_dir))

    # Force shorter trusted step time to speed up unit test
    # TODO document this
    context.config.trusted_step_time_limit_sec = 1.0

    command_clean(formatter=formatter, context=context, skip_confirm=True)
    command_gen(formatter=formatter, context=context, verify_hash=False, show_reason=False)

    def form_submission_fullpath(path: str):
        return str((problem_dir / "solutions" / path).absolute())

    for submission, expected_result in expected_results.items():

        if isinstance(submission, str):
            submission_files = [form_submission_fullpath(submission)]
        elif isinstance(submission, tuple):
            submission_files = list(map(form_submission_fullpath, submission))
        else:
            assert False, "Submission file is neither a string nor a tuple of strings"

        invoke_summary = command_invoke(formatter=formatter,
                                        context=context,
                                        show_reason=False,
                                        submission_files=submission_files)

        for codename, predicates in expected_result.items():
            invoke_result = invoke_summary.testcase_results[codename]
            assert invoke_result is not None
            for pred in predicates:
                pred(invoke_result)
