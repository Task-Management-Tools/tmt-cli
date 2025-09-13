import os
import shutil
import signal
import subprocess
from pathlib import Path

from internal.context import TMTContext
from internal.runner import Process, wait_procs
from internal.compilation_makefile import compile_with_make, clean_with_make
from internal.compilation_cpp_single import compile_cpp_single
from internal.outcome import (
    EvaluationOutcome,
    EvaluationResult,
    CompilationOutcome,
    CompilationResult,
)

from internal.steps.solution import SolutionStep


class InteractorStep:
    """Implements ICPC interactor compilation and execution."""

    def __init__(self, *, context: TMTContext):
        self.context = context

    def compile(self) -> CompilationResult:
        if self.context.path.has_checker_directory():
            comp_result = compile_with_make(
                makefile_path=self.context.path.makefile_checker,
                directory=self.context.path.checker,
                context=self.context,
                executable_stack_size_mib=self.context.config.trusted_step_memory_limit_mib,
            )

            shutil.copy(
                os.path.join(self.context.path.checker, "checker"),
                self.context.path.sandbox_checker,
            )

            return comp_result
        return CompilationResult(
            CompilationOutcome.FAILED, "`checker' directory not found."
        )

    def run_interactor(
        self, input_file: str, answer_file: str, feedback_dir: str
    ) -> EvaluationResult:
        raise NotImplementedError("Interactor execution is handled in SolutionStep.")
