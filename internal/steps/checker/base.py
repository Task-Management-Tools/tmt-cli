from abc import ABC, abstractmethod

from internal.context import CheckerType, TMTContext, SandboxDirectory
from internal.exceptions import TMTMissingFileError
from internal.formatting.base import Formatter
from internal.outcomes import EvaluationResult, CompilationResult


class CheckerStep(ABC):
    """
    Base class for running checker (checking the participant's output is correct or not).

    CheckerStep may write to:
     - sandbox directories `checker`, `checker_compilation`, and
     - log directory
    but must not write to others.
    It can read from other sandbox dirs (for example, most checkers assume the output is generated inside the solution sandbox)


    Subclasses must implement :meth:`clean_up`, :meth:`compile` and :meth:`run_checker` to perform the actual checker logic.

    Args:
        context: The current TMT context.
        sandbox: The sandbox directory to use for checker execution, or ``None`` if no sandbox is availble (for example, during clean up).
        is_generation: Whether this step is running during generation rather than evaluation.

    Raises:
        TMTMissingFileError: if the checker config indicates a custom checker but the checker directory does not exist.
    """

    def __init__(
        self, context: TMTContext, sandbox: SandboxDirectory | None, is_generation: bool
    ):
        self.context = context
        self.sandbox = sandbox
        if self.sandbox:
            self.sandbox.checker.create()
            self.sandbox.checker_compilation.create()

        self.is_generation = is_generation

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
            assert context.config.checker.filename is not None

            if not context.path.has_checker_directory():
                raise TMTMissingFileError(filetype="Directory", filename="checker")

            self.checker_name = context.config.checker.filename

    def check_unused_checker(self, formatter: Formatter) -> bool:
        """
        Produce a warning if the checker directory is present but default checker is used indicated by the configuration.

        Args:
            formatter: The current formatter in use.
        """
        if self.context.path.has_checker_directory() and self.use_default_checker:
            formatter.println(
                formatter.ANSI_YELLOW,
                "Warning: Directory 'checker' exists but it is not used by this problem. Check problem.yaml or remove the directory.",
                formatter.ANSI_RESET,
            )
            return True
        return False

    @abstractmethod
    def clean_up(self):
        """
        Clear relevant files produced by this step.
        """
        pass

    @abstractmethod
    def compile(self) -> CompilationResult:
        """
        Compile the checker.
        """
        raise NotImplementedError

    @abstractmethod
    def run_checker(
        self,
        result: EvaluationResult,
        codename: str,
    ) -> EvaluationResult:
        """
        Run the checker and fill in relevant fields in EvaluationResult.

        Args:
            result: The current evaluation result after solution is executed.
            codename: The corresponding testcase codename.
        """
        raise NotImplementedError
