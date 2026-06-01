import os
import pathlib
from dataclasses import dataclass

from internal.formatting import Formatter
from internal.context import (
    AnswerGenerationType,
    TMTContext,
    SandboxDirectory,
)
from internal.compilation import recognize_language
from internal.outcomes import (
    CompilationOutcome,
    CompilationResult,
)
from internal.compilation.makefile import make_compile_target

from internal.steps.generation import GenerationStep
from internal.steps.utils import CompilationJob, CompilationSlot
from internal.steps.validation import ValidationStep
from internal.steps.solution import get_solution_step_type
from internal.steps.checker import CheckerStep, get_checker_step_type


@dataclass
class CommandCompileAllSummary:
    compilation_result: dict[CompilationSlot, CompilationResult]

    def __bool__(self) -> bool:
        def is_compilation_error(cresult: CompilationResult | None):
            return cresult is not None and not cresult

        return not any(map(is_compilation_error, self.compilation_result.values()))


@dataclass
class CommandCompileSingleSummary:
    compilation_result: CompilationResult | None = None
    source: str | None = None

    def __bool__(self) -> bool:
        return bool(self.compilation_result)


def compile_single(
    *,
    formatter: Formatter,
    context: TMTContext,
    source: str,
) -> CommandCompileSingleSummary:

    summary = CommandCompileSingleSummary()
    context.set_log_directory(context.path.logs)

    source_path = pathlib.Path(source).expanduser().resolve()
    source_name = source_path.name
    source_directory = str(source_path.parent)

    def compile_fail(reason: str) -> CommandCompileSingleSummary:
        result = CompilationResult(
            verdict=CompilationOutcome.FAILED,
            exit_status=-1,
            standard_error=reason,
        )
        summary.compilation_result = result
        summary.source = source_name
        formatter.print_compile_result(result, name=source_name)
        result.dump_to_logs(context.log_directory, source_path.stem)
        return summary

    if not source_path.exists() or not source_path.is_file():
        return compile_fail(f"Source file {source_name} is not a file.")

    if recognize_language([str(source_path)], context) is None:
        return compile_fail(
            f"Source file {source_name} is not recognized by any language."
        )

    formatter.print(f"{source_name.ljust(10)}  compile ")
    result = make_compile_target(
        context=context,
        directory=source_directory,
        sources=[source_name],
        target=source_path.stem,
        executable_stack_size_mib=context.config.trusted_step_memory_limit_mib,
    )
    summary.compilation_result = result
    summary.source = source_name
    formatter.print_compile_result(result, name=source_name)

    if (
        result.verdict is CompilationOutcome.SUCCESS
        and result.produced_file is None
    ):
        raise FileNotFoundError("Compilation did not produce source executable")

    result.dump_to_logs(context.log_directory, source_path.stem)
    return summary


def compile_all(
    *,
    formatter: Formatter,
    context: TMTContext,
) -> CommandCompileAllSummary:
    """Generate test cases in the given directory."""
    context.set_log_directory(context.path.logs_generation)
    summary = CommandCompileAllSummary(compilation_result={})

    # TODO when multiprocess generation is used, reflect this sandbox usage
    sandbox = SandboxDirectory(context.path.default_sandbox)
    sandbox.create()

    context.path.clean_logs()
    os.makedirs(context.path.logs)
    os.makedirs(context.path.logs_generation, exist_ok=True)

    # Init all steps
    generation_step = GenerationStep(context=context, sandbox=sandbox)
    validation_step = ValidationStep(context=context, sandbox=sandbox)

    assert context.config.answer_generation.type is AnswerGenerationType.SOLUTION
    solution_step_type = get_solution_step_type(
        problem_type=context.config.problem_type,
        judge_convention=context.config.judge_convention,
    )
    solution_step = solution_step_type(
        context=context,
        sandbox=sandbox,
        is_generation=True,
        submission_files=[
            os.path.join(
                context.path.solutions, context.config.answer_generation.filename
            )
        ],
    )

    checker_step_type = get_checker_step_type(
        problem_type=context.config.problem_type,
        judge_convention=context.config.judge_convention,
    )
    checker_step: CheckerStep | None = None
    if checker_step_type is not None:
        checker_step = checker_step_type(
            context=context, sandbox=sandbox, is_generation=True
        )
        checker_step.check_unused_checker(formatter)

        # During generation, if the default checker is used then it is never meaningful to run it because it always succeed
        if checker_step.use_default_checker:
            checker_step = None

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
        formatter.print(f"{job.slot.value.ljust(10)}  compile ")
        result = job.compile_fn()
        summary.compilation_result[job.slot] = result
        formatter.print_compile_result(result, name=job.display_file)
        if not result:
            return summary

    return summary


def command_compile(
    *,
    formatter: Formatter,
    context: TMTContext,
    source: str | None,
) -> CommandCompileAllSummary | CommandCompileSingleSummary:
    if source is None:
        return compile_all(formatter=formatter, context=context)

    return compile_single(formatter=formatter, context=context, source=source)
