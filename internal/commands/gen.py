import pathlib
import os
import hashlib
import json

from internal.formatting import Formatter
from internal.context import CheckerType, AnswerGenerationType, TMTContext
from internal.errors import TMTInvalidConfigError
from internal.outcome import (
    ExecutionOutcome,
    eval_outcome_to_run_outcome,
)

from internal.steps.generation import GenerationStep
from internal.steps.validation import ValidationStep
from internal.steps.solution import SolutionStep, make_solution_step
from internal.steps.checker.icpc import ICPCCheckerStep
from internal.steps.interactor import InteractorStep


def gen_single(
    *,
    formatter: Formatter,
    generation_step: GenerationStep,
    validation_step: ValidationStep,
    solution_step: SolutionStep,
    checker_step: ICPCCheckerStep | None,
    interactor_step: InteractorStep | None,
    codename_display_width: int,
    show_reason: bool,
    testset,
    test,
):
    codename = test.test_name
    assert codename is not None, "codename should not be None here"

    formatter.print(" " * 4)
    formatter.print_fixed_width(codename, width=codename_display_width)

    # Run generator
    formatter.print("gen ")
    result = generation_step.run_generator(
        test.execute.commands, codename, list(testset.extra_file)
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
                raise TMTInvalidConfigError("Validation with pipe is not supported.")
            validation_commands.append(exe.commands[0])
        validation_step.run_validator(
            result, validation_commands, codename, list(testset.extra_file)
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
        if interactor_step is None:
            solution_result = solution_step.run_solution(codename)
        else:
            solution_result = interactor_step.run_solution(
                solution_step,
                codename,
            )
        result.output_generation = eval_outcome_to_run_outcome(solution_result)
        result.reason = solution_result.checker_reason
    formatter.print_exec_result(result.output_generation)

    # Run checker
    # If both input is validated and output is available, run checker if the testcase type should apply check
    if checker_step is not None:
        formatter.print("val ")
        checker_step.run_checker_during_gen(result, codename)
        formatter.print_exec_result(result.output_validation)
    else:
        result.output_validation = ExecutionOutcome.SKIPPED_SUCCESS

    if show_reason:
        formatter.print_reason(result.reason)

    formatter.println()

    return result


def command_gen(
    *, formatter: Formatter, context: TMTContext, verify_hash: bool, show_reason: bool
):
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

    context.path.clean_logs()
    os.makedirs(context.path.logs)
    os.makedirs(context.path.logs_generation, exist_ok=True)

    # Compile generators, validators and solutions
    generation_step = GenerationStep(context)
    validation_step = ValidationStep(context)

    assert context.config.answer_generation.type is AnswerGenerationType.SOLUTION
    solution_step: SolutionStep = make_solution_step(
        solution_type=context.config.solution.type,
        context=context,
        is_generation=True,
        submission_files=[context.config.answer_generation.filename],
    )

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

    checker_step: ICPCCheckerStep | None = None
    if context.config.checker is not None:
        formatter.print("Checker     compile ")
        checker_step = ICPCCheckerStep(context)
        checker_step.prepare_sandbox()
        formatter.print_compile_string_with_exit(checker_step.compile(), endl=False)

        formatter.print(
            " " * 2,
            "(default)"
            if context.config.checker.type is CheckerType.DEFAULT
            else context.config.checker.filename,
            endl=True,
        )

    interactor_step: InteractorStep | None = None
    if context.config.interactor is not None:
        formatter.print("Interactor  compile ")
        interactor_step = InteractorStep(context=context)
        interactor_step.prepare_sandbox()
        interactor_compilation = interactor_step.compile()
        formatter.print_compile_string_with_exit(interactor_compilation)

    # TODO: in case of update testcases, these should be mkdir
    # instead of mkdir_clean.
    context.path.clean_testcases()
    os.makedirs(context.path.testcases, exist_ok=True)
    pathlib.Path(context.path.testcases_summary).touch()

    codename_display_width: int = max(map(len, context.recipe.get_all_test_names())) + 2
    testcase_hashes: dict[str, str] = {}

    with open(context.path.testcases_summary, "wt") as testcases_summary:
        for testset in context.recipe.testsets.values():
            for test in testset.tests:
                result = gen_single(
                    formatter=formatter,
                    codename_display_width=codename_display_width,
                    generation_step=generation_step,
                    validation_step=validation_step,
                    solution_step=solution_step,
                    checker_step=checker_step,
                    interactor_step=interactor_step,
                    show_reason=show_reason,
                    testset=testset,
                    test=test,
                )
                codename = test.test_name
                with open(
                    os.path.join(context.path.logs_generation, f"{codename}.gen.log"),
                    "w+",
                ) as f:
                    f.write(result.reason)
                # TODO: this should print more meaningful contents, right now it is only the testcases
                if result:
                    testcases_summary.write(f"{codename}\n")
                    for testcase_file_exts in [
                        context.config.input_extension,
                        context.config.output_extension,
                    ] + list(testset.extra_file):
                        base_filename = context.construct_test_filename(
                            codename, testcase_file_exts
                        )
                        file = os.path.join(context.path.testcases, base_filename)
                        with open(file, "rb") as f:
                            testcase_hashes[base_filename] = hashlib.sha256(
                                f.read()
                            ).hexdigest()

        if verify_hash:
            formatter.println()
            with open(context.path.testcases_hashes, "r") as f:
                official_testcase_hashes: dict[str, str] = json.load(f)
            formatter.print_hash_diff(official_testcase_hashes, testcase_hashes)
        else:
            with open(context.path.testcases_hashes, "w") as f:
                json.dump(testcase_hashes, f, sort_keys=True, indent=4)
