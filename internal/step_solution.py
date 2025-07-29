import os
import platform
import subprocess

from pathlib import Path

from internal.globals import context
from internal.runner import Process, wait_for_outputs
from internal.outcome import EvaluationResult, CompilationResult, CompilationOutcome


class MetaSolutionStep:
    def __init__(self, *, submission_files: list[str], grader: str | None):

        self.prepare_interactor = False
        self.prepare_manager = False
        self.prepare_checker = False

    def compile(self, compiler: str, files: list[str], flags: list[str],
                stack_size: int, executable_name: str) -> CompilationResult:
        """
        Stack size is specified in MB.
        Returns a string as the compilation standard error, and an int as the exit code.
        The integer will be -1 if one of the files does not exist.
        """
        for file in files:
            if not Path(file).exists():
                return CompilationResult(verdict=CompilationOutcome.FAILED,
                                         standard_error=f"File {file} could not be found.",
                                         exit_status=-1)

        cxx_flags = os.getenv("CXXFLAGS", "").split()
        cxx_flags += flags

        # On MacOS, this has to be set during compile time
        if platform.system() == "Darwin":
            cxx_flags += f" -Wl,--stack,{stack_size * 1024 * 1024}"

        cxx_flags += files + ["-o", executable_name]

        compilation = Process([compiler] + cxx_flags,
                              preexec_fn=lambda: os.chdir(context.path.sandbox_solution),
                              stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE,
                              time_limit=context.config.trusted_step_time_limit,
                              memory_limit=context.config.trusted_step_memory_limit)

        stdout, stderr = wait_for_outputs(compilation)
        return CompilationResult(verdict=(CompilationOutcome.SUCCESS if compilation.status == 0 else
                                          CompilationOutcome.TIMEDOUT if compilation.is_timedout else
                                          CompilationOutcome.FAILED),
                                 standard_output=stdout,
                                 standard_error=stderr,
                                 exit_status=compilation.status)

    def prepare_sandbox(self):
        context.path.mkdir_sandbox_solution()

    def compile_solution(self) -> CompilationResult:
        pass

    def compile_interactor(self) -> CompilationResult:
        pass

    def compile_manager(self) -> CompilationResult:
        pass

    def run_solution(self, code_name: str, store_output: None | str) -> EvaluationResult:
        """
        Runs solution for input file code_name. If store_output is not None, then move the solution to store_output.
        Otherwise, keep the output in the sandbox and report the file in EvaluationResult.
        """
        raise NotImplementedError
