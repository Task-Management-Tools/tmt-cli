import pathlib
import os
import shutil
import hashlib
import json

from internal.recipe_parser import parse_recipe_data
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



def command_gen(*, formatter: Formatter, context: TMTContext, verify_hash: bool, show_reason: bool):
    """Generate test cases in the given directory."""

    if verify_hash and not (
        os.path.exists(context.path.testcases_hashes)
        and os.path.isfile(context.path.testcases_hashes)
    ):
        formatter.println(
            formatter.ANSI_RED,
            "Testcase hashes does not exist. There is nothing to verify.",
            formatter.ANSI_RESET,
        )
        return

    # Compile generators, validators and solutions
    generation_step = GenerationStep(context)
    validation_step = ValidationStep(context)
    run_checker = (
        context.config.problem_type is ProblemType.BATCH
        and context.config.checker_type is not CheckerType.DEFAULT
        and (
            context.config.check_forced_output or context.config.check_generated_output
        )
    )
    if run_checker:
        checker_step = ICPCCheckerStep(context)
    model_solution_full_path = context.path.replace_with_solution(
        context.config.model_solution_path
    )

    solution_step: SolutionStep = make_solution_step(
        problem_type=context.config.problem_type,
        context=context,
        is_generation=True,
        submission_files=[model_solution_full_path],
    )

    context.path.clean_logs()
    os.makedirs(context.path.logs)
    os.makedirs(context.path.logs_generation, exist_ok=True)

    formatter.print("Generator   compile ")
    generation_step.prepare_sandbox()
    generation_compilation = generation_step.compile()
    formatter.print_compile_string_with_exit(generation_compilation)

    formatter.print("Validator   compile ")
    validation_step.prepare_sandbox()
    validation_compilation = validation_step.compile()
    formatter.print_compile_string_with_exit(validation_compilation)

    formatter.print("Solution    compile ")
    solution_step.prepare_sandbox()
    formatter.print_compile_string_with_exit(solution_step.compile_solution())

    if solution_step.has_interactor():
        formatter.print("Interactor  compile ")
        formatter.print_compile_string_with_exit(solution_step.compile_interactor())

    if solution_step.has_manager():
        formatter.print("Manager     compile ")
        formatter.print_compile_string_with_exit(solution_step.compile_manager())

    if run_checker:
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

    with open(context.path.tmt_recipe) as f:
        recipe = parse_recipe_data(f.readlines())

    # TODO: in case of update testcases, these should be mkdir instead of mkdir_clean.
    context.path.clean_testcases()
    os.makedirs(context.path.testcases, exist_ok=True)
    pathlib.Path(context.path.testcases_summary).touch()

    codename_length = max(map(len, recipe.get_all_test_names())) + 2
    testcase_hashes = {}

    with open(context.path.testcases_summary, "wt") as testcases_summary:
        for testset in recipe.testsets.values():
            for test in testset.tests:
                code_name = test.test_name
                if code_name is None:
                    raise ValueError(f"command_gen: testcase without name encountered: {test}")

                formatter.print(" " * 4)
                formatter.print_fixed_width(code_name, width=codename_length)

                # Run generator
                formatter.print("gen ")
                result = generation_step.run_generator(
                    test.execute.commands, code_name, list(testset.extra_file)
                )
                formatter.print_exec_result(result.input_generation)

                # Run validator: skip if input_generation did not succeed
                formatter.print("val ")
                if result.input_generation is not ExecutionOutcome.SUCCESS:
                    result.input_validation = ExecutionOutcome.SKIPPED
                else:
                    validation_commands = []
                    for exe in test.validation:
                        if len(exe.commands) != 1:
                            raise ValueError("Validation with pipe is not supported.")
                        validation_commands.append(exe.commands[0])
                    validation_step.run_validator(
                        result, validation_commands, code_name, list(testset.extra_file)
                    )
                formatter.print_exec_result(result.input_validation)

                # Run solution:
                # skip (and fail) if input validation did not succeed
                # skip if generator already produced output
                formatter.print("ans ")
                if result.input_validation is not ExecutionOutcome.SUCCESS:
                    result.output_generation = ExecutionOutcome.SKIPPED
                elif result.output_generation is ExecutionOutcome.SKIPPED_SUCCESS:
                    pass
                else:
                    solution_result = solution_step.run_solution(code_name)
                    result.output_generation = eval_outcome_to_run_outcome(
                        solution_result
                    )
                    result.reason = solution_result.checker_reason
                formatter.print_exec_result(result.output_generation)

                # Run checker
                # If both input is validated and output is available, run checker if the testcase type should apply check
                if run_checker:
                    formatter.print("val ")
                    if result.output_generation not in [
                        ExecutionOutcome.SUCCESS,
                        ExecutionOutcome.SKIPPED_SUCCESS,
                    ] or result.input_validation not in [
                        ExecutionOutcome.SUCCESS,
                        ExecutionOutcome.SKIPPED_SUCCESS,
                    ]:
                        result.output_validation = ExecutionOutcome.SKIPPED
                    elif (
                        result.is_output_forced
                        and not context.config.check_forced_output
                    ) or (
                        not result.is_output_forced
                        and not context.config.check_generated_output
                    ):
                        result.output_validation = ExecutionOutcome.SKIPPED_SUCCESS
                    else:
                        testcase_input = os.path.join(
                            context.path.testcases,
                            context.construct_input_filename(code_name),
                        )
                        testcase_answer = os.path.join(
                            context.path.testcases,
                            context.construct_output_filename(code_name),
                        )

                        copied_testcase_output = os.path.join(
                            context.path.sandbox_checker,
                            os.path.basename(testcase_answer),
                        )
                        shutil.copy(testcase_answer, copied_testcase_output)

                        checker_result = checker_step.run_checker(
                            context.config.checker_arguments,
                            EvaluationResult(output_file=copied_testcase_output),
                            testcase_input,
                            testcase_answer,
                        )
                        result.output_validation = eval_outcome_to_grade_outcome(
                            checker_result
                        )
                        result.reason = checker_result.checker_reason
                    formatter.print_exec_result(result.output_validation)
                else:
                    result.output_validation = ExecutionOutcome.SKIPPED_SUCCESS

                if show_reason:
                    formatter.print_reason(result.reason)

                formatter.println()

                with open(
                    os.path.join(context.path.logs_generation, f"{code_name}.gen.log"),
                    "w+",
                ) as f:
                    f.write(result.reason)
                # TODO: this should print more meaningful contents, right now it is only the testcases
                if result:
                    testcases_summary.write(f"{code_name}\n")
                    for testcase_file_exts in [
                        context.config.input_extension,
                        context.config.output_extension,
                    ] + list(testset.extra_file):
                        base_filename = context.construct_test_filename(
                            code_name, testcase_file_exts
                        )
                        file = os.path.join(context.path.testcases, base_filename)
                        with open(file, "rb") as f:
                            testcase_hashes[base_filename] = hashlib.sha256(
                                f.read()
                            ).hexdigest()

        if verify_hash:
            formatter.println()
            with open(context.path.testcases_hashes, "r") as f:
                official_testcase_hashes: dict = json.load(f)
            if testcase_hashes == official_testcase_hashes:
                formatter.println(
                    formatter.ANSI_GREEN, "Hash matches!", formatter.ANSI_RESET
                )
            else:
                tab = " " * 4
                # Hash mismatch
                formatter.println(
                    formatter.ANSI_RED, "Hash mismatches:", formatter.ANSI_RESET
                )
                common_files = official_testcase_hashes.keys() & testcase_hashes.keys()
                for filename in sorted(common_files):
                    if official_testcase_hashes[filename] != testcase_hashes[filename]:
                        formatter.println(
                            tab,
                            f"{filename}: {official_testcase_hashes[filename]} (found {testcase_hashes[filename]})",
                        )
                # Missing files
                missing_files = official_testcase_hashes.keys() - testcase_hashes.keys()
                if len(missing_files) > 0:
                    formatter.println(
                        formatter.ANSI_RED, "Missing files:", formatter.ANSI_RESET
                    )
                    for file in sorted(missing_files):
                        formatter.println(tab, file)
                # Extra files
                extra_files = testcase_hashes.keys() - official_testcase_hashes.keys()
                if len(extra_files) > 0:
                    formatter.println(
                        formatter.ANSI_RED, "Extra files:", formatter.ANSI_RESET
                    )
                    for file in sorted(extra_files):
                        formatter.println(tab, file)

        else:
            with open(context.path.testcases_hashes, "w") as f:
                json.dump(testcase_hashes, f, sort_keys=True, indent=4)
