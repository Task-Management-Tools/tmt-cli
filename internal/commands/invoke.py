import pathlib
import os
import subprocess

from internal.formatting import Formatter
from internal.context import TMTContext
from internal.outcome import eval_outcome_to_run_outcome
from internal.steps.solution import SolutionStep, make_solution_step
from internal.steps.checker.icpc import ICPCCheckerStep
from internal.steps.interactor import InteractorStep


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


def command_invoke(
    *,
    formatter: Formatter,
    context: TMTContext,
    show_reason: bool,
    submission_files: list[str],
):
    actual_files = [os.path.join(os.getcwd(), file) for file in submission_files]

    if not (
        os.path.exists(context.path.testcases_summary)
        and os.path.isfile(context.path.testcases_summary)
    ):
        formatter.println(
            formatter.ANSI_RED,
            "Testcase summary does not exist. Please generate the testcases first.",
            formatter.ANSI_RESET,
        )
        return
    with open(context.path.testcases_summary, "rt") as testcases_summary:
        available_testcases = [line.strip() for line in testcases_summary.readlines()]
    unavailable_testcases = [
        testcase
        for testcase in context.recipe.get_all_test_names()
        if available_testcases.count(testcase) == 0
    ]

    assert pathlib.Path(context.path.testcases_summary).exists()
    solution_step: SolutionStep = make_solution_step(
        solution_type=context.config.solution.type,
        context=context,
        is_generation=False,
        submission_files=actual_files,
    )
    formatter.print("Solution    compile ")
    solution_step.prepare_sandbox()
    formatter.print_compile_string_with_exit(solution_step.compile_solution())

    if context.config.interactor is not None:
        interactor_step = InteractorStep(context=context)
        formatter.print("Interactor  compile ")
        formatter.print_compile_string_with_exit(interactor_step.compile_interactor())

    # TODO manager

    # TODO option to skip_checker:
    checker_step = ICPCCheckerStep(context)
    formatter.print("Checker     compile ")
    checker_step.prepare_sandbox()
    formatter.print_compile_string_with_exit(checker_step.compile(), endl=False)

    formatter.print(
        " " * 2,
        "(default)"
        if checker_step.use_default_checker
        else context.config.checker.filename,
        endl=True,
    )

    if context.path.has_checker_directory() and checker_step.use_default_checker:
        formatter.println(
            formatter.ANSI_YELLOW,
            "Warning: Directory 'checker' exists but it is not used by this problem. Check problem.yaml or remove the directory.",
            formatter.ANSI_RESET,
        )

    all_testcases = [
        test.test_name
        for testset in context.recipe.testsets.values()
        for test in testset.tests
    ]
    with open(context.path.testcases_summary, "rt") as testcases_summary:
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

    for testcase in available_testcases:
        formatter.print(" " * 4)
        formatter.print_fixed_width(testcase, width=codename_length)

        formatter.print("sol ")
        solution_result = solution_step.run_solution(testcase)
        formatter.print_exec_result(eval_outcome_to_run_outcome(solution_result))
        formatter.print(
            f"{solution_result.solution_cpu_time_sec:6.3f} s / {solution_result.solution_max_memory_kib / 1024:5.4g} MiB  "
        )

        with open(
            os.path.join(context.path.logs_invocation, f"{testcase}.sol.log"), "w+"
        ) as f:
            f.write(solution_result.checker_reason)

        # TODO option to skip_checker
        # if context.config.checker is not None:
        formatter.print("check ")
        testcase_input = os.path.join(
            context.path.testcases, context.construct_input_filename(testcase)
        )
        testcase_answer = os.path.join(
            context.path.testcases, context.construct_output_filename(testcase)
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

        if solution_result.output_file is not None:
            os.unlink(solution_result.output_file)
