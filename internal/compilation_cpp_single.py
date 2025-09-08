import os
import platform
import subprocess

from pathlib import Path

from internal.outcome import CompilationResult, CompilationOutcome
from internal.runner import Process, wait_for_outputs

# TODO: this should be a class when we extend language supports


def compile_cpp_single(
    *,
    working_dir: str,
    files: list[str],
    compiler: str,
    compile_flags: list[str],
    compile_time_limit_sec: float,
    compile_memory_limit_mib: int,
    executable_stack_size_mib: int,
    executable_name: str,
) -> CompilationResult:
    """
    Stack size is specified in MiB.
    Returns a string as the compilation standard error, and an int as the exit code.
    The integer will be -1 if one of the files does not exist.
    """

    for file in files:
        if not Path(file).exists():
            return CompilationResult(
                verdict=CompilationOutcome.FAILED,
                standard_error=f"File {file} could not be found.",
                exit_status=-1,
            )

    # On MacOS, this has to be set during compile time
    if platform.system() == "Darwin":
        compile_flags += [f"-Wl,--stack,{executable_stack_size_mib * 1024 * 1024}"]

    compilation = Process(
        [compiler] + compile_flags + files + ["-o", executable_name],
        preexec_fn=lambda: os.chdir(working_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        time_limit_sec=compile_time_limit_sec,
        memory_limit_mib=compile_memory_limit_mib,
    )

    stdout, stderr = wait_for_outputs(compilation)

    if compilation.status == 0:
        verdict = CompilationOutcome.SUCCESS
    elif compilation.is_timedout:
        verdict = CompilationOutcome.TIMEDOUT
    else:
        verdict = CompilationOutcome.FAILED

    return CompilationResult(
        verdict=verdict,
        standard_output=stdout.rstrip(),
        standard_error=stderr.rstrip(),
        exit_status=compilation.status,
    )
