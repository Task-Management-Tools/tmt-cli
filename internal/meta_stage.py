import os
import subprocess
import platform
from .paths import ProblemDirectoryHelper
from .runner import Process, wait_for_outputs


MAKE = "make"

class MetaMakefileCompileStage:
    def __init__(self, problem_dir: str, makefile_path: str,
                 time_limit: float = 10_000, memory_limit: int = 4 * 1024 * 1024):
        """
        Parameters:
            problem_dir: Absolute path to the problem working directory.
            makefile_path: Absolute path to the compilation Makefile.
            time_limit: Validation stage time limit per task (miliseconds, default: 30s).
            memory_limit: Validation stage memory limit per task (kbytes, default: 4 GB).
        """
        self.working_dir = ProblemDirectoryHelper(problem_dir)
        self.makefile_path = makefile_path
        self.time_limit = time_limit
        self.memory_limit = memory_limit

    def compile_with_make(self, directory) -> bool:
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
        return stdout, stderr, compile_process.status
