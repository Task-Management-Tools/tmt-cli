import os
import platform
import shutil
import signal
import subprocess

from pathlib import Path

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from internal.context import TMTContext

from internal.runner import Process, pre_wait_procs, wait_procs
from internal.compilation_makefile import compile_with_make
from internal.compilation_cpp_single import compile_cpp_single
from internal.step_solution import MetaSolutionStep
from internal.outcome import EvaluationOutcome, EvaluationResult, CompilationOutcome, CompilationResult


class InteractiveICPCSolutionStep(MetaSolutionStep):
    """Implements ICPC interactive problem evaluation."""

    def __init__(self, *, context: 'TMTContext', is_trusted, submission_files: list[str]):
        super().__init__(context=context,
                         is_trusted=is_trusted,
                         submission_files=submission_files)

        if len(submission_files) != 1:
            raise ValueError("ICPC-style interactive task only supports single file submission.")

    @classmethod
    def has_interactor(cls):
        return True

    @classmethod
    def skip_checker(cls):
        return True

    def prepare_sandbox(self):
        self.context.path.mkdir_sandbox_solution()
        self.context.path.mkdir_sandbox_checker()

    def compile_solution(self) -> CompilationResult:
        files = self.submission_files

        return compile_cpp_single(working_dir=self.context.path.sandbox_solution,
                                  files=files,
                                  flags=None,
                                  # these parameters are intended trusted step time limit instead of compile limit,
                                  # since they will occur on judge, so they should have more restrictive limits
                                  compile_time_limit_sec=self.context.config.trusted_step_time_limit_sec,
                                  compile_memory_limit_mib=self.context.config.trusted_step_memory_limit_mib,
                                  executable_stack_size_mib=self.memory_limit_mib,
                                  executable_name=self.executable_name)

    def compile_interactor(self) -> CompilationResult:
        if self.context.path.has_checker_directory():
            compile_result = compile_with_make(makefile_path=self.context.path.makefile_checker,
                                               directory=self.context.path.checker,
                                               compile_time_limit_sec=self.context.config.trusted_compile_time_limit_sec,
                                               compile_memory_limit_mib=self.context.config.trusted_compile_memory_limit_mib,
                                               executable_stack_size_mib=self.context.config.trusted_step_memory_limit_mib)
            shutil.copy(os.path.join(self.context.path.checker, "checker"), self.context.path.sandbox_checker)
            return compile_result
        return CompilationResult(CompilationOutcome.FAILED, "`checker' directory not found.")

    def run_solution(self, code_name: str, store_output: None | str) -> EvaluationResult:
        """
        This function only returns FileNotFoundError for execution error.

        If store_output is specified, then we create an empty file as dummy output file.
        """

        file_in_name = self.context.construct_input_filename(code_name)
        file_out_name = self.context.construct_output_filename(code_name)
        if store_output:  # We are working with official output
            file_sol_err_name = f"{code_name}.sol.err"
        else:  # We are invoking and testing the solution
            file_sol_err_name = f"{code_name}.invoke.err"
        file_checker_err_name = f"{code_name}.checker.err"

        testcase_input = os.path.join(self.context.path.testcases, file_in_name)
        testcase_answer = os.path.join(self.context.path.testcases, file_out_name)
        sandbox_checker_input_file = os.path.join(self.context.path.sandbox_checker, file_in_name)
        sandbox_checker_answer_file = os.path.join(self.context.path.sandbox_checker, file_out_name)
        sandbox_checker_err_file = os.path.join(self.context.path.sandbox_checker, file_checker_err_name)
        sandbox_solution_err_file = os.path.join(self.context.path.sandbox_solution, file_sol_err_name)

        try:
            shutil.copy(testcase_input, sandbox_checker_input_file)
            if Path(testcase_answer).exists():
                shutil.copy(testcase_answer, sandbox_checker_answer_file)
            else:
                Path(sandbox_checker_answer_file).touch()

            feedback_dir = os.path.join(self.context.path.sandbox_solution, "feedback_dir") + os.sep
            if not os.path.isdir(feedback_dir):
                os.mkdir(feedback_dir)

            pre_wait_procs()
            
            def solution_preexec_fn():
                os.chdir(self.context.path.sandbox_solution)
                signal.signal(signal.SIGPIPE, signal.SIG_IGN)
            solution = Process(os.path.join(self.context.path.sandbox_solution, self.executable_name),
                               preexec_fn=solution_preexec_fn,
                               stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE,
                               stderr_redirect=sandbox_solution_err_file,
                               time_limit=self.time_limit_sec,
                               memory_limit=self.memory_limit_mib,
                               output_limit=self.output_limit_mib)

            def interactor_preexec_fn():
                os.chdir(self.context.path.sandbox_checker)
                signal.signal(signal.SIGPIPE, signal.SIG_IGN)
            interactor = Process([os.path.join(self.context.path.sandbox_checker, "checker"),
                                  sandbox_checker_input_file, sandbox_checker_answer_file, feedback_dir],
                                 preexec_fn=interactor_preexec_fn,
                                 stdin=solution.stdout,
                                 stdout=solution.stdin,
                                 stderr_redirect=sandbox_checker_err_file,
                                 time_limit=max(self.time_limit_sec, self.context.config.trusted_step_time_limit_sec) + 1,
                                 memory_limit=self.context.config.trusted_step_memory_limit_mib,
                                 output_limit=self.context.config.trusted_step_output_limit_mib)

            solution.stdin.close()
            solution.stdout.close()

            wait_procs([solution, interactor])

            if Path(sandbox_checker_input_file).exists():
                os.unlink(sandbox_checker_input_file)
            if Path(sandbox_checker_answer_file).exists():
                os.unlink(sandbox_checker_answer_file)

            # Prepare directories (normally the testcases should exist, just in case)
            self.context.path.mkdir_testcases()
            self.context.path.mkdir_logs()

            # Move logs
            Path(sandbox_checker_err_file).touch()
            shutil.move(sandbox_checker_err_file, os.path.join(self.context.path.logs, file_checker_err_name))
            Path(sandbox_solution_err_file).touch()
            shutil.move(sandbox_solution_err_file, os.path.join(self.context.path.logs, file_sol_err_name))

            # Move output
            if store_output:
                dummy_output_file = os.path.join(self.context.path.testcases, file_out_name)
                with open(dummy_output_file, "w+b"):
                    pass  # Truncate the file

        except FileNotFoundError as exception:
            # We can simply raise, since there will be no processes left
            # This should be treated as internal error
            raise exception

        result = EvaluationResult(
            verdict=EvaluationOutcome.RUN_SUCCESS,
            execution_time=solution.cpu_time,
            execution_wall_clock_time=solution.wall_clock_time,
            execution_memory=solution.max_vss,
            exit_code=solution.exit_code,
            exit_signal=solution.exit_signal,
            output_file=None
        )

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
            checker_feedback_file = Path(feedback_dir) / "judgemessage.txt"
            if checker_feedback_file.is_file():
                with open(checker_feedback_file, "r") as f:
                    result.checker_reason = f.readline().strip()

        shutil.rmtree(feedback_dir)

        return result
