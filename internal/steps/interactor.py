import os
import shutil

from internal.context import TMTContext
from internal.compilation_makefile import compile_with_make, clean_with_make
from internal.outcome import (
    EvaluationResult,
    CompilationOutcome,
    CompilationResult,
)


class InteractorStep:
    """Implements ICPC interactor compilation and execution."""

    def __init__(self, *, context: TMTContext):
        self.context = context

    def prepare_sandbox(self) -> None:
        os.makedirs(self.context.path.sandbox_interactor, exist_ok=True)

    def clean_up(self) -> None:
        clean_with_make(
            makefile_path=self.context.path.makefile_checker,
            directory=self.context.path.interactor,
            context=self.context,
            env={"SRCS": self.context.config.interactor.filename},
        )

    def compile_interactor(self) -> CompilationResult:
        if self.context.path.has_interactor_directory():
            comp_result = compile_with_make(
                makefile_path=self.context.path.makefile_checker,
                directory=self.context.path.interactor,
                context=self.context,
                executable_stack_size_mib=self.context.config.trusted_step_memory_limit_mib,
                env={"SRCS": self.context.config.interactor.filename},
            )

            shutil.copy(
                os.path.join(self.context.path.interactor, "checker"),
                self.context.path.sandbox_interactor,
            )

            return comp_result
        return CompilationResult(
            CompilationOutcome.FAILED, "`interactor' directory not found."
        )

    def run_interactor(
        self, input_file: str, answer_file: str, feedback_dir: str
    ) -> EvaluationResult:
        raise NotImplementedError("Interactor execution is handled in SolutionStep.")
