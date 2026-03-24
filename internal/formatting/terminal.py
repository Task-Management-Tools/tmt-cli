import os

from internal import commands
from internal.context.context import TMTContext
from internal.outcomes import (
    CompilationOutcome,
    EvaluationOutcome,
    EvaluationResult,
    ExecutionOutcome,
)
from .base import Formatter


class TerminalFormatter(Formatter):
    """
    Implements formatting behavior in the terminals.
    """

    def __init__(self):
        super().__init__()
        self.ANSI_RESET = self.AnsiSequence("\033[0m")
        self.ANSI_RED = self.AnsiSequence("\033[31m")
        self.ANSI_GREEN = self.AnsiSequence("\033[32m")
        self.ANSI_YELLOW = self.AnsiSequence("\033[33m")
        self.ANSI_BLUE = self.AnsiSequence("\033[34m")
        self.ANSI_PURPLE = self.AnsiSequence("\033[35m")
        self.ANSI_RED_BG = self.AnsiSequence("\033[41m")
        self.ANSI_GREY = self.AnsiSequence("\033[90m")
        self.ANSI_ORANGE = self.AnsiSequence("\033[38:5:172m")

        try:
            self.terminal_width = os.get_terminal_size().columns
        except OSError:  # If stdout is not a terminal
            self.terminal_width = None
        self.cursor = 0

    def advance_cursor(self, num):
        if self.terminal_width is not None:
            self.cursor = (self.cursor + num) % self.terminal_width

    def print(self, *args, endl=False):
        # TODO: do we support endline in text?
        for arg in args:
            if not isinstance(arg, self.AnsiSequence):
                self.advance_cursor(len(str(arg)))

        if endl:
            self.cursor = 0
        print(*args, sep="", flush=True, end=("\n" if endl else ""))

    def print_fixed_width(self, *args, width, endl=False):
        total_length = 0
        for arg in args:
            if not isinstance(arg, self.AnsiSequence):
                total_length += len(str(arg))
        pad = " " * max(0, width - total_length)

        self.print(*args, pad, endl=endl)

    def print_compile_result(self, result, name: str = "", endl: bool = True):
        match result.verdict:
            case CompilationOutcome.FAILED:
                self.print("[", self.ANSI_RED, "FAIL", self.ANSI_RESET, "]")
            case CompilationOutcome.TIMEDOUT:
                self.print("[", self.ANSI_RED, "CTLE", self.ANSI_RESET, "]")
            case CompilationOutcome.SKIPPED:
                self.print("[", self.ANSI_GREY, "SKIP", self.ANSI_RESET, "]")
            case CompilationOutcome.SUCCESS:
                if result.standard_error.find("warning") > 0:
                    self.print("[", self.ANSI_YELLOW, "WARN", self.ANSI_RESET, "]")
                else:
                    self.print("[", self.ANSI_GREEN, "OK", self.ANSI_RESET, "]  ")
            case _:
                raise ValueError("Invaid enum")

        if len(name):
            self.print(" " * 2, name)

        if result:
            if endl:
                self.println()
            return

        self.println()
        self.print(
            self.ANSI_YELLOW,
            "exit-code: ",
            self.ANSI_RESET,
            result.exit_status,
            endl=True,
        )
        if result.standard_output.strip() != "":
            self.print(self.ANSI_YELLOW, "standard output:", self.ANSI_RESET, endl=True)
            self.print(result.standard_output, endl=True)
        if result.standard_error.strip() != "":
            self.print(self.ANSI_YELLOW, "standard error:", self.ANSI_RESET, endl=True)
            self.print(result.standard_error, endl=True)

    def print_exec_result(self, result):
        WIDTH = 7

        def format(color: str, content: str):
            return "[", color, content, self.ANSI_RESET, "]"

        if result is ExecutionOutcome.SUCCESS:
            self.print_fixed_width(*format(self.ANSI_GREEN, "OK"), width=WIDTH)
        elif result is ExecutionOutcome.CRASHED:
            self.print_fixed_width(*format(self.ANSI_PURPLE, "RTE"), width=WIDTH)
        elif result is ExecutionOutcome.FAILED:  # This is validation failed
            self.print_fixed_width(*format(self.ANSI_RED, "FAIL"), width=WIDTH)
        elif result is ExecutionOutcome.TIMEDOUT:
            self.print_fixed_width(*format(self.ANSI_BLUE, "TLE"), width=WIDTH)
        elif (
            result is ExecutionOutcome.SKIPPED
            or result is ExecutionOutcome.SKIPPED_SUCCESS
        ):
            self.print_fixed_width(*format(self.ANSI_GREY, "SKIP"), width=WIDTH)
        else:
            raise ValueError(f"Unexpected ExecutionOutcome {result}")

    def print_checker_reason(self, reason):
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
    group_wrong_answer = [
        EvaluationOutcome.WRONG,
        EvaluationOutcome.NO_FILE,
        EvaluationOutcome.NO_OUTPUT,
    ]
    group_timeout = [EvaluationOutcome.TIMEOUT, EvaluationOutcome.TIMEOUT_WALL]
    group_runtime_error = [
        EvaluationOutcome.RUNERROR_SIGNAL,
        EvaluationOutcome.RUNERROR_EXITCODE,
        EvaluationOutcome.RUNERROR_MEMORY,
    ]
    group_judge_error = [
        EvaluationOutcome.MANAGER_CRASHED,
        EvaluationOutcome.MANAGER_TIMEOUT,
        EvaluationOutcome.CHECKER_CRASHED,
        EvaluationOutcome.CHECKER_FAILED,
        EvaluationOutcome.CHECKER_TIMEDOUT,
        EvaluationOutcome.INTERNAL_ERROR,
    ]
    group_output_limit = [
        EvaluationOutcome.RUNERROR_OUTPUT,
        EvaluationOutcome.OUTPUT_LIMIT,
    ]

    def print_checker_status(self, result):
        # TODO: determine the real checker status, since TIOJ new-style checker runs even if the solution fails

        def print_result(checker_color: str, checker_status: str):
            self.print_fixed_width(
                "[", checker_color, checker_status, self.ANSI_RESET, "]", width=8
            )

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
        elif result.verdict in self.group_output_limit:
            return print_result(self.ANSI_GREY, "SKIP")
        elif result.verdict in self.group_judge_error:
            return print_result(self.ANSI_RED_BG, "FAIL")
        else:
            raise ValueError(f"Unexpected EvaluationOutcome {result.verdict}")

    def get_verdict_color(self, verdict: EvaluationOutcome):
        if verdict in self.group_accepted:
            return self.ANSI_GREEN
        elif verdict in self.group_partial:
            return self.ANSI_YELLOW
        elif verdict in self.group_wrong_answer:
            return self.ANSI_RED
        elif verdict in self.group_timeout:
            return self.ANSI_BLUE
        elif verdict in self.group_runtime_error:
            return self.ANSI_PURPLE
        elif verdict in self.group_output_limit:
            return self.ANSI_ORANGE
        elif verdict in self.group_judge_error:
            return self.ANSI_RED
        else:
            raise ValueError(f"Unexpected EvaluationOutcome {verdict}")

    def print_testcase_verdict(
        self,
        result: EvaluationResult,
        context: "TMTContext",
        print_reason: bool = False,
    ):
        # TODO: determine the real checker status, since TIOJ new-style checker runs even if the solution fails

        verdict_display = result.override_verdict_display or result.verdict.value

        self.print(self.get_verdict_color(result.verdict))

        if context.config.judge_convention.display_score:
            self.print(f"{result.score:<6.4g}  ")

        self.print_fixed_width(verdict_display, self.ANSI_RESET, " ", width=16)
        if print_reason:
            self.print_checker_reason(result.reason)

    def format_time_usage(self, time_sec: float, is_timer_triggered: bool):
        if is_timer_triggered:
            return f"> {time_sec:.3f}".rjust(7) + " s"
        else:
            return f"{time_sec:.3f}".rjust(7) + " s"

    def format_memory_usage(self, max_memory_kib: int, max_memory_upper_bound_kib: int):
        if max_memory_kib == -1:
            return (
                self.ANSI_GREY,
                f"< {max_memory_upper_bound_kib // 1024:3} MiB",
                self.ANSI_RESET,
            )
        else:
            return f"{max_memory_kib / 1024:5.4g} MiB"

    def format_points(self, point: float):
        return f"{point:.2f}".rstrip("0").rstrip(".")

    def print_exec_details(
        self, result: EvaluationResult, context: "TMTContext"
    ) -> None:
        self.print(
            self.format_time_usage(result.cpu_time_sec, result.timer_triggered),
            self.ANSI_RESET,
        )
        self.print(" / ")
        self.print(
            *self.format_memory_usage(
                result.max_memory_kib, result.max_memory_upper_bound_kib
            )
        )
        self.print(" " * 2)

    def print_testset_summary(
        self,
        results: "list[commands.invoke.TestsetResult]",
        overall: "commands.invoke.TestsetResult",
        context: "TMTContext",
    ):

        if context.config.judge_convention.display_testsets:
            self.println("Testset summary")
        else:
            self.println("Subtask summary")

        name_width = score_width = full_score_width = 0
        score = max_score = 0

        for r in results:
            name_width = max(name_width, len(r.testset_name))
            if not r.num_testcases:
                r.score = 0.0
            if r.max_score is not None:
                r.score *= r.max_score
                max_score += r.max_score
                score += r.score

                score_width = max(score_width, len(self.format_points(r.score)))
                full_score_width = max(
                    full_score_width, len(self.format_points(r.max_score))
                )

        overall.score, overall.max_score = score, max_score
        score_width = max(score_width, len(self.format_points(score)))
        full_score_width = max(full_score_width, len(self.format_points(max_score)))

        sol_config = context.config.solution

        def print_testset(ts: "commands.invoke.TestsetResult"):
            # Name
            self.print(" " * 4, ts.testset_name.ljust(name_width), " " * 4)

            if ts.num_testcases == 0:
                self.println(self.ANSI_RED, " " * 7, "(empty)", self.ANSI_RESET)
                return

            # Max time & memory
            self.print(
                self.ANSI_BLUE
                if ts.max_cpu_time_sec > sol_config.time_limit_sec
                else "",
                self.format_time_usage(ts.max_cpu_time_sec, ts.is_timer_triggered),
                self.ANSI_RESET,
            )
            self.print(" / ")
            self.print(
                self.ANSI_PURPLE
                if ts.max_memory_kib > sol_config.memory_limit_kib
                else "",
                *self.format_memory_usage(
                    ts.max_memory_kib, ts.max_memory_upper_bound_kib
                ),
                self.ANSI_RESET,
            )
            self.print(" " * 4)

            # Score
            if context.config.judge_convention.display_score:
                if ts.verdict == EvaluationOutcome.ACCEPTED:
                    score_color = self.ANSI_GREEN
                # When the scoring summary is different, it is partial if it obtains any score,
                # or it has the partial verdict (if the testset is 0 score)
                elif ts.score > 0 or ts.verdict == EvaluationOutcome.PARTIAL:
                    score_color = self.ANSI_YELLOW
                else:
                    score_color = self.ANSI_RESET

                self.print(
                    score_color,
                    self.format_points(ts.score).rjust(score_width),
                    " / ",
                    self.format_points(ts.max_score).rjust(full_score_width),
                    " pts",
                    self.ANSI_RESET,
                )
                self.print(" " * 4)

            # Verdict
            self.print_fixed_width(
                self.get_verdict_color(ts.verdict),
                ts.verdict.value,
                self.ANSI_RESET,
                width=28,
            )

            if ts.worst_testcase and ts.verdict != EvaluationOutcome.ACCEPTED:
                self.print("@ ", ts.worst_testcase)
            self.println()

        # Print testsets/subtasks
        for r in results:
            print_testset(r)
        self.println()

        # Print overall
        self.println("Overall")
        print_testset(overall)

    def print_hash_diff(self, official_testcase_hashes, testcase_hashes):
        if testcase_hashes == official_testcase_hashes:
            self.println(self.ANSI_GREEN, "Hash matches!", self.ANSI_RESET)
            return

        tab = " " * 4
        # Hash mismatch
        self.println(self.ANSI_RED, "Hash mismatches:", self.ANSI_RESET)
        common_files = official_testcase_hashes.keys() & testcase_hashes.keys()
        for filename in sorted(common_files):
            if official_testcase_hashes[filename] != testcase_hashes[filename]:
                self.println(
                    tab,
                    f"{filename}: {official_testcase_hashes[filename]} (found {testcase_hashes[filename]})",
                )
        # Missing files
        missing_files = official_testcase_hashes.keys() - testcase_hashes.keys()
        if len(missing_files) > 0:
            self.println(self.ANSI_RED, "Missing files:", self.ANSI_RESET)
            for file in sorted(missing_files):
                self.println(tab, file)
        # Extra files
        extra_files = testcase_hashes.keys() - official_testcase_hashes.keys()
        if len(extra_files) > 0:
            self.println(self.ANSI_RED, "Extra files:", self.ANSI_RESET)
            for file in sorted(extra_files):
                self.println(tab, file)
