from dataclasses import dataclass
import pathlib
import os
import subprocess

from internal.formatting import Formatter
from internal.context import TMTContext, SandboxDirectory
from internal.outcomes import (
    CompilationResult,
    EvaluationOutcome,
    EvaluationResult,
    eval_outcome_to_run_outcome,
)
import internal.recipe_parser as recipe_parser
from internal.steps.checker import get_checker_step_type
from internal.steps.solution import get_solution_step_type
from internal.steps.utils import CompilationJob, CompilationSlot


def is_apport_active():
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "apport.service"],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout.strip() == "active"
    except FileNotFoundError:
        return False  # systemctl not available


class CommandInvokeSummary:
    def __init__(self):
        self.testcase_results: dict[str, EvaluationResult | None] = {}
        self.directory_error: bool = False
        self.compilation_result: dict[CompilationSlot, CompilationResult] = {}

    def __bool__(self):
        if self.directory_error:
            return False

        def is_compilation_error(cresult: CompilationResult | None):
            return cresult is not None and not cresult

        if any(map(is_compilation_error, self.compilation_result.values())):
            return False

        # TODO this should check for expected verdicts; right now only failures are checked against
        def predicate(result: EvaluationResult):
            return result.verdict not in [
                EvaluationOutcome.MANAGER_CRASHED,
                EvaluationOutcome.MANAGER_FAILED,
                EvaluationOutcome.MANAGER_TIMEOUT,
                EvaluationOutcome.CHECKER_CRASHED,
                EvaluationOutcome.CHECKER_FAILED,
                EvaluationOutcome.CHECKER_TIMEDOUT,
                EvaluationOutcome.INTERNAL_ERROR,
            ]

        return all(map(predicate, self.testcase_results.values()))

    def directory_fail(self):
        self.directory_error = True
        return self

    def compilation_fail(self):
        self.compilation_error = True
        return self


@dataclass
class TestsetResult:
    testset_name: str

    max_score: float | None
    score: float = float("inf")
    verdict: EvaluationOutcome = EvaluationOutcome.RUN_SUCCESS

    worst_testcase: str = None
    num_testcases: int = 0
    expected_testcases: int = 0

    max_cpu_time_sec: float = 0.0
    is_timer_triggered: bool = False

    max_memory_kib: int = -1
    max_memory_upper_bound_kib: int = 0

    def combine(self, other: "EvaluationResult | TestsetResult"):
        if isinstance(other, EvaluationResult):
            self.max_cpu_time_sec, self.is_timer_triggered = max(
                (self.max_cpu_time_sec, self.is_timer_triggered),
                (other.cpu_time_sec, other.timer_triggered),
            )
            if other.score < self.score:
                self.worst_testcase = other.codename
                self.score = other.score
                self.verdict = other.verdict
            self.num_testcases += 1
            self.expected_testcases += 1
            self.max_memory_kib = max(self.max_memory_kib, other.max_memory_kib)
            self.max_memory_upper_bound_kib = max(
                self.max_memory_upper_bound_kib, other.max_memory_upper_bound_kib
            )

        elif isinstance(other, TestsetResult):
            self.max_cpu_time_sec, self.is_timer_triggered = max(
                (self.max_cpu_time_sec, self.is_timer_triggered),
                (other.max_cpu_time_sec, other.is_timer_triggered),
            )
            if other.score < self.score:
                self.worst_testcase = other.worst_testcase
                self.score = other.score
                self.verdict = other.verdict
            self.num_testcases += other.num_testcases
            self.expected_testcases += other.expected_testcases
            self.max_memory_kib = max(self.max_memory_kib, other.max_memory_kib)
            self.max_memory_upper_bound_kib = max(
                self.max_memory_upper_bound_kib, other.max_memory_upper_bound_kib
            )


