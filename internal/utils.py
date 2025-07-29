from internal.outcome import CompilationResult, CompilationOutcome

ANSI_RESET = "\033[0m"
ANSI_RED = "\033[31m"
ANSI_GREEN = "\033[32m"
ANSI_YELLOW = "\033[33m"
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


def format_single_compile_string(stderr: str, returncode: int) -> str:
    """
    Formats the compilation output.
    """
    if returncode != 0:
        return (f"[{ANSI_RED}FAIL{ANSI_RESET}]\n" +
                f"{ANSI_YELLOW}exit-code:{ANSI_RESET} {returncode}\n" +
                f"{ANSI_YELLOW}standard error:{ANSI_RESET}\n{stderr}\n")
    elif stderr.find("warning") > 0:
        return f"[{ANSI_YELLOW}WARN{ANSI_RESET}]\n"
    else:
        return f"[{ANSI_GREEN}OK{ANSI_RESET}]\n"


def format_single_run_string(result: bool) -> str:
    """
    Formats the execution output.
    """
    if result == False:
        return f"[{ANSI_RED}FAIL{ANSI_RESET}]"
    else:
        return f"[{ANSI_GREEN}OK{ANSI_RESET}]  "
