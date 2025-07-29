import os
import subprocess
import platform

from pathlib import Path

from internal.runner import Process, wait_for_outputs
from internal.outcome import CompilationOutcome, CompilationResult


MAKE = "make"


class MetaMakefileCompileStep:
    def __init__(self, *, makefile_path: str, time_limit: float, memory_limit: int):
        """
        Parameters:
            problem_dir: Absolute path to the problem working directory.
            makefile_path: Absolute path to the compilation Makefile.
            time_limit: Validation stage time limit per task (miliseconds, default: 30s).
            memory_limit: Validation stage memory limit per task (kbytes, default: 4 GB).
        """
        self.makefile_path = makefile_path
        self.time_limit = time_limit
        self.memory_limit = memory_limit

    def compile_with_make(self, directory) -> CompilationOutcome:
        command = [MAKE, "-C", directory, "-f", self.makefile_path]

        cxx_flags = os.getenv("CXXFLAGS", "")
        cxx_flags += "-std=c++20 -Wall -Wextra -O2"

        # On MacOS, this has to be set during compile time
        if platform.system() == "Darwin":
            cxx_flags += f" -Wl,--stack,{self.memory_limit}"

        compile_process = Process(command,
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE,
                                  time_limit=self.time_limit,
                                  memory_limit=self.memory_limit,
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
