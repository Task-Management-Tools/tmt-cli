import pathlib

from internal.commands.compile import (
    CommandCompileAllSummary,
    CommandCompileSingleSummary,
    command_compile,
)
from internal.commands.clean import command_clean
from internal.context import TMTContext
from internal.formatting.empty import EmptyFormatter
from internal.outcomes import CompilationOutcome
from internal.steps.utils import CompilationSlot


def _make_context(problem_relpath: str) -> TMTContext:
    script_dir = pathlib.Path(__file__).parent.parent.resolve()
    problem_dir = pathlib.Path(__file__).parent / "problems" / problem_relpath
    return TMTContext(str(problem_dir), str(script_dir))


def test_compile_single_uses_source_directory():
    context = _make_context("batch/icpc-generator")
    source_file = pathlib.Path(context.path.generator) / "print.cpp"

    try:
        summary = command_compile(
            formatter=EmptyFormatter(),
            context=context,
            source=str(source_file),
        )

        assert isinstance(summary, CommandCompileSingleSummary)
        assert summary.compilation_result is not None
        assert summary.compilation_result.verdict is CompilationOutcome.SUCCESS
        assert summary.source == "print.cpp"
        assert summary.compilation_result.produced_file is not None
        assert pathlib.Path(summary.compilation_result.produced_file).exists()
        assert summary.compilation_result.produced_file.startswith(
            str(source_file.parent)
        )
    finally:
        command_clean(formatter=EmptyFormatter(), context=context, skip_confirm=True)


def test_compile_without_source_uses_compile_all():
    context = _make_context("batch/cms-verdict")

    try:
        result = command_compile(
            formatter=EmptyFormatter(),
            context=context,
            source=None,
        )

        assert isinstance(result, CommandCompileAllSummary)
        assert CompilationSlot.GENERATOR in result.compilation_result
        assert CompilationSlot.VALIDATOR in result.compilation_result
        assert CompilationSlot.SOLUTION in result.compilation_result
    finally:
        command_clean(formatter=EmptyFormatter(), context=context, skip_confirm=True)


def test_compile_solution_with_grader_headers():
    context = _make_context("communication/2-proc-grader-fifo")
    source_file = pathlib.Path(context.path.solutions) / "model-solution.cpp"

    try:
        summary = command_compile(
            formatter=EmptyFormatter(),
            context=context,
            source=str(source_file),
        )

        assert isinstance(summary, CommandCompileSingleSummary)
        assert summary.compilation_result is not None
        assert summary.compilation_result.verdict is CompilationOutcome.SUCCESS
        assert summary.source == "model-solution.cpp"
        assert summary.compilation_result.produced_file is not None
        assert pathlib.Path(summary.compilation_result.produced_file).exists()
    finally:
        command_clean(formatter=EmptyFormatter(), context=context, skip_confirm=True)
