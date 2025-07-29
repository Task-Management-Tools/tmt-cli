import os
import platform
import subprocess

from enum import Enum
from dataclasses import dataclass

from internal.globals import context
from internal.runner import Process, wait_for_outputs


class EvaluationOutcome(Enum):
    # The submission has run successfully.
    RUN_SUCCESS = "run-success"
    # The submission has run successfully and is correct.
    ACCEPTED = "success"
    # The submission has run successfully and is partially correct.
    PARTIAL = "partial"
    # The submission has run successfully but is not correct (typical sense of WA).
    WRONG = "wrong"
    # CMS no-output: not producing the required file
    NO_FILE = "no-file"
    # DOMJudge no-output (incorrect and not producing output)
    NO_OUTPUT = "no-output"
    # classic TLE
    TIMEOUT = "timeout"
    # This is wall-clock exceeded TLE; DOMJudge, CMS, and Codeforces all supports this result.
    TIMEOUT_WALL = "wall-clock-timeout"
    # Output limit exceeded. Since DOMJudge actually detects output limit by truncating the stream
    # instead of TIOJ-style signal detection, we will need separate verdicts.
    OUTPUT_LIMIT = "output-limit"
    # Runtime error caused by signal SIGXFSZ. TIOJ treat this as OLE.
    RUNERROR_OUTPUT = "run-error-output-exceed"
    # Runtime error caused by signal (FPE, SEGV, etc.) except SIGXFSZ.
    RUNERROR_SIGNAL = "runtime-error-signal"
    # Runtime error caused by non-zero exitcode.
    RUNERROR_EXITCODE = "runtime-error-exitcode"
    # Manager/Interactor crashed.
    MANAGER_CRASHED = "manager-crashed"
    # Manager/Interactor timed out.
    MANAGER_TIMEOUT = "manager-timeout"
    # Checker crashed.
    CHECKER_CRASHED = "checker-crashed"
    # Checker failed.
    CHECKER_FAILED = "checker-crashed"
    # Checker timed-out.
    CHECKER_TIMEDOUT = "checker-timeout"
    # Internal error.
    INTERNAL_ERROR = "internal-error"


@dataclass
class EvaluationResult:
    verdict: EvaluationOutcome
    execution_time: float
    execution_wall_clock_time: float
    execution_memory: int
    exit_code: int
    exit_signal: int
    output_file: str


class MetaSolutionStep:
    def __init__(self, *, executable_name: str, memory_limit: int):
        # memory_limit is required because compilation requires setting stack size in MacOS

        self.executable_name = executable_name
        self.memory_limit = memory_limit

        self.prepare_interactor = False
        self.prepare_manager = False
        self.prepare_checker = False

    def compile(self, compiler: str, files: list[str], flags: list[str]) -> tuple[str, int]:

        cxx_flags = os.getenv("CXXFLAGS", "").split()
        cxx_flags += flags

        # On MacOS, this has to be set during compile time
        if platform.system() == "Darwin":
            cxx_flags += f" -Wl,--stack,{self.memory_limit}"

        cxx_flags += files + ["-o", self.executable_name]

        compilation = Process([compiler] + cxx_flags,
                              preexec_fn=lambda: os.chdir(context.path.sandbox_solution),
                              stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE,
                              time_limit=context.config.trusted_step_time_limit,
                              memory_limit=context.config.trusted_step_memory_limit)

        _, stderr = wait_for_outputs(compilation)
        return stderr, compilation.status

    def prepare_sandbox(self):
        context.path.mkdir_sandbox_solution()

    def compile_solution(self) -> tuple[str, int]:
        pass

    def compile_interactor(self) -> tuple[str, int]:
        pass

    def compile_manager(self) -> tuple[str, int]:
        pass

    def run_solution(self, code_name: str, store_output: None | str) -> EvaluationResult:
        """
        Runs solution for input file code_name. If store_output is not None, then move the solution to store_output.
        Otherwise, keep the output in the sandbox and report the file in EvaluationResult.
        """
        raise NotImplementedError
