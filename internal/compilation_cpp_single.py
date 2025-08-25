import os
import platform
import subprocess

from pathlib import Path

from internal.outcome import CompilationResult, CompilationOutcome
from internal.runner import Process, wait_for_outputs

# TODO: this should be a class when we extend language supports


def compile_cpp_single(*, working_dir: str, files: list[str], flags: list[str],
                       compile_time_limit_sec: float, compile_memory_limit_mib: int,
                       executable_stack_size_mib: int, executable_name: str) -> CompilationResult:
    """
    Stack size is specified in MiB.
    Returns a string as the compilation standard error, and an int as the exit code.
    The integer will be -1 if one of the files does not exist.
    """
    if flags is None:
        # TODO: change this set to user specified
        if platform.system() == "Darwin":
            flags = ["-std=gnu++20", "-O2", "-pipe", "-s"]
        else:
            flags = ["-std=gnu++20", "-O2", "-pipe", "-static", "-s"]

    for file in files:
        if not Path(file).exists():
            return CompilationResult(verdict=CompilationOutcome.FAILED,
                                     standard_error=f"File {file} could not be found.",
                                     exit_status=-1)

    # TODO: tell this to the users
    compiler = os.getenv("CXX", "g++")

    cxx_flags = os.getenv("CXXFLAGS", "").split()
    cxx_flags += flags

    # On MacOS, this has to be set during compile time
    if platform.system() == "Darwin":
        cxx_flags += f" -Wl,--stack,{executable_stack_size_mib * 1024 * 1024}"

    cxx_flags += files + ["-o", executable_name]

    compilation = Process([compiler] + cxx_flags,
                          preexec_fn=lambda: os.chdir(working_dir),
                          stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE,
                          time_limit=compile_time_limit_sec,
                          memory_limit=compile_memory_limit_mib)

    stdout, stderr = wait_for_outputs(compilation)
    return CompilationResult(verdict=(CompilationOutcome.SUCCESS if compilation.status == 0 else
                                      CompilationOutcome.TIMEDOUT if compilation.is_timedout else
                                      CompilationOutcome.FAILED),
                             standard_output=stdout,
                             standard_error=stderr,
                             exit_status=compilation.status)
