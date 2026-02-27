import pathlib
import os
import hashlib
import json

from internal.formatting import Formatter
from internal.context import (
    AnswerGenerationType,
    TMTContext,
    SandboxDirectory,
)
from internal.exceptions import TMTInvalidConfigError
from internal.outcomes import (
    CompilationResult,
    ExecutionOutcome,
    GenerationResult,
    eval_outcome_to_run_outcome,
)

from internal.steps.generation import GenerationStep
from internal.steps.validation import ValidationStep
from internal.steps.solution import SolutionStep, make_solution_step
from internal.steps.checker.icpc import ICPCCheckerStep
from internal.steps.interactor import ICPCInteractorStep


def gen_single(
    *,
    formatter: Formatter,
    generation_step: GenerationStep,
    validation_step: ValidationStep,
    solution_step: SolutionStep,
    checker_step: ICPCCheckerStep | None,
    interactor_step: ICPCInteractorStep | None,
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
    solution_result = None

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
        checker_step.run_checker_during_gen(result, solution_result, codename)
        formatter.print_exec_result(result.output_validation)
    else:
        result.output_validation = ExecutionOutcome.SKIPPED_SUCCESS

    if show_reason:
        formatter.print_checker_reason(result.reason)

    formatter.println()

    return result


class CommandGenSummary:
    def __init__(self):
        self.testcase_results: dict[str, GenerationResult | None] = {}
        self.testcase_summary_path: str | None = None
        self.testcase_hashes: dict[str, str] = {}

        self.generation_compilation: CompilationResult | None = None
        self.validation_compilation: CompilationResult | None = None
        self.solution_compilation: CompilationResult | None = None
        self.checker_compilation: CompilationResult | None = None
        self.interactor_compilation: CompilationResult | None = None

    def __bool__(self):
        all_compilations = [
            self.generation_compilation,
            self.validation_compilation,
            self.solution_compilation,
            self.checker_compilation,
            self.interactor_compilation,
        ]

        def is_compilation_error(cresult: CompilationResult | None):
            return cresult is not None and not cresult

        if any(map(is_compilation_error, all_compilations)):
            return False

        return all(self.testcase_results.values())


def command_gen(
    *, formatter: Formatter, context: TMTContext, verify_hash: bool, show_reason: bool
) -> CommandGenSummary:
    """Generate test cases in the given directory."""

    summary = CommandGenSummary()

    # TODO when multiprocess generation is used, reflect this sandbox usage
    sandbox = SandboxDirectory(context.path.default_sandbox)
    sandbox.create()

    if verify_hash and not (
        os.path.exists(context.path.testcases_hashes)
        and os.path.isfile(context.path.testcases_hashes)
    ):
        formatter.println(
            formatter.ANSI_RED,
            "Testcase hashes does not exist. There is nothing to verify.",
            formatter.ANSI_RESET,
        )
        return False

    context.path.clean_logs()
    os.makedirs(context.path.logs)
    os.makedirs(context.path.logs_generation, exist_ok=True)

    # Init all steps
    generation_step = GenerationStep(context=context, sandbox=sandbox)
    validation_step = ValidationStep(context=context, sandbox=sandbox)

    assert context.config.answer_generation.type is AnswerGenerationType.SOLUTION
    solution_step: SolutionStep = make_solution_step(
        solution_type=context.config.solution.type,
        context=context,
        sandbox=sandbox,
        is_generation=True,
        submission_files=[context.config.answer_generation.filename],
    )

    checker_step: ICPCCheckerStep | None = None
    if context.config.checker is not None:
        checker_step = ICPCCheckerStep(context=context, sandbox=sandbox)
        checker_step.check_unused_checker(formatter)

    interactor_step: ICPCInteractorStep | None = None
    if context.config.interactor is not None:
        interactor_step = ICPCInteractorStep(context=context, sandbox=sandbox)

    # Compile steps
    formatter.print("Generator   compile ")
    summary.generation_compilation = generation_step.compile()
    formatter.print_compile_result(summary.generation_compilation)
    if not summary.generation_compilation:
        return summary

    formatter.print("Validator   compile ")
    summary.validation_compilation = validation_step.compile()
    formatter.print_compile_result(summary.validation_compilation)
    if not summary.validation_compilation:
        return summary

    formatter.print("Solution    compile ")
    summary.solution_compilation = solution_step.compile_solution()
    formatter.print_compile_result(summary.solution_compilation)
    if not summary.solution_compilation:
        return summary

    if interactor_step is not None:
        formatter.print("Interactor  compile ")
        summary.interactor_compilation = interactor_step.compile()
        formatter.print_compile_result(
            summary.interactor_compilation, name=interactor_step.interactor_name
        )
        if not summary.interactor_compilation:
            return summary

    if checker_step is not None:
        formatter.print("Checker     compile ")
        summary.checker_compilation = checker_step.compile()
        formatter.print_compile_result(
            summary.checker_compilation, name=checker_step.checker_name
        )
        if not summary.checker_compilation:
            return summary

    # TODO: in case of update testcases, these should be mkdir
    # instead of mkdir_clean.
    context.path.clean_testcases()
    os.makedirs(context.path.testcases, exist_ok=True)
    pathlib.Path(context.path.testcase_summary).touch()

    codename_display_width: int = max(map(len, context.recipe.get_all_test_names())) + 2

    # Execute steps
    with open(context.path.testcase_summary, "wt") as testcase_summary_file:
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
                assert codename is not None

                with open(
                    os.path.join(context.path.logs_generation, f"{codename}.gen.log"),
                    "w+",
                ) as f:
                    f.write(result.reason)

                summary.testcase_results[codename] = result
                if not result:
                    continue

                # TODO: this should print more meaningful contents, right now it is only the testcases
                testcase_summary_file.write(f"{codename}\n")
                for testcase_file_exts in [
                    context.config.input_extension,
                    context.config.output_extension,
                ] + list(testset.extra_file):
                    base_filename = context.construct_test_filename(
                        codename, testcase_file_exts
                    )
                    file = os.path.join(context.path.testcases, base_filename)
                    with open(file, "rb") as f:
                        summary.testcase_hashes[base_filename] = hashlib.sha256(
                            f.read()
                        ).hexdigest()

        if verify_hash:
            formatter.println()
            with open(context.path.testcases_hashes, "r") as f:
                official_testcase_hashes: dict[str, str] = json.load(f)
            formatter.print_hash_diff(official_testcase_hashes, summary.testcase_hashes)
        else:
            # Duplicated test detection
            input_hashes: dict[str, list[str]] = {}
            for file, hash in summary.testcase_hashes.items():
                if file.endswith(context.config.input_extension):
                    if hash not in input_hashes:
                        input_hashes[hash] = []
                    input_hashes[hash].append(file)
            dupe_hashes = {
                hash: filelist
                for hash, filelist in input_hashes.items()
                if len(filelist) > 1
            }
            if len(dupe_hashes):
                formatter.println(
                    formatter.ANSI_YELLOW,
                    "Warning: same hash value for input files detected:",
                )
                for hash, filelist in dupe_hashes.items():
                    print(f"\t{hash}: {', '.join(filelist)}")
                formatter.println(
                    "Please make sure the possibly duplicated test is intended.",
                    formatter.ANSI_RESET,
                )
                for hash, filelist in dupe_hashes.items():
                    last_file = open(
                        file=os.path.join(context.path.testcases, filelist[0])
                    )
                    last_file_content = last_file.read()
                    last_file.close()
                    for i in range(1, len(filelist)):
                        current_file = open(
                            file=os.path.join(context.path.testcases, filelist[i])
                        )
                        current_file_content = current_file.read()
                        current_file.close()
                        if (
                            last_file_content != current_file_content
                        ):  # SHA-256 collision?
                            formatter.println(
                                formatter.ANSI_RED_BG,
                                f"You found a SHA-256 hash collision: {filelist[i - 1]} and {filelist[i]}. You should check whether your disk and RAM are still working properly.",
                                formatter.ANSI_RESET,
                            )
                        last_file_content = current_file_content

            # Dump duplicated test
            with open(context.path.testcases_hashes, "w") as f:
                json.dump(summary.testcase_hashes, f, sort_keys=True, indent=4)

    summary.testcase_summary_path = context.path.testcase_summary
    return summary
