import os
import shutil
import signal
import subprocess
from pathlib import Path

from internal.context import TMTContext
from internal.runner import Process, pre_wait_procs, wait_procs
from internal.compilation_makefile import compile_with_make, clean_with_make
from internal.compilation_cpp_single import compile_cpp_single
from internal.outcome import (
    EvaluationOutcome,
    EvaluationResult,
    CompilationOutcome,
    CompilationResult,
)

from .base import SolutionStep


class InteractiveICPCSolutionStep(SolutionStep):
    """Implements ICPC interactive problem evaluation."""

    def __init__(
        self, *, context: TMTContext, is_generation: bool, submission_files: list[str]
    ):
        super().__init__(
            context=context,
            is_generation=is_generation,
            submission_files=submission_files,
        )

    @classmethod
    def has_interactor(cls):
        return True

    @classmethod
    def skip_checker(cls):
        return True

    def prepare_sandbox(self):
        os.makedirs(self.context.path.sandbox_solution, exist_ok=True)
        os.makedirs(self.context.path.sandbox_checker, exist_ok=True)

    def clean_up(self):
        clean_with_make(
            makefile_path=self.context.path.makefile_checker,
            directory=self.context.path.checker,
            context=self.context,
        )

    def compile_solution(self) -> CompilationResult:
        if len(self.submission_files) != 1:
            return CompilationResult(
                verdict=CompilationOutcome.FAILED,
                exit_status=-1,
                standard_error="ICPC-style interactive task only supports single file submission.",
            )

        comp_result = compile_cpp_single(
            working_dir=self.context.path.sandbox_solution,
            files=self.submission_files,
            compiler=self.context.compiler("cpp"),
            compile_flags=self.context.compile_flags("cpp"),
            # these parameters are intended trusted step time limit instead of compile limit,
            # since they will occur on judge, so they should have more restrictive limits
            compile_time_limit_sec=self.context.config.trusted_step_time_limit_sec,
            compile_memory_limit_mib=self.context.config.trusted_step_memory_limit_mib,
            executable_stack_size_mib=self.memory_limit_mib,
            executable_name=self.executable_name,
        )
        comp_result.dump_to_logs(self.log_directory, "solution")
        return comp_result

    def compile_interactor(self) -> CompilationResult:
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

            comp_result.dump_to_logs(self.log_directory, "interactor")
            return comp_result
        return CompilationResult(
            CompilationOutcome.FAILED, "`checker' directory not found."
        )

    def run_solution(self, code_name: str) -> EvaluationResult:
        """
        This function only returns FileNotFoundError for execution error.

        If store_output is specified, then we create an empty file as dummy output file.
        """
        os.makedirs(self.log_directory, exist_ok=True)

        file_in_name = self.context.construct_input_filename(code_name)
        file_out_name = self.context.construct_output_filename(code_name)
        file_sol_err_name = f"{code_name}.sol.err"
        file_checker_err_name = f"{code_name}.checker.err"

        testcase_input = os.path.join(self.context.path.testcases, file_in_name)
        testcase_answer = os.path.join(self.context.path.testcases, file_out_name)
        sandbox_checker_input_file = os.path.join(
            self.context.path.sandbox_checker, file_in_name
        )
        sandbox_checker_answer_file = os.path.join(
            self.context.path.sandbox_checker, file_out_name
        )
        sandbox_checker_err_file = os.path.join(
            self.context.path.sandbox_checker, file_checker_err_name
        )
        sandbox_checker_feedback_dir = (
            os.path.join(self.context.path.sandbox_checker, "feedback_dir") + os.sep
        )
        sandbox_solution_err_file = os.path.join(
            self.context.path.sandbox_solution, file_sol_err_name
        )

        # Create dummy output
        if self.is_generation:
            with open(testcase_answer, "w+b"):
                pass  # Truncate the file

        try:
            shutil.copy(testcase_input, sandbox_checker_input_file)
            shutil.copy(testcase_answer, sandbox_checker_answer_file)

            if not os.path.isdir(sandbox_checker_feedback_dir):
                os.mkdir(sandbox_checker_feedback_dir)
            self.context.path.empty_directory(sandbox_checker_feedback_dir)

            sigset = pre_wait_procs()

            def solution_preexec_fn():
                os.chdir(self.context.path.sandbox_solution)
                signal.signal(signal.SIGPIPE, signal.SIG_IGN)

            solution = Process(
                os.path.join(self.context.path.sandbox_solution, self.executable_name),
                preexec_fn=solution_preexec_fn,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr_redirect=sandbox_solution_err_file,
                time_limit_sec=self.time_limit_sec,
                memory_limit_mib=self.memory_limit_mib,
                output_limit_mib=self.output_limit_mib,
            )

            def interactor_preexec_fn():
                os.chdir(self.context.path.sandbox_checker)
                signal.signal(signal.SIGPIPE, signal.SIG_IGN)

            interactor = Process(
                [
                    os.path.join(self.context.path.sandbox_checker, "checker"),
                    sandbox_checker_input_file,
                    sandbox_checker_answer_file,
                    sandbox_checker_feedback_dir,
                ],
                preexec_fn=interactor_preexec_fn,
                stdin=solution.stdout,
                stdout=solution.stdin,
                stderr_redirect=sandbox_checker_err_file,
                time_limit_sec=max(
                    self.time_limit_sec * 2,
                    self.context.config.trusted_step_time_limit_sec,
                )
                + 1,
                memory_limit_mib=self.context.config.trusted_step_memory_limit_mib,
                output_limit_mib=self.context.config.trusted_step_output_limit_mib,
            )

            assert solution.stdin is not None and solution.stdout is not None
            solution.stdin.close()
            solution.stdout.close()

            wait_procs([solution, interactor], sigset)

            if Path(sandbox_checker_input_file).exists():
                os.unlink(sandbox_checker_input_file)
            if Path(sandbox_checker_answer_file).exists():
                os.unlink(sandbox_checker_answer_file)

            # Move logs
            Path(sandbox_checker_err_file).touch()
            shutil.move(
                sandbox_checker_err_file,
                os.path.join(self.log_directory, file_checker_err_name),
            )
            Path(sandbox_solution_err_file).touch()
            shutil.move(
                sandbox_solution_err_file,
                os.path.join(self.log_directory, file_sol_err_name),
            )

            checker_feedback_logs = os.path.join(
                self.log_directory, f"{code_name}.checker.feedback"
            )
            if os.path.isdir(checker_feedback_logs):
                shutil.rmtree(checker_feedback_logs)
            shutil.copytree(
                sandbox_checker_feedback_dir,
                os.path.join(self.log_directory, f"{code_name}.checker.feedback"),
            )

        except FileNotFoundError as exception:
            # We can simply raise, since there will be no processes left
            # This should be treated as internal error
            raise exception

        result = EvaluationResult(
            verdict=EvaluationOutcome.RUN_SUCCESS, output_file=None
        )
        result.fill_from_solution_process(solution)

        # First, we check if the interactor crashed
        if interactor.is_timedout:
            result.verdict = EvaluationOutcome.CHECKER_TIMEDOUT
        elif interactor.is_signaled_exit:
            result.verdict = EvaluationOutcome.CHECKER_CRASHED
        # else, we check if solution executed successfully
        elif self.is_solution_abormal_exit(solution, result):
            pass
        # Noe, we can check if solution is actually correct
        elif interactor.exit_code == 42:
            result.verdict = EvaluationOutcome.ACCEPTED
        else:
            result.verdict = EvaluationOutcome.WRONG

            # See ICPCCheckerStep.
            checker_feedback_file = (
                Path(sandbox_checker_feedback_dir) / "judgemessage.txt"
            )
            if checker_feedback_file.is_file():
                with open(checker_feedback_file, "r") as f:
                    result.checker_reason = f.readline().strip()

        shutil.rmtree(sandbox_checker_feedback_dir)

        return result
