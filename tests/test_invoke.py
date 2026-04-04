import operator
import pathlib
from typing import Callable
import pytest

from internal.commands.invoke import command_invoke
from internal.context import TMTContext
from internal.formatting.terminal import TerminalFormatter

from internal.outcomes import (
    EvaluationOutcome,
    EvaluationResult,
)
from internal.commands import command_clean
from internal.commands.gen import command_gen

# fmt: off

def verdict(*args: EvaluationOutcome):
    def predicate(submission: tuple[str], result: EvaluationResult):
        assert result.verdict in args, \
            f"Submission {', '.join(submission)} on testcase {result.codename}: " \
            f"expecting verdict to be one of [{', '.join(map(lambda x: x.value, args))}] (got {result.verdict.value})"
    return predicate

CORRECT   = verdict(EvaluationOutcome.ACCEPTED)
PARTIAL   = verdict(EvaluationOutcome.PARTIAL)
WRONG     = verdict(EvaluationOutcome.WRONG)
NO_FILE   = verdict(EvaluationOutcome.NO_FILE)
NO_OUTPUT = verdict(EvaluationOutcome.NO_OUTPUT)
TLE_CPU   = verdict(EvaluationOutcome.TIMEOUT)
TLE_WALL  = verdict(EvaluationOutcome.TIMEOUT_WALL)
OLE       = verdict(EvaluationOutcome.OUTPUT_LIMIT, EvaluationOutcome.RUNERROR_OUTPUT)
RTE       = verdict(EvaluationOutcome.RUNERROR_MEMORY, EvaluationOutcome.RUNERROR_SIGNAL,
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


class _AttributePredicateFactory:
    def __init__(self, attr_name: str, eq_pred=operator.eq):
        """
        Factory of predicate testing if attribute of an EvaluationResult equals the target value.

        Args:
            attr_name: The target attribute name to be tested.
            eq_pred: The equality function to be used. Default to the built-in equal operator.
        """
        self.attr_name = attr_name
        self.eq_pred = eq_pred

    def __eq__(self, other):
        def predicate(submission: tuple[str], result: EvaluationResult):
            target = getattr(result, self.attr_name)
            assert self.eq_pred(target, other), (
                f"Submission {', '.join(submission)} on testcase {result.codename}: "
                f"expecting {self.attr_name} to be {other!r} (got {target!r})"
            )

        predicate.__name__ = f"{self.attr_name} == {other!r}"
        return predicate


SCORE = _AttributePredicateFactory("score", lambda a, b: abs(a - b) <= 1e-6)
FEEDBACK = _AttributePredicateFactory("feedback")
REASON = _AttributePredicateFactory("reason")


# fmt: off
expected_results_batch_no_testdata = {
    ("model-solution.cpp",):     {},
}

expected_results_batch_cms_checker = {
    ("model-solution.cpp",):     { "1_full_1": (CORRECT,   SCORE == 1,   REASON == "correct reason", FEEDBACK == "correct feedback") },
    ("wrong.cpp",):              { "1_full_1": (WRONG,     SCORE == 0,   REASON == "wrong reason",   FEEDBACK == "wrong feedback") },
    ("partial.cpp",):            { "1_full_1": (PARTIAL,   SCORE == 0.5, REASON == "partial reason", FEEDBACK == "partial feedback") },
    ("checker-crash.cpp",):      { "1_full_1": (CHK_CRASH, SCORE == 0) },
    ("checker-utf8-crash.cpp",): { "1_full_1": (CHK_FAIL,  SCORE == 0) },
    ("checker-fail.cpp",):       { "1_full_1": (CHK_FAIL,  SCORE == 0) },
    ("checker-singal.cpp",):     { "1_full_1": (CHK_CRASH, SCORE == 0) },
    ("checker-timeout.cpp",):    { "1_full_1": (CHK_TLE,   SCORE == 0) },
}

expected_results_batch_cms_whitediff = {
    ("extra-line.py",):          { "1_full_1": (WRONG,   SCORE == 0) },
    ("extra-space.py",):         { "1_full_1": (CORRECT, SCORE == 1) },
    ("extra-token.py",):         { "1_full_1": (WRONG,   SCORE == 0) },
    ("extra-trailing-line.py",): { "1_full_1": (CORRECT, SCORE == 1) },
    ("less-line.py",):           { "1_full_1": (WRONG,   SCORE == 0) },
    ("less-space.py",):          { "1_full_1": (CORRECT, SCORE == 1) },
    ("less-token.py",):          { "1_full_1": (WRONG,   SCORE == 0) },
    ("missing-token.py",):       { "1_full_1": (WRONG,   SCORE == 0) },
    ("model-solution.py",):      { "1_full_1": (CORRECT, SCORE == 1) },
    ("without-last-eol.py",):    { "1_full_1": (CORRECT, SCORE == 1) },
}

expected_results_batch_cms_grader = {
    ("model-solution.cpp",): { "1_full_1": (CORRECT, SCORE == 1) },
    ("model-solution.py",):  { "1_full_1": (CORRECT, SCORE == 1) },
    ("wrong.cpp",):          { "1_full_1": (WRONG,   SCORE == 0) },
    ("wrong.py",):           { "1_full_1": (WRONG,   SCORE == 0) },
}

expected_results_batch_cms_verdict = {
    ("cpp.cpp",):    { "1_full_01": (CORRECT,  SCORE == 1),
                       "1_full_02": (WRONG,    SCORE == 0),
                       "1_full_03": (WRONG,    SCORE == 0), # CMS has no "no output" verdict
                       "1_full_04": (NO_FILE,  SCORE == 0),
                       "1_full_05": (TLE_CPU,  SCORE == 0),
                       "1_full_06": (TLE_WALL, SCORE == 0),
                       "1_full_07": (RTE_EXIT, SCORE == 0),
                       "1_full_08": (RTE_SIG,  SCORE == 0),
                       "1_full_09": (RTE,      SCORE == 0), # CMS has no explicit OLE signal, any RTE is fine here
                       "1_full_10": (RTE_SIG,  SCORE == 0), # We don't send SIGXCPU anymore, just a normal signal
                       "1_full_11": (RTE,      SCORE == 0),
                       "1_full_12": (MLE,      SCORE == 0), },
    ("python3.py",): { "1_full_01": (CORRECT,  SCORE == 1),
                       "1_full_02": (WRONG,    SCORE == 0),
                       "1_full_03": (WRONG,    SCORE == 0), # CMS has no "no output" verdict
                       "1_full_04": (WRONG,    SCORE == 0), # Did not implement this in Python
                       "1_full_05": (TLE_CPU,  SCORE == 0),
                       "1_full_06": (TLE_WALL, SCORE == 0),
                       "1_full_07": (RTE_EXIT, SCORE == 0),
                       "1_full_08": (RTE_SIG,  SCORE == 0),
                       "1_full_09": (RTE,      SCORE == 0), # CMS has no explicit OLE signal, any RTE is fine here
                       "1_full_10": (RTE_SIG,  SCORE == 0), # We don't send SIGXCPU anymore, just a normal signal
                       "1_full_11": (RTE,      SCORE == 0),
                       "1_full_12": (MLE,      SCORE == 0), },
}

expected_results_batch_icpc_checker = {
    # Only test the first file because the second is the same
    ("model-solution.cpp",):  { "1_input_1": (CORRECT,   SCORE == 1, REASON == "correct feedback") },
    ("wrong.cpp",):           { "1_input_1": (WRONG,     SCORE == 0, REASON == "wrong feedback") },
    ("checker-crash.cpp",):   { "1_input_1": (CHK_CRASH, SCORE == 0) },
    ("checker-timeout.cpp",): { "1_input_1": (CHK_TLE,   SCORE == 0) },
}

expected_results_batch_icpc_default_floatcmp = {
    ("model-solution.cpp",):   { "1_full_1": (CORRECT,   SCORE == 1) },
    ("abs1e-4.cpp",):          { "1_full_1": (WRONG,     SCORE == 0) },
    ("abs1e-6.cpp",):          { "1_full_1": (CORRECT,   SCORE == 1) },
    ("abs1e-7.cpp",):          { "1_full_1": (CORRECT,   SCORE == 1) },
    ("rel1e-4.cpp",):          { "1_full_1": (WRONG,     SCORE == 0) },
    ("rel1e-6.cpp",):          { "1_full_1": (CORRECT,   SCORE == 1) },
    ("rel1e-7.cpp",):          { "1_full_1": (CORRECT,   SCORE == 1) },
    ("exact.cpp",):            { "1_full_1": (CORRECT,   SCORE == 1) },
    ("no-setprecision.cpp",):  { "1_full_1": (WRONG,     SCORE == 0) },
}

expected_results_communication_1_proc_grader_stdio = {
    ("model-solution.cpp",): { "1_full_1": (CORRECT,   SCORE == 1) },
    ("exit-0.cpp",):         { "1_full_1": (WRONG,     SCORE == 0) },
    ("exit-1.cpp",):         { "1_full_1": (RTE_EXIT,  SCORE == 0) },
    ("sleep.cpp",):          { "1_full_1": (TLE_WALL,  SCORE == 0) },
}

expected_results_communication_2_proc_grader_stdio = {
    ("model-solution.cpp",):       { "1_full_1": (CORRECT,   SCORE == 1) },
    ("first-proc-exit-0.cpp",):    { "1_full_1": (WRONG,     SCORE == 0) },
    ("first-proc-exit-1.cpp",):    { "1_full_1": (RTE_EXIT,  SCORE == 0) },
    ("second-proc-exit-0.cpp",):   { "1_full_1": (WRONG,     SCORE == 0) },
    ("second-proc-exit-1.cpp",):   { "1_full_1": (RTE_EXIT,  SCORE == 0) },
    ("one-side-cpu.cpp",):         { "1_full_1": (CORRECT,   SCORE == 1) },
    ("two-side-cpu.cpp",):         { "1_full_1": (TLE_CPU,   SCORE == 0) },
    ("one-side-sleep-short.cpp",): { "1_full_1": (CORRECT,   SCORE == 1) },
    ("two-side-sleep-short.cpp",): { "1_full_1": (CORRECT,   SCORE == 1) },
    ("one-side-sleep-long.cpp",):  { "1_full_1": (TLE_WALL,  SCORE == 0) },
    ("two-side-sleep-long.cpp",):  { "1_full_1": (TLE_WALL,  SCORE == 0) },
}

expected_results_outputonly_basic = {
    ("dirtest",):     { "0": (WRONG,   SCORE == 0),
                        "1": (PARTIAL, SCORE == 0.5),
                        "2": (CORRECT, SCORE == 1),
                        "3": (NO_FILE,) },
    ("dirtest/0.out", "dirtest/1.out", "dirtest/2.out"):
                      { "0": (WRONG,   SCORE == 0),
                        "1": (PARTIAL, SCORE == 0.5),
                        "2": (CORRECT, SCORE == 1),
                        "3": (NO_FILE,) },
    ("ziptest.zip",): { "0": (NO_FILE,),
                        "1": (WRONG,   SCORE == 0),
                        "2": (PARTIAL, SCORE == 0.5),
                        "3": (CORRECT, SCORE == 1),
                        "4": (NO_FILE,) },
}
@pytest.mark.parametrize(
    "problem_path, expected_results",
    [
        ("problems/batch/no-testdata",   expected_results_batch_no_testdata),
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
def test_invoke(
    problem_path: str,
    expected_results: dict[tuple[str], dict[str, tuple[Callable[[EvaluationResult], None]]]],
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
            assert False, f"Submission file {submission} is a single string: please put it inside a tuple"
        assert isinstance(submission, tuple)
        submission_files = list(map(form_submission_fullpath, submission))

        invoke_summary = command_invoke(formatter=formatter,
                                        context=context,
                                        show_reason=False,
                                        submission_files=submission_files)

        for codename, predicates in expected_result.items():
            invoke_result = invoke_summary.testcase_results[codename]
            assert invoke_result is not None
            for pred in predicates:
                pred(submission, invoke_result)
