import pathlib
import os
import shutil

from internal.recipe_parser import parse_recipe_data
from internal.utils import is_apport_active
from internal.formatting import Formatter
from internal.context import CheckerType, TMTContext, ProblemType, find_problem_dir
from internal.outcome import (
    EvaluationResult,
    ExecutionOutcome,
    eval_outcome_to_grade_outcome,
    eval_outcome_to_run_outcome,
)

from internal.steps.generation import GenerationStep
from internal.steps.validation import ValidationStep
from internal.steps.solution import SolutionStep, make_solution_step
from internal.steps.checker.icpc import ICPCCheckerStep



def command_invoke(context: TMTContext, args):
    formatter = Formatter()
    actual_files = [os.path.join(os.getcwd(), file) for file in args.submission_files]

    with open(context.path.tmt_recipe) as f:
        recipe = parse_recipe_data(f.readlines())

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
        for testcase in recipe.get_all_test_names()
        if available_testcases.count(testcase) == 0
    ]

    if pathlib.Path(context.path.testcases_summary).exists():
        solution_step: SolutionStep = make_solution_step(
            problem_type=context.config.problem_type,
            context=context,
            is_generation=False,
            submission_files=actual_files,
        )
        checker_step = ICPCCheckerStep(context)

        formatter.print("Solution    compile ")
        solution_step.prepare_sandbox()
        formatter.print_compile_string_with_exit(solution_step.compile_solution())

        if solution_step.has_interactor():
            formatter.print("Interactor  compile ")
            formatter.print_compile_string_with_exit(solution_step.compile_interactor())

        if solution_step.has_manager():
            formatter.print("Manager     compile ")
            formatter.print_compile_string_with_exit(solution_step.compile_manager())

        if not solution_step.skip_checker():
            formatter.print("Checker     compile ")
            checker_step.prepare_sandbox()
            formatter.print_compile_string_with_exit(checker_step.compile(), endl=False)

            formatter.print(' ' * 2,
                            "(default)" if context.config.checker_type is CheckerType.DEFAULT else
                            context.config.checker_filename, endl=True)

            if (
                context.path.has_checker_directory()
                and context.config.checker_type is CheckerType.DEFAULT
            ):
                formatter.println(
                    formatter.ANSI_YELLOW,
                    "Warning: Directory 'checker' exists but it is not used by this problem. Check problem.yaml or remove the directory.",
                    formatter.ANSI_RESET,
                )

    recipe = parse_recipe_data(open(context.path.tmt_recipe).readlines())
    all_testcases = [
        test.test_name for testset in recipe.testsets.values() for test in testset.tests
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

        if not solution_step.skip_checker():
            formatter.print("check ")
            testcase_input = os.path.join(
                context.path.testcases, context.construct_input_filename(testcase)
            )
            testcase_answer = os.path.join(
                context.path.testcases, context.construct_output_filename(testcase)
            )
            solution_result = checker_step.run_checker(
                context.config.checker_arguments,
                solution_result,
                testcase_input,
                testcase_answer,
            )

            formatter.print_checker_status(solution_result)

        formatter.print_checker_verdict(solution_result, print_reason=args.show_reason)
        formatter.println()

        if solution_result.output_file is not None:
            os.unlink(solution_result.output_file)

