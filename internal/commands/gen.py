import pathlib
import os
import hashlib
import json
import filecmp

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
from internal.steps.utils import CompilationJob, CompilationSlot
from internal.steps.validation import ValidationStep
from internal.steps.solution import SolutionStep, make_solution_step_type
from internal.steps.checker.icpc import ICPCCheckerStep


def gen_single(
    *,
    formatter: Formatter,
    generation_step: GenerationStep,
    validation_step: ValidationStep,
    solution_step: SolutionStep,
    checker_step: ICPCCheckerStep | None,
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
        solution_result = solution_step.run_solution(codename)
        result.output_generation = eval_outcome_to_run_outcome(solution_result)
        result.reason = solution_result.reason
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

        self.compilation_result: dict[CompilationSlot, CompilationResult] = {}

        self.hash_mismatch: bool = False

    def __bool__(self):
        def is_compilation_error(cresult: CompilationResult | None):
            return cresult is not None and not cresult

        if any(map(is_compilation_error, self.compilation_result.values())):
            return False

        if self.hash_mismatch:
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
        summary.hash_mismatch = True
        return summary

    context.path.clean_logs()
    os.makedirs(context.path.logs)
    os.makedirs(context.path.logs_generation, exist_ok=True)

    # Init all steps
    generation_step = GenerationStep(context=context, sandbox=sandbox)
    validation_step = ValidationStep(context=context, sandbox=sandbox)

    assert context.config.answer_generation.type is AnswerGenerationType.SOLUTION
    solution_step_type = make_solution_step_type(
        problem_type=context.config.problem_type,
        judge_convention=context.config.judge_convention,
    )
    solution_step = solution_step_type(
        context=context,
        sandbox=sandbox,
        is_generation=True,
        submission_files=[context.config.answer_generation.filename],
    )

    checker_step: ICPCCheckerStep | None = None
    if context.config.checker is not None:
        checker_step = ICPCCheckerStep(context=context, sandbox=sandbox)
        checker_step.check_unused_checker(formatter)

    # Compile steps
    def compilation_jobs():
        yield CompilationJob(CompilationSlot.GENERATOR, generation_step.compile, "")
        yield CompilationJob(CompilationSlot.VALIDATOR, validation_step.compile, "")
        yield from solution_step.compilation_jobs()
        if checker_step is not None:
            yield CompilationJob(
                CompilationSlot.CHECKER, checker_step.compile, checker_step.checker_name
            )

    for job in compilation_jobs():
        formatter.print(f"{job.slot.display_name.ljust(10)}  compile ")
        result = job.compile_fn()
        summary.compilation_result[job.slot] = result
        formatter.print_compile_result(result, name=job.display_file)
        if not result:
            return summary

    # TODO: in case of update testcases, these should be mkdir
    # instead of mkdir_clean.
    context.path.clean_testcases()
    os.makedirs(context.path.testcases, exist_ok=True)
    pathlib.Path(context.path.testcase_summary).touch()

    codename_display_width: int = max(map(len, context.recipe.get_all_test_names())) + 2

    # Execute steps
    with open(context.path.testcase_summary, "wt") as testcase_summary_file:
        summary.testcase_summary_path = context.path.testcase_summary

        for testset in context.recipe.testsets.values():
            for test in testset.tests:
                result = gen_single(
                    formatter=formatter,
                    codename_display_width=codename_display_width,
                    generation_step=generation_step,
                    validation_step=validation_step,
                    solution_step=solution_step,
                    checker_step=checker_step,
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
            summary.hash_mismatch = official_testcase_hashes != summary.testcase_hashes
        else:
            # Dump hashes first
            with open(context.path.testcases_hashes, "w") as f:
                json.dump(summary.testcase_hashes, f, sort_keys=True, indent=4)

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
            if not len(dupe_hashes):
                return summary

            # Warn for same input hashes
            formatter.println(
                formatter.ANSI_YELLOW,
                "Warning: same hash value for input files detected:",
            )
            for hash, filelist in dupe_hashes.items():
                formatter.println(f"    {hash}: {', '.join(filelist)}")
            formatter.println(
                "Please make sure the possibly duplicated test is intended.",
                formatter.ANSI_RESET,
            )

            # Addtional check for actual file content
            for hash, filelist in dupe_hashes.items():
                for i in range(len(filelist) - 1):
                    if filecmp.cmp(
                        os.path.join(context.path.testcases, filelist[i]),
                        os.path.join(context.path.testcases, filelist[i + 1]),
                        shallow=False,
                    ):
                        continue
                    # SHA-256 collision?
                    formatter.println(
                        formatter.ANSI_RED_BG,
                        f"You found a SHA-256 hash collision: {filelist[i]} and {filelist[i + 1]}. "
                        "You should check whether your disk and RAM are still working properly.",
                        formatter.ANSI_RESET,
                    )

    return summary
