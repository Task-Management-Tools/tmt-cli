import os
import platform
import resource
import shutil
import signal

from pathlib import Path

from internal.runner import Process, wait_procs
from internal.utils import make_file_extension
from internal.step_solution import MetaSolutionStep, EvaluationOutcome, EvaluationResult

# TODO: in this solution step, only one file can be submitted
class BatchSolutionStep(MetaSolutionStep):
    def __init__(self, executable_name: str, problem_dir: str, submission_file: str,
                 time_limit: float, memory_limit: int, output_limit: int,
                 grader: str | None, compile_time_limit: float = 10_000, compile_memory_limit: float = 4 * 1024 * 1024):
        super().__init__(executable_name=executable_name,
                         problem_dir=problem_dir,
                         memory_limit=memory_limit,
                         compile_time_limit=compile_time_limit,
                         compile_memory_limit=compile_memory_limit)

        self.time_limit = time_limit
        self.output_limit = (resource.RLIM_INFINITY if output_limit == 'unlimited' else output_limit)
        self.submission_file = submission_file
        self.grader = grader

        self.prepare_interactor = False
        self.prepare_manager = False
        self.prepare_checker = False

    def compile_solution(self) -> tuple[str, int]:
        files = [self.working_dir.replace_with_solution(self.submission_file)]
        if self.grader:
            files.append(self.working_dir.replace_with_grader(self.grader))

        # TODO: change this set to user specified
        if platform.system() == "Darwin":
            compile_flags = ["-std=gnu++20", "-O2", "-pipe", "-s"]
        else:
            compile_flags = ["-std=gnu++20", "-O2", "-pipe", "-static", "-s"]

        # TODO: tell this to the users
        cxx = os.getenv("CXX", "g++")

        return self.compile(cxx, files, compile_flags)

    def prepare_sandbox(self):
        self.working_dir.mkdir_sandbox_solution()

    def run_solution(self, code_name: str, input_ext: str, output_ext: str, store_output: bool) -> EvaluationResult:
        """
        This function only returns FileNotFoundError for execution error.

        If store_output is specified, then we will move the output out of the sandbox and store it to the testcases.
        Otherwise, we keep that file inside the sandbox, and we invoke checker to check the file.
        """
        input_ext = make_file_extension(input_ext)
        output_ext = make_file_extension(output_ext)

        file_in_name = f"{code_name}{input_ext}"
        file_out_name = f"{code_name}{output_ext}"
        if store_output:  # We are working with official output
            file_err_name = f"{code_name}.sol.err"
        else:  # We are invoking and testing the solution
            file_err_name = f"{code_name}.invoke.err"

        testcase_input = os.path.join(self.working_dir.testcases, file_in_name)
        sandbox_input_file = os.path.join(self.working_dir.sandbox_solution, file_in_name)
        sandbox_output_file = os.path.join(self.working_dir.sandbox_solution, file_out_name)
        sandbox_error_file = os.path.join(self.working_dir.sandbox_solution, file_err_name)
        Path(sandbox_output_file).touch()
        Path(sandbox_error_file).touch()

        try:
            shutil.copy(testcase_input, sandbox_input_file)

            solution = Process(os.path.join(self.working_dir.sandbox_solution, self.executable_name),
                               preexec_fn=lambda: os.chdir(self.working_dir.sandbox_solution),
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
            self.working_dir.mkdir_testcases()
            self.working_dir.mkdir_logs()

            # Move output
            if store_output:
                shutil.move(sandbox_output_file,
                            os.path.join(self.working_dir.testcases, file_out_name))
            # Move logs
            shutil.move(sandbox_error_file,
                        os.path.join(self.working_dir.logs, file_err_name))

        result = EvaluationResult(
            verdict=EvaluationOutcome.RUN_SUCCESS,
            execution_time=solution.cpu_time,
            execution_wall_clock_time=solution.wall_clock_time,
            execution_memory=solution.max_vss,
            exit_code=solution.exit_code,
            exit_signal=solution.exit_signal,
            output_file=None if store_output else sandbox_output_file
        )
        if solution.cpu_time > self.time_limit:
            result.verdict = EvaluationOutcome.TIMEOUT
        elif solution.is_timedout:
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
