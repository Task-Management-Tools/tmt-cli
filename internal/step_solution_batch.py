import os
import platform
import resource
import shutil

from pathlib import Path

from internal.runner import Process, wait_procs
from internal.utils import make_file_extension
from internal.step_solution import MetaSolutionStep


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
        self.working_dir.mkdir_sandbox()
        self.working_dir.clear_sandbox()

    def _run_solution(self, code_name: str, input_ext: str, output_ext: str) -> bool:
        pass

    def run_solution_for_output(self, code_name: str, input_ext: str, output_ext: str) -> bool:
        """
        This function can raise FileNotFoundError (when validator file or expected files do not exist),
        TimeoutError (when the validator timed-out), and ChildProcessError (when the validator crashes by signaled).

        Note the latter is not the same with validation failed: validators could still run sucessfully and return non-zero value.
        """
        # TODO: abstract this to _run_solution to reuse it for actual evaluation.

        input_ext = make_file_extension(input_ext)
        output_ext = make_file_extension(output_ext)

        # It is fine to use the same output file: we use O_TRUNC so the logs will be the last
        # validator stdout/stderr.
        file_in_name = f"{code_name}{input_ext}"
        file_out_name = f"{code_name}{output_ext}"
        file_err_name = f"{code_name}.sol.err"
        sandbox_input_file = os.path.join(self.working_dir.sandbox, file_in_name)
        sandbox_output_file = os.path.join(self.working_dir.sandbox, file_out_name)
        sandbox_error_file = os.path.join(self.working_dir.sandbox, file_err_name)
        Path(sandbox_output_file).touch()
        Path(sandbox_error_file).touch()

        try:
            shutil.copy(os.path.join(self.working_dir.testcases, file_in_name),
                        sandbox_input_file)

            solution = Process(os.path.join(self.working_dir.sandbox, self.executable_name),
                               preexec_fn=lambda: os.chdir(self.working_dir.sandbox),
                               stdin_redirect=sandbox_input_file,
                               stdout_redirect=sandbox_output_file,
                               stderr_redirect=sandbox_error_file,
                               time_limit=self.time_limit,
                               memory_limit=self.memory_limit,
                               output_limit=self.output_limit)

            wait_procs([solution])
            if solution.is_timedout or solution.is_signaled_exit or solution.status:
                return False

        except FileNotFoundError as exception:
            # We can simply raise, since there will be no processes left
            raise exception

        self.working_dir.mkdir_testcases()
        self.working_dir.mkdir_logs()

        try:
            os.unlink(sandbox_input_file)
            # Move output
            shutil.move(sandbox_output_file,
                        os.path.join(self.working_dir.testcases, file_out_name))
            # Move logs
            shutil.move(sandbox_error_file,
                        os.path.join(self.working_dir.logs, file_err_name))
        except FileNotFoundError as exception:
            raise exception

        return True
