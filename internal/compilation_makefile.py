import os
import subprocess
import platform

from pathlib import Path

from internal.runner import Process, wait_for_outputs
from internal.outcome import CompilationOutcome, CompilationResult


MAKE = "make"


def compile_with_make(*, makefile_path: str, directory: str,
                      compile_time_limit_sec: float, compile_memory_limit_mib: int,
                      executable_stack_size_mib: int) -> CompilationOutcome:
    command = [MAKE, "-C", directory, "-f", makefile_path]

    cxx_flags = os.getenv("CXXFLAGS", "")
    cxx_flags += "-std=c++20 -Wall -Wextra -O2"

    # On MacOS, this has to be set during compile time
    if platform.system() == "Darwin":
        cxx_flags += f" -Wl,--stack,{executable_stack_size_mib}"

    compile_process = Process(command,
                              stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE,
                              time_limit=compile_time_limit_sec,
                              memory_limit=compile_memory_limit_mib,
                              env={"CXXFLAGS": cxx_flags} | os.environ)
    stdout, stderr = wait_for_outputs(compile_process)

    # We have to obtain stderr again from files if they are piped out.
    logs = sorted(Path(directory).glob('._*.compile.log'))
    for log in logs:
        with log.open('r') as infile:
            stderr += infile.read()

    return CompilationResult(verdict=(CompilationOutcome.SUCCESS if compile_process.status == 0 else
                                      CompilationOutcome.TIMEDOUT if compile_process.is_timedout else
                                      CompilationOutcome.FAILED),
                             standard_output=stdout,
                             standard_error=stderr,
                             exit_status=compile_process.status)
