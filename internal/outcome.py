from enum import Enum
from dataclasses import dataclass


class EvaluationOutcome(Enum):
    # The submission has run successfully.
    RUN_SUCCESS = "Solution ran successfully"
    # The submission has run successfully and is correct.
    ACCEPTED = "Correct"
    # The submission has run successfully and is partially correct.
    PARTIAL = "Partially Correct"
    # The submission has run successfully but is not correct (typical sense of WA).
    WRONG = "Wrong Answer"
    # CMS no-output: not producing the required file
    NO_FILE = "No Output File Found"
    # DOMJudge no-output (incorrect and not producing output)
    NO_OUTPUT = "No Output"
    # classic TLE
    TIMEOUT = "Time Limit Exceeded"
    # This is wall-clock exceeded TLE; DOMJudge, CMS, and Codeforces all supports this result.
    TIMEOUT_WALL = "Time Limit Exceeded (wall clock)"
    # Output limit exceeded. Since DOMJudge actually detects output limit by truncating the stream
    # instead of TIOJ-style signal detection, we will need separate verdicts.
    OUTPUT_LIMIT = "Output Limit Exceeded"
    # Runtime error caused by signal SIGXFSZ. TIOJ treat this as OLE.
    RUNERROR_OUTPUT = "Runtime Error (output limit exceeded)"
    # Runtime error caused by signal (FPE, SEGV, etc.) except SIGXFSZ.
    RUNERROR_SIGNAL = "Runtime Error (signaled)"
    # Runtime error caused by non-zero exitcode.
    RUNERROR_EXITCODE = "Runtime Error (non-zero exit code)"
    # Manager/Interactor crashed.
    MANAGER_CRASHED = "Judge Error: Manager Crashed"
    # Manager/Interactor timed out.
    MANAGER_TIMEOUT = "Judge Error: Manager Timed-out"
    # Checker crashed (this is checker exited by signaled).
    CHECKER_CRASHED = "Judge Error: Checker Crashed"
    # Checker failed (this is checker exit with non-zero return code).
    CHECKER_FAILED = "Judge Error: Checker Failed"
    # Checker timed-out.
    CHECKER_TIMEDOUT = "Judge Error: Checker Timed-out"
    # Internal error.
    INTERNAL_ERROR = "Internal Error"


@dataclass
class EvaluationResult:
    verdict: EvaluationOutcome
    execution_time: float
    execution_wall_clock_time: float
    execution_memory: int
    exit_code: int
    exit_signal: int
    output_file: str

    checker_run: bool = False
    checker_reason: str = ""


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


class ExecutionOutcome(Enum):
    # The execution finished successfully.
    SUCCESS = "Execution success"
    # The execution crashed.
    CRASHED = "Execution crashed"
    # The execution crashed.
    FAILED = "Execution failed"
    # The execution timed-out.
    TIMEDOUT = "Execution timed-out"
    # The execution was not needed or skipped (most likely because the previous one is skipped).
    SKIPPED = "Execution Skipped"


@dataclass
class ExecutionResult:
    verdict: ExecutionOutcome
    reason: str = ""

    def __bool__(self):
        return self.verdict is ExecutionOutcome.SUCCESS


def eval_result_to_exec_result(eval_res: EvaluationResult) -> ExecutionResult:
    """
    Maps EvaluationResult to ExecutionResult, whenwhether output is correct is not relavant here.
    (For example, when generating answer files.)
    """
    allowed_outcome = [EvaluationOutcome.RUN_SUCCESS,
                       EvaluationOutcome.NO_FILE,
                       EvaluationOutcome.TIMEOUT,
                       EvaluationOutcome.TIMEOUT_WALL,
                       EvaluationOutcome.RUNERROR_OUTPUT,
                       EvaluationOutcome.RUNERROR_SIGNAL,
                       EvaluationOutcome.RUNERROR_EXITCODE]
    if eval_res.verdict not in allowed_outcome:
        raise ValueError(f"Expect verdict to be one of {allowed_outcome}, found {eval_res.verdict}")

    if eval_res.verdict is EvaluationOutcome.RUN_SUCCESS:
        return ExecutionResult(verdict=ExecutionOutcome.SUCCESS)
    elif eval_res.verdict is EvaluationOutcome.TIMEOUT or eval_res.verdict is EvaluationOutcome.TIMEOUT_WALL:
        return ExecutionResult(verdict=ExecutionOutcome.TIMEDOUT)
    else:
        reason = ("Output limit reached" if eval_res.verdict is EvaluationOutcome.RUNERROR_OUTPUT else
                  f"Solution crashed with signal {eval_res.exit_signal}" if eval_res.verdict is EvaluationOutcome.RUNERROR_SIGNAL else
                  f"Solution exited with non-zero exit code {eval_res.exit_code}" if eval_res.verdict is EvaluationOutcome.RUNERROR_EXITCODE else
                  f"Solution did not produce required file" if eval_res.verdict is  EvaluationOutcome.NO_FILE else
                  f"Unknown error {eval_res}")
        return ExecutionResult(verdict=ExecutionOutcome.CRASHED,
                               reason=reason)
