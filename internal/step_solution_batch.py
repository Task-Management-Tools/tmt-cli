from __future__ import annotations

import os
import platform
import shutil
import signal

from pathlib import Path

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from internal.context import TMTContext
from internal.runner import Process, pre_wait_procs, wait_procs
from internal.compilation_cpp_single import compile_cpp_single
from internal.step_solution import MetaSolutionStep
from internal.outcome import EvaluationOutcome, EvaluationResult, CompilationResult



class BatchSolutionStep(MetaSolutionStep):
    def __init__(self, *, context: TMTContext,
                 time_limit: float, memory_limit: int, output_limit: int,
                 submission_files: list[str]):
        self.context = context

        self.executable_name = self.context.config.problem_name
        self.time_limit = time_limit
        self.memory_limit = memory_limit
        self.output_limit = output_limit

        if len(submission_files) != 1:
            raise ValueError("Batch task only supports single file submission.")
        self.submission_file = submission_files[0]
        self.grader = None # TODO: infer from config file (context)
        
        self.has_interactor = False

    def prepare_sandbox(self):
        self.context.path.mkdir_sandbox_solution()

    def compile_solution(self) -> CompilationResult:
        files = [self.submission_file]
        if self.grader is not None:
            files.append(self.context.path.replace_with_grader(self.grader))

        # TODO: change this set to user specified
        if platform.system() == "Darwin":
            compile_flags = ["-std=gnu++20", "-O2", "-pipe", "-s"]
        else:
            compile_flags = ["-std=gnu++20", "-O2", "-pipe", "-static", "-s"]

        return compile_cpp_single(working_dir=self.context.path.sandbox_solution,
                                  files=files, 
                                  flags=compile_flags, 
                                  # these parameters are intended trusted step time limit instead of compile limit, 
                                  # since they will occur on judge, so they should have more restrictive limits
                                  compile_time_limit_sec=self.context.config.trusted_step_time_limit_sec,
                                  compile_memory_limit_mib=self.context.config.trusted_step_memory_limit_mib,
                                  executable_stack_size_mib=self.memory_limit,
                                  executable_name=self.executable_name)

    def run_solution(self, code_name: str, store_output: None | str) -> EvaluationResult:
        """
        This function only returns FileNotFoundError for execution error.

        If store_output is specified, then we will move the output out of the sandbox and store it to the testcases.
        Otherwise, we keep that file inside the sandbox, and we invoke checker to check the file.
        """

        file_in_name = self.context.construct_input_filename(code_name)
        file_out_name = self.context.construct_output_filename(code_name)
        if store_output:  # We are working with official output
            file_err_name = f"{code_name}.sol.err"
        else:  # We are invoking and testing the solution
            file_err_name = f"{code_name}.invoke.err"

        testcase_input = os.path.join(self.context.path.testcases, file_in_name)
        sandbox_input_file = os.path.join(self.context.path.sandbox_solution, file_in_name)
        sandbox_output_file = os.path.join(self.context.path.sandbox_solution, file_out_name)
        sandbox_error_file = os.path.join(self.context.path.sandbox_solution, file_err_name)
        Path(sandbox_output_file).touch()
        Path(sandbox_error_file).touch()

        no_output_file = False

        try:
            shutil.copy(testcase_input, sandbox_input_file)

            pre_wait_procs()
            # TODO: noramlly judge should use pipe for I/O, which might make some subtle differences
            # currently, for convenience, it is from file but we should support both modes.
            solution = Process(os.path.join(self.context.path.sandbox_solution, self.executable_name),
                               preexec_fn=lambda: os.chdir(self.context.path.sandbox_solution),
                               stdin_redirect=sandbox_input_file,
                               stdout_redirect=sandbox_output_file,
                               stderr_redirect=sandbox_error_file,
                               time_limit=self.time_limit,
                               memory_limit=self.memory_limit,
                               output_limit=self.output_limit)
            wait_procs([solution])

            if Path(sandbox_input_file).exists():
                os.unlink(sandbox_input_file)

            # Prepare directories (normally the testcases should exist, just in case)
            self.context.path.mkdir_testcases()
            self.context.path.mkdir_logs()

            # Move logs
            Path(sandbox_error_file).touch()
            shutil.move(sandbox_error_file, os.path.join(self.context.path.logs, file_err_name))

            # Move output
            if store_output:
                if Path(sandbox_output_file).exists():
                    shutil.move(sandbox_output_file, os.path.join(self.context.path.testcases, file_out_name))
                else:
                    no_output_file = True
                    
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
            output_file=sandbox_output_file if store_output is not None else None
        )

        if no_output_file:
            result.verdict = EvaluationOutcome.NO_FILE
        elif solution.cpu_time > self.time_limit:
            result.verdict = EvaluationOutcome.TIMEOUT
        elif solution.wall_clock_time > self.time_limit:
            result.verdict = EvaluationOutcome.TIMEOUT_WALL
        elif solution.exit_signal == signal.SIGXFSZ:
            result.verdict = EvaluationOutcome.OUTPUT_LIMIT
        elif solution.exit_signal == signal.SIGXCPU:  # this can happen
            result.verdict = EvaluationOutcome.TIMEOUT
        elif solution.exit_signal != 0:
            result.verdict = EvaluationOutcome.RUNERROR_SIGNAL
            result.checker_reason = f"Execution killed by signal ({signal.strsignal(solution.exit_signal)})"
        elif solution.exit_code != 0:
            result.verdict = EvaluationOutcome.RUNERROR_EXITCODE
            result.checker_reason = f"Execution exited with exit code {solution.exit_code}"

        return result
