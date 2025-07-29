from enum import Enum
from dataclasses import dataclass

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

class CompilationOutcome(Enum):
    # The compilation finished successfully.
    SUCCESS = "Compilation success"
    # The compilation failed because of non-zero exit code.
    FAILED = "Compilation failed"
    # The compilation timed-out.
    TIMEDOUT = "Compilation timed-out"
    # The compilation was not needed or skipped.
    SKIPPED = "Compilation skipped"

@dataclass
class CompilationResult:
    verdict: CompilationOutcome
    standard_output: str = ""
    standard_error: str = ""
    exit_status: int = 0
