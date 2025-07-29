
ANSI_RESET = "\033[0m"
ANSI_RED = "\033[31m"
ANSI_GREEN = "\033[32m"
ANSI_YELLOW = "\033[33m"

def make_file_extension(ext: str):
    """Make sure the file extension starts with a dot."""
    if not ext.startswith('.'):
        ext = '.' + ext
    return ext

def format_make_compile_string(stdout: str, stderr: str, returncode: int) -> str:
    """
    Formats the compilation output.
    """
    if returncode != 0:
        return (f"[{ANSI_RED}FAIL{ANSI_RESET}]\n" + 
                f"{ANSI_YELLOW}exit-code:{ANSI_RESET} {returncode}\n" +
                f"{ANSI_YELLOW}standatd output:{ANSI_RESET}\n{stdout}\n" +
                f"{ANSI_YELLOW}standatd error:{ANSI_RESET}\n{stderr}\n")
    elif stderr.find("warning") > 0:
        return f"[{ANSI_YELLOW}WARN{ANSI_RESET}]\n"
    else:
        return f"[{ANSI_GREEN}OK{ANSI_RESET}]\n"

def format_single_compile_string(stderr: str, returncode: int) -> str:
    """
    Formats the compilation output.
    """
    if returncode != 0:
        return (f"[{ANSI_RED}FAIL{ANSI_RESET}]\n" + 
                f"{ANSI_YELLOW}exit-code:{ANSI_RESET} {returncode}\n" +
                f"{ANSI_YELLOW}standatd error:{ANSI_RESET}\n{stderr}\n")
    elif stderr.find("warning") > 0:
        return f"[{ANSI_YELLOW}WARN{ANSI_RESET}]\n"
    else:
        return f"[{ANSI_GREEN}OK{ANSI_RESET}]\n"

def format_single_run_string(result: bool) -> str:
    """
    Formats the compilation output.
    """
    if result == False:
        return f"[{ANSI_RED}FAIL{ANSI_RESET}]"
    else:
        return f"[{ANSI_GREEN}OK{ANSI_RESET}]  "