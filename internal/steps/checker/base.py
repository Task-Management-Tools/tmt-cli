from abc import ABC, abstractmethod

from internal.context import CheckerType, TMTContext, SandboxDirectory
from internal.exceptions import TMTInvalidConfigError, TMTMissingFileError
from internal.formatting.base import Formatter
from internal.outcomes import EvaluationResult, CompilationResult


class CheckerStep(ABC):
    def __init__(self, context: TMTContext, sandbox: SandboxDirectory | None):
        self.context = context
        self.sandbox = sandbox
        if self.sandbox:
            self.sandbox.checker.create()
            self.sandbox.checker_compilation.create()

        if context.config.checker is None:
            self.use_default_checker = True
            self.checker_name = "(default)"
            self.arguments = []
            return

        self.arguments = context.config.checker.arguments or []
        if context.config.checker.type == CheckerType.DEFAULT:
            self.use_default_checker = True
            self.checker_name = "(default)"
        else:
            self.use_default_checker = False

            if context.config.checker is None:
                raise TMTInvalidConfigError("Config section `checker` is not present.")
            if context.config.checker.filename is None:
                raise TMTInvalidConfigError(
                    "Config option `checker.filename` is not present."
                )
            if not context.path.has_checker_directory():
                raise TMTMissingFileError(filetype="Directory", filename="checker")

            self.checker_name = context.config.checker.filename

    def check_unused_checker(self, formatter: Formatter) -> bool:
        if self.context.path.has_checker_directory() and self.use_default_checker:
            formatter.println(
                formatter.ANSI_YELLOW,
                "Warning: Directory 'checker' exists but it is not used by this problem. Check problem.yaml or remove the directory.",
                formatter.ANSI_RESET,
            )
            return True
        return False

    @abstractmethod
    def compile(self) -> CompilationResult:
        raise NotImplementedError

    @abstractmethod
    def run_checker(
        self,
        evaluation_record: EvaluationResult,
        input_file: str,
        answer_file: str,
    ) -> EvaluationResult:
        raise NotImplementedError
