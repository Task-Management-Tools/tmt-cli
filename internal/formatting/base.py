import sys

from abc import ABC, abstractmethod

from internal import commands
from internal.context.context import TMTContext
from internal.outcomes import (
    CompilationResult,
    ExecutionOutcome,
    EvaluationResult,
)


class Formatter(ABC):
    class AnsiSequence:
        def __init__(self, text: str):
            self.text = text

        def __str__(self):
            if sys.stdout.isatty():
                return self.text
            else:
                return ""

    def __init__(self):
        self.ANSI_RESET = ""
        self.ANSI_RED = ""
        self.ANSI_GREEN = ""
        self.ANSI_YELLOW = ""
        self.ANSI_BLUE = ""
        self.ANSI_PURPLE = ""
        self.ANSI_RED_BG = ""
        self.ANSI_GREY = ""
        self.ANSI_ORANGE = ""

    @abstractmethod
    def print(self, *args, endl=False) -> None:
        """
        Print everything in the argument lists.
        Newline should not be introduced since formatter might track the row/column where the cursor is.
        """

    def println(self, *args) -> None:
        """
        Print everything in the argument lists with an extra newline.
        """
        self.print(*args, endl=True)

    @abstractmethod
    def print_fixed_width(self, *args, width: int, endl=False) -> None:
        """
        Print everything in the argument lists, and pads to a fixed width.
        """

    @abstractmethod
    def print_compile_result(
        self, result: CompilationResult, name: str = "", endl: bool = True
    ) -> None:
        """
        Formats the compilation result.
        """

    @abstractmethod
    def print_exec_result(self, result: ExecutionOutcome) -> None:
        """
        Formats the execution output.
        """

    @abstractmethod
    def print_checker_reason(self, reason: str) -> None:
        """
        Formats the checker reason.
        """

    @abstractmethod
    def print_checker_status(self, result: EvaluationResult) -> None:
        """
        Formats the execution short status (the one with surrounded by square brackets).
        """

    @abstractmethod
    def print_testcase_verdict(
        self,
        result: EvaluationResult,
        context: "TMTContext",
        print_reason: bool = False,
    ) -> None:
        """
        Formats the execution verdict and reason.
        """

    @abstractmethod
    def print_exec_details(
        self, result: ExecutionOutcome, context: "TMTContext"
    ) -> None:
        """
        Formats the detail statistics of the execution output.
        """

    @abstractmethod
    def print_testset_summary(
        self,
        results: "list[commands.invoke.TestsetResult]",
        overall: "commands.invoke.TestsetResult",
        context: "TMTContext",
    ):
        """
        Formats the execution verdict and reason of a testset.
        """

    @abstractmethod
    def print_hash_diff(
        self, official_testcase_hashes: dict[str, str], testcase_hashes: dict[str, str]
    ) -> None:
        """
        Formats testcase input hashes diff in the terminal.
        """
