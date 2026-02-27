import pathlib
import os
import subprocess

from internal.formatting import Formatter
from internal.context import TMTContext, SandboxDirectory
from internal.outcomes import (
    EvaluationOutcome,
    EvaluationResult,
    eval_outcome_to_run_outcome,
)
from internal.steps.solution import SolutionStep, make_solution_step
from internal.steps.checker.icpc import ICPCCheckerStep
from internal.steps.interactor import ICPCInteractorStep


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
        self.compilation_error: bool = False

    def __bool__(self):
        if self.directory_error or self.compilation_error:
            return False

        # TODO this should check for expected verdicts; right now only failures are checked against
        def predicate(result: EvaluationResult):
            return result not in [
                EvaluationOutcome.MANAGER_CRASHED,
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


def command_invoke(
    *,
    formatter: Formatter,
    context: TMTContext,
    show_reason: bool,
    submission_files: list[str],
) -> CommandInvokeSummary:

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

    solution_step: SolutionStep = make_solution_step(
        solution_type=context.config.solution.type,
        context=context,
        sandbox=sandbox,
        is_generation=False,
        submission_files=actual_files,
    )

    interactor_step = None
    if context.config.interactor is not None:
        interactor_step = ICPCInteractorStep(context=context, sandbox=sandbox)

    # TODO manager

    # TODO option to skip_checker:
    checker_step = ICPCCheckerStep(context=context, sandbox=sandbox)
    checker_step.check_unused_checker(formatter)

    formatter.print("Solution    compile ")
    solution_compilation_result = solution_step.compile_solution()
    formatter.print_compile_result(solution_compilation_result)
    if not solution_compilation_result:
        return summary.compilation_fail()

    if interactor_step is not None:
        formatter.print("Interactor  compile ")
        interactor_compilation_result = interactor_step.compile()
        formatter.print_compile_result(
            interactor_compilation_result, name=interactor_step.interactor_name
        )
        if not interactor_compilation_result:
            return summary.compilation_fail()

    # TODO manager

    if checker_step is not None:
        formatter.print("Checker     compile ")
        checker_compilation_result = checker_step.compile()
        formatter.print_compile_result(
            checker_compilation_result, name=checker_step.checker_name
        )
        if not checker_compilation_result:
            return summary.compilation_fail()

    all_testcases = [
        test.test_name
        for testset in context.recipe.testsets.values()
        for test in testset.tests
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

    codename_length = max(map(len, available_testcases)) + 2

    for codename in available_testcases:
        formatter.print(" " * 4)
        formatter.print_fixed_width(codename, width=codename_length)

        formatter.print("sol ")
        if interactor_step is None:
            solution_result = solution_step.run_solution(codename)
        else:
            solution_result = interactor_step.run_solution(
                solution_step,
                codename,
            )
        formatter.print_exec_result(eval_outcome_to_run_outcome(solution_result))
        formatter.print(
            f"{solution_result.solution_cpu_time_sec:6.3f} s / {solution_result.solution_max_memory_kib / 1024:5.4g} MiB  "
        )

        with open(
            os.path.join(context.path.logs_invocation, f"{codename}.sol.log"), "w+"
        ) as f:
            f.write(solution_result.checker_reason)

        # TODO option to skip_checker
        if checker_step is not None:
            formatter.print("check ")
            testcase_input = os.path.join(
                context.path.testcases, context.construct_input_filename(codename)
            )
            testcase_answer = os.path.join(
                context.path.testcases, context.construct_output_filename(codename)
            )
            checker_arguments = (
                context.config.checker.arguments
                if context.config.checker is not None
                else []
            )
            solution_result = checker_step.run_checker(
                checker_arguments,
                solution_result,
                testcase_input,
                testcase_answer,
            )

        formatter.print_checker_status(solution_result)
        formatter.print_checker_verdict(solution_result, print_reason=show_reason)
        formatter.println()

        summary.testcase_results[codename] = solution_result

    return summary
