import os
import platform
import shutil
import signal

from pathlib import Path

from internal.globals import context
from internal.runner import Process, pre_wait_procs, wait_procs
from internal.utils import make_file_extension
from internal.step_solution import MetaSolutionStep
from internal.outcome import EvaluationOutcome, EvaluationResult, CompilationResult

# TODO: in this solution step, only one file can be submitted
class BatchSolutionStep(MetaSolutionStep):
    def __init__(self, submission_files: list[str], grader: str | None):

        self.executable_name = context.config.problem_name
        self.time_limit = context.config.time_limit
        self.memory_limit = context.config.memory_limit
        self.output_limit = context.config.output_limit
    
        if len(submission_files) != 1:
            raise ValueError("Batch task only supports single file submission.")
        self.submission_file = submission_files[0]
        self.grader = grader

        self.prepare_interactor = False
        self.prepare_manager = False
        self.prepare_checker = False

    def compile_solution(self) -> CompilationResult:
        files = [self.submission_file]
        if self.grader:
            files.append(context.path.replace_with_grader(self.grader))

        # TODO: change this set to user specified
        if platform.system() == "Darwin":
            compile_flags = ["-std=gnu++20", "-O2", "-pipe", "-s"]
        else:
            compile_flags = ["-std=gnu++20", "-O2", "-pipe", "-static", "-s"]

        # TODO: tell this to the users
        cxx = os.getenv("CXX", "g++")

        return self.compile(cxx, files, compile_flags, self.memory_limit, self.executable_name)

    def prepare_sandbox(self):
        context.path.mkdir_sandbox_solution()


    def run_solution(self, code_name: str, store_output: None | str) -> EvaluationResult:
        """
        This function only returns FileNotFoundError for execution error.

        If store_output is specified, then we will move the output out of the sandbox and store it to the testcases.
        Otherwise, we keep that file inside the sandbox, and we invoke checker to check the file.
        """
        input_ext = make_file_extension(context.config.input_extension)
        output_ext = make_file_extension(context.config.output_extension)

        file_in_name = f"{code_name}{input_ext}"
        file_out_name = f"{code_name}{output_ext}"
        if store_output:  # We are working with official output
            file_err_name = f"{code_name}.sol.err"
        else:  # We are invoking and testing the solution
            file_err_name = f"{code_name}.invoke.err"

        testcase_input = os.path.join(context.path.testcases, file_in_name)
        sandbox_input_file = os.path.join(context.path.sandbox_solution, file_in_name)
        sandbox_output_file = os.path.join(context.path.sandbox_solution, file_out_name)
        sandbox_error_file = os.path.join(context.path.sandbox_solution, file_err_name)
        Path(sandbox_output_file).touch()
        Path(sandbox_error_file).touch()

        try:
            shutil.copy(testcase_input, sandbox_input_file)

            pre_wait_procs()
            solution = Process(os.path.join(context.path.sandbox_solution, self.executable_name),
                               preexec_fn=lambda: os.chdir(context.path.sandbox_solution),
                               stdin_redirect=sandbox_input_file,
                               stdout_redirect=sandbox_output_file,
                               stderr_redirect=sandbox_error_file,
                               time_limit=self.time_limit,
                               memory_limit=self.memory_limit,
                               output_limit=self.output_limit)

            wait_procs([solution])

            os.unlink(sandbox_input_file)

        except FileNotFoundError as exception:
            # We can simply raise, since there will be no processes left
            raise exception

        finally:
            # We have to clean up the testcases anyways
            context.path.mkdir_testcases()
            context.path.mkdir_logs()

            # Move output
            if store_output:
                shutil.move(sandbox_output_file,
                            os.path.join(context.path.testcases, file_out_name))
            # Move logs
            shutil.move(sandbox_error_file,
                        os.path.join(context.path.logs, file_err_name))

        result = EvaluationResult(
            verdict=EvaluationOutcome.RUN_SUCCESS,
            execution_time=solution.cpu_time,
            execution_wall_clock_time=solution.wall_clock_time,
            execution_memory=solution.max_vss,
            exit_code=solution.exit_code,
            exit_signal=solution.exit_signal,
            output_file=sandbox_output_file if store_output is not None else None 
        )

        if solution.cpu_time > self.time_limit / 1000:
            result.verdict = EvaluationOutcome.TIMEOUT
        elif solution.wall_clock_time > self.time_limit / 1000:
            result.verdict = EvaluationOutcome.TIMEOUT_WALL
        elif solution.exit_signal == signal.SIGXFSZ:
            result.verdict = EvaluationOutcome.RUNERROR_SIGNAL
        elif solution.exit_signal == signal.SIGXCPU: # this can happen
            result.verdict = EvaluationOutcome.TIMEOUT
        elif solution.exit_signal != 0:
            result.verdict = EvaluationOutcome.RUNERROR_SIGNAL
        elif solution.exit_code != 0:
            result.verdict = EvaluationOutcome.RUNERROR_EXITCODE

        return result
