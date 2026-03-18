import math
import os
from pathlib import Path
import shutil
import typing
from internal.compilation.makefile import make_clean, make_compile_target
from internal.compilation.single import get_run_single_command

from internal.outcomes import (
    EvaluationOutcome,
    EvaluationResult,
    CompilationOutcome,
    CompilationResult,
)
from internal.process import Process, wait_procs
from internal.steps.utils import requires_sandbox

from .base import CheckerStep


class CMSCheckerStep(CheckerStep):
    """
    CheckerStep class implementing CMS (contest management system) checker behavior.

    This class also provides :meth:`white_diff` and :meth:`parse_std_manager_output` for reusable CMS components.

    See :class:`CheckerStep`.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.limits = self.context.config  # shorthand
        if len(self.arguments):
            pass
            # TODO: warn/error because CMS checker does not accept extra arguments

    @requires_sandbox
    def compile(self) -> CompilationResult:
        if self.use_default_checker:
            return CompilationResult(CompilationOutcome.SUCCESS)

        compile_result = make_compile_target(
            context=self.context,
            directory=self.context.path.checker,
            sources=[self.context.config.checker.filename],
            target="checker",
            executable_stack_size_mib=self.limits.trusted_step_memory_limit_mib,
        )

        # Finally, if success, ...
        if compile_result.verdict is CompilationOutcome.SUCCESS:
            if compile_result.produced_file is None:
                raise FileNotFoundError("Compilation did not produce checker")
            self.compiled_checker_path = compile_result.produced_file

        return compile_result

    def clean_up(self):
        make_clean(directory=self.context.path.checker)

    @classmethod
    def white_diff(
        cls, output: typing.BinaryIO, answer: typing.BinaryIO
    ) -> tuple[float, EvaluationOutcome, str]:
        """
        Performs CMS style whitediff on two binary readable streams.

        In CMS style whitediff, two lines are considered same if they contains the same tokens in the same order.
        The tokens are taken by treating consecutive ASCII space characters as separator.

        Args:
            output: The output stream to be checked against.
            answer: The answer stream to be checked against.

        Returns:
            tuple:
                A 3-tuple containing a `float`, an enum of `EvaluationOutcome`, and a `str`,
                representing the score (either 0.0 or 1.0), the verdict, and the admin feedback (not participant visible feedback)
        """

        WHITES = b" \t\n\r\v\f"
        TRUNC_LEN = 50

        def normalize(s: bytes):
            s = s.translate(bytes.maketrans(WHITES, b" " * len(WHITES)))
            return b" ".join(s.split())

        def truncate(s: bytes):
            return s if len(s) <= TRUNC_LEN else s[:TRUNC_LEN] + b"..."

        line = 1
        while True:
            line_out = normalize(output.readline())
            line_ans = normalize(answer.readline())

            if line_out == b"" and line_ans == b"":
                break
            if line_out != line_ans:
                return (
                    0.0,
                    EvaluationOutcome.WRONG,
                    f'On line {line}, found: "{truncate(line_out).decode(errors="ignore")}", expected: "{truncate(line_ans).decode(errors="ignore")}"',
                )
            line += 1

        return 1.0, EvaluationOutcome.ACCEPTED, ""

    @classmethod
    def parse_std_manager_output(
        cls, manager_out_filename: str, manager_err_filename: str, is_checker: bool
    ):
        """
        Reads CMS standard manager output and parse the respective judging results.

        Args:
            manager_out_filename: The standard output of the manager/checker.
            manager_err_filename: The standard error of the manager/checker.
            is_checker: Whether the manager is in fact a comparator. This slightly affects the verdict and the admin feedback string.

        Returns:
            tuple:
                A 4-tuple containing a `float`, an enum of `EvaluationOutcome`, and two optional `str`s.
                They represents the score, the verdict, the feedback to the participants, and to the admins.
                The last two might be None of the line does not exist in the standard error.
        """

        score: float = 0.0
        verdict: EvaluationOutcome
        display: str | None = None
        reason: str | None = None

        try:
            with open(manager_out_filename) as f:
                score = float(f.readline().strip())
                if math.isnan(score) or math.isinf(score):
                    raise ValueError("run_solution: manager score is NaN or infinities")
            if score <= 0:
                verdict = EvaluationOutcome.WRONG
            elif score < 1:
                verdict = EvaluationOutcome.PARTIAL
            else:
                verdict = EvaluationOutcome.ACCEPTED
        except ValueError:
            if is_checker:
                verdict = EvaluationOutcome.CHECKER_FAILED
                reason = "Comparator did not print a valid floating point number to standard output"
            else:
                verdict = EvaluationOutcome.MANAGER_FAILED
                reason = "Manager did not print a valid floating point number to standard output"

        with open(manager_err_filename) as f:
            display = f.readline().strip() or None
            reason = f.readline().strip() or None

            if display == "translate:success":
                display = EvaluationOutcome.ACCEPTED.value
            if display == "translate:wrong":
                display = EvaluationOutcome.WRONG.value
            if display == "translate:partial":
                display = EvaluationOutcome.PARTIAL.value

        return score, verdict, display, reason

    @requires_sandbox
    def run_checker(
        self,
        result: EvaluationResult,
        codename: str,
    ) -> EvaluationResult:

        # In CMS mode we do not need to check anything
        # we are guaranteed that the process does terminate successfully and checker always need to be run
        if result.verdict is not EvaluationOutcome.RUN_SUCCESS:
            result.checker_run = False
            return result

        input_file = os.path.join(
            self.context.path.testcases, self.context.construct_input_filename(codename)
        )
        output_file = result.output_file
        answer_file = os.path.join(
            self.context.path.testcases,
            self.context.construct_output_filename(codename),
        )

        if output_file is None or not Path(output_file).exists():
            result.verdict = EvaluationOutcome.NO_FILE

        self.sandbox.checker.clean()

        if self.use_default_checker:
            try:
                output_io = open(output_file, "rb")
                answer_io = open(answer_file, "rb")
                score, verdict, feedback = self.white_diff(output_io, answer_io)

            except Exception as e:
                score, verdict, feedback = (
                    0.0,
                    EvaluationOutcome.CHECKER_CRASHED,
                    f"Default whitediff failed with exception {str(e)}",
                )

            result.score = score
            result.verdict = verdict
            result.reason = feedback
            with open(
                os.path.join(self.log_directory, f"{codename}.check.err"), "w"
            ) as f:
                f.write(result.reason)

        else:
            assert self.compiled_checker_path is not None
            checker_exec_command = get_run_single_command(
                context=self.context,
                directory=os.path.dirname(self.compiled_checker_path),
                executable_filename_base="checker",
                executable_stack_size_mib=self.limits.trusted_step_memory_limit_mib,
            )
            assert checker_exec_command is not None

            # The checker is invoked via
            # checker input_file answer_file output_file > score 2> reason

            checker_out_file = os.path.join(
                self.sandbox.checker.path, f"{codename}.check.out"
            )
            checker_err_file = os.path.join(
                self.sandbox.checker.path, f"{codename}.check.err"
            )

            checker_process = Process(
                checker_exec_command + [input_file, answer_file, output_file],
                preexec_fn=lambda: os.chdir(self.sandbox.checker.path),
                stdin=None,
                stdout_redirect=checker_out_file,
                stderr_redirect=checker_err_file,
                time_limit_sec=self.limits.trusted_step_time_limit_sec,
                memory_limit_mib=self.limits.trusted_step_memory_limit_mib,
                output_limit_mib=self.limits.trusted_step_output_limit_mib,
            )

            shutil.copy(
                checker_out_file,
                os.path.join(self.log_directory, os.path.basename(checker_out_file)),
            )
            shutil.copy(
                checker_err_file,
                os.path.join(self.log_directory, os.path.basename(checker_err_file)),
            )

            wait_procs([checker_process])

            if checker_process.is_timedout:
                result.verdict = EvaluationOutcome.CHECKER_TIMEDOUT
            elif checker_process.is_signaled_exit or checker_process.exit_code:
                result.verdict = EvaluationOutcome.CHECKER_CRASHED
            else:
                score, verdict, display, reason = self.parse_std_manager_output(
                    checker_out_file, checker_err_file, True
                )

                result.score = score
                result.verdict = verdict
                result.override_verdict_display = display
                result.reason = result.reason or reason or ""

        return result
