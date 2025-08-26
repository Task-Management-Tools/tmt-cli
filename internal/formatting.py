import sys
import os

from internal.outcome import (
    CompilationResult, CompilationOutcome, ExecutionResult, ExecutionOutcome, EvaluationResult, EvaluationOutcome
)


class Formatter:
    class AnsiSequence:
        def __init__(self, text: str):
            self.text = text

        def __str__(self):
            if sys.stdout.isatty():
                return self.text
            else:
                return ""

    def __init__(self):
        self.ANSI_RESET = self.AnsiSequence("\033[0m")
        self.ANSI_RED = self.AnsiSequence("\033[31m")
        self.ANSI_GREEN = self.AnsiSequence("\033[32m")
        self.ANSI_YELLOW = self.AnsiSequence("\033[33m")
        self.ANSI_BLUE = self.AnsiSequence("\033[34m")
        self.ANSI_PURPLE = self.AnsiSequence("\033[35m")
        self.ANSI_RED_BG = self.AnsiSequence("\033[41m")
        self.ANSI_GREY = self.AnsiSequence("\033[90m")

        try:
            self.terminal_width = os.get_terminal_size().columns
        except OSError:  # If stdout is not a terminal
            self.terminal_width = None
        self.cursor = 0

    def advance_cursor(self, num: int):
        if self.terminal_width is not None:
            self.cursor = (self.cursor + num) % self.terminal_width

    def print(self, *args, endl=False) -> None:
        # TODO: do we support endline in text?
        for arg in args:
            if not isinstance(arg, self.AnsiSequence):
                self.advance_cursor(len(str(arg)))

        if endl:
            self.cursor = 0
        print(*args, sep="", flush=True, end=('\n' if endl else ""))

    def print_fixed_width(self, *args, width: int, endl=False) -> None:
        total_length = 0
        for arg in args:
            if not isinstance(arg, self.AnsiSequence):
                total_length += len(str(arg))
        pad = ' ' * max(0, width - total_length)
        self.advance_cursor(max(width, total_length))

        if endl:
            self.cursor = 0
        print(*args, pad, flush=True, sep="", end=('\n' if endl else ""))

    def print_compile_string(self, result: CompilationResult) -> None:
        """
        Prints the compilation output in formatted result.
        """
        if result.verdict not in [CompilationOutcome.SUCCESS, CompilationOutcome.SKIPPED]:
            self.print('[', self.ANSI_RED, "FAIL", self.ANSI_RESET, ']', endl=True)
            self.print(self.ANSI_YELLOW, "exit-code: ", self.ANSI_RESET, result.exit_status, endl=True)
            if result.standard_output.strip() != "":
                self.print(self.ANSI_YELLOW, "standard output:", self.ANSI_RESET, endl=True)
                self.print(result.standard_output, endl=True)
            if result.standard_error.strip() != "":
                self.print(self.ANSI_YELLOW, "standard error:", self.ANSI_RESET, endl=True)
                self.print(result.standard_error, endl=True)
        elif result.verdict is CompilationOutcome.SKIPPED:
            self.print("[", self.ANSI_GREY, "SKIP", self.ANSI_RESET, "]", endl=True)
        elif result.standard_error.find("warning") > 0:
            self.print("[", self.ANSI_YELLOW, "WARN", self.ANSI_RESET, "]", endl=True)
        else:
            self.print("[", self.ANSI_GREEN, "OK", self.ANSI_RESET, "]", endl=True)

    def print_compile_string_with_exit(self, result: CompilationResult) -> str:
        """
        Prints the compilation output in formatted result. This function can exit the whole program if the 
        CompilationResult is failure.
        """
        self.print_compile_string(result)
        if result.verdict not in [CompilationOutcome.SUCCESS, CompilationOutcome.SKIPPED]:
            exit(1)

    def print_exec_result(self, result: ExecutionResult) -> None:
        """
        Formats the execution output.
        """
        WIDTH = 7

        def format(color: str, content: str):
            return '[', color, content, self.ANSI_RESET, ']'

        if result.verdict is ExecutionOutcome.SUCCESS:
            self.print_fixed_width(*format(self.ANSI_GREEN, "OK"), width=WIDTH)
        elif result.verdict is ExecutionOutcome.CRASHED:
            self.print_fixed_width(*format(self.ANSI_PURPLE, "RTE"), width=WIDTH)
        elif result.verdict is ExecutionOutcome.FAILED:  # This is validation failed
            self.print_fixed_width(*format(self.ANSI_RED, "FAIL"), width=WIDTH)
        elif result.verdict is ExecutionOutcome.TIMEDOUT:
            self.print_fixed_width(*format(self.ANSI_BLUE, "TLE"), width=WIDTH)
        elif result.verdict is ExecutionOutcome.SKIPPED:
            self.print_fixed_width(*format(self.ANSI_GREY, "SKIP"), width=WIDTH)
        else:
            raise ValueError(f"Unexpected ExecutionOutcome {result.verdict}")

    def print_reason(self, reason: str):
        # TODO: the following terminal width threshold should be configurable via global settings 
        if self.terminal_width is not None and self.terminal_width >= 96:
            buffer = reason
            cursor_position = self.cursor
            while len(buffer):
                self.print_fixed_width(width=cursor_position - self.cursor)
                remain_width = self.terminal_width - self.cursor
                self.print(buffer[:remain_width])
                buffer = buffer[remain_width:]
        else:
            self.print(reason)

    group_accepted = [EvaluationOutcome.ACCEPTED]
    group_partial = [EvaluationOutcome.PARTIAL]
    group_wrong_answer = [EvaluationOutcome.WRONG, EvaluationOutcome.NO_FILE, EvaluationOutcome.NO_OUTPUT]
    group_timeout = [EvaluationOutcome.TIMEOUT, EvaluationOutcome.TIMEOUT_WALL]
    group_runtime_error = [EvaluationOutcome.RUNERROR_OUTPUT, EvaluationOutcome.RUNERROR_SIGNAL, 
                            EvaluationOutcome.RUNERROR_EXITCODE, EvaluationOutcome.RUNERROR_MEMORY]
    group_judge_error = [EvaluationOutcome.MANAGER_CRASHED, EvaluationOutcome.MANAGER_TIMEOUT,
                            EvaluationOutcome.CHECKER_CRASHED,  EvaluationOutcome.CHECKER_FAILED, EvaluationOutcome.CHECKER_TIMEDOUT,
                            EvaluationOutcome.INTERNAL_ERROR]
        
    def print_checker_status(self, result: EvaluationResult) -> str:
        """
        Formats the execution short status (the one with surrounded by square brackets).
        """
        # TODO: determine the real checker status, since TIOJ new-style checker runs even if the solution fails

        def print_result(checker_color: str, checker_status: str):
            self.print_fixed_width('[', checker_color, checker_status, self.ANSI_RESET, ']', width=8)



        if result.verdict in self.group_accepted:
            return print_result(self.ANSI_GREEN, "OK")
        elif result.verdict in self.group_partial:
            return print_result(self.ANSI_GREEN, "OK")
        elif result.verdict in self.group_wrong_answer:
            return print_result(self.ANSI_GREEN, "OK")
        elif result.verdict in self.group_timeout:
            return print_result(self.ANSI_GREY, "SKIP")
        elif result.verdict in self.group_runtime_error:
            return print_result(self.ANSI_GREY, "SKIP")
        elif result.verdict in self.group_judge_error:
            return print_result(self.ANSI_RED_BG, "FAIL")
        else:
            raise ValueError(f"Unexpected EvaluationOutcome {result.verdict}")

    def print_checker_verdict(self, result: EvaluationResult, print_reason: bool = False) -> str:
        """
        Formats the execution verdict and reason.
        """
        # TODO: determine the real checker status, since TIOJ new-style checker runs even if the solution fails

        def print_result(content_color: str):
            self.print_fixed_width(content_color, result.verdict.value, self.ANSI_RESET, ' ', width=16)
            if print_reason:
                self.print_reason(result.checker_reason)

        if result.verdict in self.group_accepted:
            return print_result(self.ANSI_GREEN)
        elif result.verdict in self.group_partial:
            return print_result(self.ANSI_YELLOW)
        elif result.verdict in self.group_wrong_answer:
            return print_result(self.ANSI_RED)
        elif result.verdict in self.group_timeout:
            return print_result(self.ANSI_BLUE)
        elif result.verdict in self.group_runtime_error:
            return print_result(self.ANSI_PURPLE)
        elif result.verdict in self.group_judge_error:
            return print_result(self.ANSI_RED)
        else:
            raise ValueError(f"Unexpected EvaluationOutcome {result.verdict}")