def command_invoke(
    *,
    formatter: Formatter,
    context: TMTContext,
    show_reason: bool,
    submission_files: list[str],
) -> CommandInvokeSummary:
    context.set_log_directory(context.path.logs_invocation)

    sandbox = SandboxDirectory(context.path.default_sandbox)
    sandbox.create()

    actual_files = [os.path.join(os.getcwd(), file) for file in submission_files]

    summary = CommandInvokeSummary()

    if not (
        os.path.exists(context.path.testcase_summary)
        and os.path.isfile(context.path.testcase_summary)
    ):
        formatter.println(
            formatter.ANSI_RED,
            "Testcase summary does not exist. Please generate the testcases first.",
            formatter.ANSI_RESET,
        )
        return summary.directory_fail()

    with open(context.path.testcase_summary, "rt") as testcases_summary:
        available_testcases = [line.strip() for line in testcases_summary.readlines()]
    unavailable_testcases = [
        testcase
        for testcase in context.recipe.get_all_test_names()
        if available_testcases.count(testcase) == 0
    ]

    assert pathlib.Path(context.path.testcase_summary).exists()

    # Make every steps first
    solution_step_type = get_solution_step_type(
        problem_type=context.config.problem_type,
        judge_convention=context.config.judge_convention,
    )
    solution_step = solution_step_type(
        context=context,
        sandbox=sandbox,
        is_generation=False,
        submission_files=actual_files,
    )

    checker_step_type = get_checker_step_type(
        problem_type=context.config.problem_type,
        judge_convention=context.config.judge_convention,
    )
    if checker_step_type is None:
        checker_step = None
    else:
        checker_step = checker_step_type(
            context=context, sandbox=sandbox, is_generation=False
        )
        checker_step.check_unused_checker(formatter)

    # TODO option to skip_checker:
    def compilation_jobs():
        yield from solution_step.compilation_jobs()
        if checker_step is not None:
            yield CompilationJob(
                CompilationSlot.CHECKER, checker_step.compile, checker_step.checker_name
            )

    for job in compilation_jobs():
        formatter.print(f"{job.slot.value.ljust(10)}  compile ")
        result = job.compile_fn()
        summary.compilation_result[job.slot] = result
        formatter.print_compile_result(result, name=job.display_file)
        if not result:
            return summary

    all_testcases = [
        test.name
        for testset in context.recipe.testsets.values()
        for test in testset.testcases
    ]
    with open(context.path.testcase_summary, "rt") as testcases_summary:
        available_testcases = [line.strip() for line in testcases_summary.readlines()]
    unavailable_testcases = [
        testcase
        for testcase in all_testcases
        if testcase is not None and available_testcases.count(testcase) == 0
    ]

    if len(unavailable_testcases):
        formatter.println(
            formatter.ANSI_YELLOW,
            "Warning: testcases ",
            ", ".join(unavailable_testcases),
            " were not available.",
            formatter.ANSI_RESET,
        )
    if is_apport_active():
        formatter.println(
            formatter.ANSI_YELLOW,
            "Warning: apport is active. Runtime error caused by signal might be treated as wall-clock limit exceeded due to apport crash collector delay.",
            formatter.ANSI_RESET,
        )

    codename_length = max(6, max(map(len, available_testcases))) + 2

    os.makedirs(context.path.logs_invocation, exist_ok=True)

    for codename in available_testcases:
        formatter.print(" " * 4)
        formatter.print_fixed_width(codename, width=codename_length)

        formatter.print("sol ")
        solution_result = solution_step.run_solution(codename)

        formatter.print_exec_result(eval_outcome_to_run_outcome(solution_result))
        formatter.print_exec_details(solution_result, context=context)

        with open(
            os.path.join(context.path.logs_invocation, f"{codename}.sol.log"), "w+"
        ) as f:
            f.write(solution_result.reason)

        # TODO option to skip_checker
        if checker_step is not None:
            formatter.print("check ")
            solution_result = checker_step.run_checker(solution_result, codename)

        formatter.print_checker_status(solution_result)
        formatter.print_testcase_verdict(
            solution_result, context=context, print_reason=show_reason
        )
        formatter.println()

        summary.testcase_results[codename] = solution_result

    testset_results: dict[str, TestsetResult] = {}

    def init_result(testset: recipe_parser.Testset | recipe_parser.Subtask):
        if isinstance(testset, recipe_parser.Subtask):
            return TestsetResult(testset_name=testset.name, max_score=testset.score)
        else:
            return TestsetResult(testset_name=testset.name, max_score=None)

    overall = TestsetResult(testset_name="", max_score=None)

    # Process without dependencies
    for ts in context.recipe.testsets.values():
        ts_res = init_result(ts)
        for testcases in ts.testcases:
            if testcases.name in summary.testcase_results:
                ts_res.combine(summary.testcase_results[testcases.name])
            else:
                ts_res.expected_testcases += 1
        testset_results[ts.name] = ts_res
        overall.combine(ts_res)

    # Include the dependencies
    for ts in reversed(context.recipe.testsets.values()):
        ts_res = init_result(ts)
        for dep_ts in ts.dependency:
            ts_res.combine(testset_results[dep_ts.name])
        ts_res.combine(testset_results[ts.name])
        testset_results[ts.name] = ts_res

    display_testsets = []
    for ts in context.recipe.testsets.values():
        if isinstance(ts, recipe_parser.Subtask):
            display_testsets.append(testset_results[ts.name])
        elif context.config.judge_convention.display_testsets:
            display_testsets.append(testset_results[ts.name])

    formatter.println()
    formatter.print_testset_summary(display_testsets, overall, context)

    return summary
