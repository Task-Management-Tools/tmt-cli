import subprocess

from internal.outcome import (
    CompilationResult, CompilationOutcome, ExecutionResult, ExecutionOutcome, EvaluationResult, EvaluationOutcome
)

ANSI_RESET = "\033[0m"
ANSI_RED = "\033[31m"
ANSI_GREEN = "\033[32m"
ANSI_YELLOW = "\033[33m"
ANSI_BLUE = "\033[34m"
ANSI_PURPLE = "\033[35m"
ANSI_RED_BG = "\033[41m"
ANSI_GREY = "\033[90m"


def make_file_extension(ext: str):
    """Make sure the file extension starts with a dot."""
    if not ext.startswith('.'):
        ext = '.' + ext
    return ext


def print_compile_string(result: CompilationResult) -> None:
    """
    Prints the compilation output in formatted result.
    """
    if result.verdict not in [CompilationOutcome.SUCCESS, CompilationOutcome.SKIPPED]:
        print(f"[{ANSI_RED}FAIL{ANSI_RESET}]")
        print(f"{ANSI_YELLOW}exit-code:{ANSI_RESET} {result.exit_status}")
        if result.standard_output.strip() != "":
            print(f"{ANSI_YELLOW}standard output:{ANSI_RESET}\n{result.standard_output}")
        if result.standard_error.strip() != "":
            print(f"{ANSI_YELLOW}standard output:{ANSI_RESET}\n{result.standard_error}")
    elif result.verdict is CompilationOutcome.SKIPPED:
        print(f"[{ANSI_GREY}SKIP{ANSI_GREY}]")
    elif result.standard_error.find("warning") > 0:
        print(f"[{ANSI_YELLOW}WARN{ANSI_RESET}]")
    else:
        print(f"[{ANSI_GREEN}OK{ANSI_RESET}]")


def print_compile_string_with_exit(result: CompilationResult) -> str:
    """
    Prints the compilation output in formatted result. This function can exit the whole program if the 
    CompilationResult is failure.
    """
    print_compile_string(result)
    if result.verdict not in [CompilationOutcome.SUCCESS, CompilationOutcome.SKIPPED]:
        exit(1)


def format_exec_result(result: ExecutionResult) -> str:
    """
    Formats the execution output.
    """
    def format(color: str, content: str):
        return f"[{color}{content}{ANSI_RESET}]" + ' ' * (6 - len(content))

    if result.verdict is ExecutionOutcome.SUCCESS:
        return format(ANSI_GREEN, "OK")
    elif result.verdict is ExecutionOutcome.CRASHED:
        return format(ANSI_PURPLE, "RTE")
    elif result.verdict is ExecutionOutcome.FAILED:  # This is validation failed
        return format(ANSI_RED, "FAIL")
    elif result.verdict is ExecutionOutcome.TIMEDOUT:
        return format(ANSI_BLUE, "TLE")
    elif result.verdict is ExecutionOutcome.SKIPPED:
        return format(ANSI_GREY, "SKIP")
    else:
        raise ValueError(f"Unexpected ExecutionOutcome {result.verdict}")


def format_checker_result(result: EvaluationResult) -> str:
    """
    Formats the execution output.
    """
    # TODO: determine the real checker status, since TIOJ new-style checker runs even if the solution fails
    def format(checker_color: str, checker_status: str, content_color: str):
        return (f"[{checker_color}{checker_status}{ANSI_RESET}]" + ' ' * (6 - len(checker_status)) +
                f"{content_color}{result.verdict.value}{ANSI_RESET}" + ' ' * 2 + 
                result.checker_reason)

    group_accepted = [EvaluationOutcome.ACCEPTED]
    group_partial = [EvaluationOutcome.PARTIAL]
    group_wrong_answer = [EvaluationOutcome.WRONG, EvaluationOutcome.NO_FILE, EvaluationOutcome.NO_OUTPUT]
    group_timeout = [EvaluationOutcome.TIMEOUT, EvaluationOutcome.TIMEOUT_WALL]
    group_runtime_error = [EvaluationOutcome.RUNERROR_OUTPUT, EvaluationOutcome.RUNERROR_SIGNAL, EvaluationOutcome.RUNERROR_EXITCODE]
    group_judge_error = [EvaluationOutcome.MANAGER_CRASHED, EvaluationOutcome.MANAGER_TIMEOUT,
                         EvaluationOutcome.CHECKER_CRASHED,  EvaluationOutcome.CHECKER_FAILED, EvaluationOutcome.CHECKER_TIMEDOUT,
                         EvaluationOutcome.INTERNAL_ERROR]

    if result.verdict in group_accepted:
        return format(ANSI_GREEN, "OK", ANSI_GREEN)
    elif result.verdict in group_partial:
        return format(ANSI_GREEN, "OK", ANSI_YELLOW)
    elif result.verdict in group_wrong_answer:
        return format(ANSI_GREEN, "OK", ANSI_RED)
    elif result.verdict in group_timeout:
        return format(ANSI_GREY, "SKIP", ANSI_BLUE)
    elif result.verdict in group_runtime_error:
        return format(ANSI_GREY, "SKIP", ANSI_PURPLE)
    elif result.verdict in group_judge_error:
        return format(ANSI_RED, "FAIL", ANSI_RED_BG)
    else:
        raise ValueError(f"Unexpected EvaluationOutcome {result.verdict}")

def is_apport_active():
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "apport.service"],
            capture_output=True,
            text=True,
            check=False
        )
        return result.stdout.strip() == "active"
    except FileNotFoundError:
        return False  # systemctl not available
