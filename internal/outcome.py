import os

from enum import Enum
from dataclasses import dataclass

from internal.runner import Process


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
    RUNERROR_MEMORY = "Runtime Error (memory limit exceeded)"
    # Runtime error caused by memory limit exceeded; this verdict only exists since we support MLE detection without cgroup.
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
    verdict: EvaluationOutcome = EvaluationOutcome.RUN_SUCCESS

    solution_cpu_time_sec: float = 0.0
    solution_wall_clock_time_sec: float = 0.0
    solution_max_memory_kib: int = 0
    solution_exit_code: int = 0
    solution_exit_signal: int = 0

    output_file: str = None

    checker_run: bool = False
    checker_reason: str = ""

    def fill_from_solution_process(self, solution: Process):
        self.verdict

        self.solution_cpu_time_sec = solution.cpu_time_sec
        self.solution_wall_clock_time_sec = solution.wall_clock_time_sec
        self.solution_max_memory_kib = solution.max_rss_kib
        self.solution_exit_code = solution.exit_code
        self.solution_exit_signal = solution.exit_signal


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

    def dump_to_logs(self, log_directory: str, job_name: str):
        os.makedirs(log_directory, exist_ok=True)
        with open(os.path.join(log_directory, job_name + ".compile.out"), "w+") as f:
            f.write(self.standard_output)
        with open(os.path.join(log_directory, job_name + ".compile.err"), "w+") as f:
            f.write(self.standard_error)


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

    group_accepted = [EvaluationOutcome.RUN_SUCCESS, EvaluationOutcome.ACCEPTED,
                      EvaluationOutcome.PARTIAL, EvaluationOutcome.WRONG, EvaluationOutcome.NO_FILE, EvaluationOutcome.NO_OUTPUT]
    group_timeout = [EvaluationOutcome.TIMEOUT, EvaluationOutcome.TIMEOUT_WALL]
    group_runtime_error = [EvaluationOutcome.RUNERROR_OUTPUT, EvaluationOutcome.RUNERROR_SIGNAL,
                           EvaluationOutcome.RUNERROR_EXITCODE, EvaluationOutcome.RUNERROR_MEMORY]
    group_judge_error = [EvaluationOutcome.MANAGER_CRASHED, EvaluationOutcome.MANAGER_TIMEOUT,
                         EvaluationOutcome.CHECKER_CRASHED,  EvaluationOutcome.CHECKER_FAILED, EvaluationOutcome.CHECKER_TIMEDOUT,
                         EvaluationOutcome.INTERNAL_ERROR]

    if eval_res.verdict in group_accepted:
        return ExecutionResult(verdict=ExecutionOutcome.SUCCESS, reason=eval_res.checker_reason)
    elif eval_res.verdict in group_timeout:
        return ExecutionResult(verdict=ExecutionOutcome.TIMEDOUT, reason=eval_res.checker_reason)
    elif eval_res.verdict in group_runtime_error:
        return ExecutionResult(verdict=ExecutionOutcome.CRASHED, reason=eval_res.checker_reason)
    elif eval_res.verdict in group_judge_error:
        return ExecutionResult(verdict=ExecutionOutcome.FAILED, reason=eval_res.checker_reason)
    else:
        raise ValueError(f"Unexpected verdict when running solution: {eval_res.verdict}")
