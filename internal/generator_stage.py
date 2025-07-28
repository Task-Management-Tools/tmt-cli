import os
import shutil
import stat
import platform
import subprocess
from .paths import (
    GENERATOR_PATH, TESTS_PATH, SANDBOX_PATH, GENERATOR_MANUAL_PATH, LOGS_PATH,
    prepare_tests_dir, prepare_sandbox_dir, prepare_logs_dir)
from .runner import Process, wait_procs


MAKE = "make"
GENERATOR_LIST = "generators"


class GenerationStage:
    def __init__(self, problem_dir: str, makefile_loc: str,
                 time_limit: float = 10_000, memory_limit: int = 4 * 1024 * 1024):
        """
        @params time_limit: Generation stage time limit per task (miliseconds, default: 30s).
        @params time_limit: Generation stage memory limit per task (kbytes, default: 4 GB).
        """
        self.problem_dir = problem_dir
        self.makefile_loc = makefile_loc
        self.time_limit = time_limit
        self.memory_limit = memory_limit

    def compile_generator(self):
        command = [MAKE, "-s", "-C", os.path.join(self.problem_dir, GENERATOR_PATH), "-f", self.makefile_loc]

        cxx_flags = os.getenv("CXXFLAGS", "")
        cxx_flags += "-std=c++20 -Wall -Wextra -O2"

        # On MacOS, this has to be set during compile time
        if platform.system() == "Darwin":
            cxx_flags += f" -Wl,--stack,{self.memory_limit}"

        compile_process = Process(command,
                                  time_limit=self.time_limit,
                                  memory_limit=self.memory_limit,
                                  env={"CXXFLAGS": cxx_flags} | os.environ)

        wait_procs([compile_process])

    def prepare_sandbox(self):
        pass

    def _is_regular_file(self, path: str):
        if not os.path.exists(path):
            return False
        return True

    def _is_executable(self, path: str):
        if not os.path.exists(path):
            return False
        st = os.stat(path)
        if stat.S_ISREG(st.st_mode) and (st.st_mode & stat.S_IXUSR):
            return True
        return False

    def _replace_with_executable(self, file: str):
        generator_path = os.path.join(self.problem_dir, GENERATOR_PATH)
        if self._is_executable(os.path.join(generator_path, file)):
            return os.path.join(generator_path, file)
        elif self._is_executable(os.path.join(generator_path, file + ".exe")):
            return os.path.join(generator_path, file + ".exe")
        else:
            raise FileNotFoundError(f"Generator {file} could not be found.")

    def _replace_with_manual(self, file: str):
        generator_manual_path = os.path.join(self.problem_dir, GENERATOR_MANUAL_PATH)
        if self._is_regular_file(os.path.join(generator_manual_path, file)):
            return os.path.join(generator_manual_path, file)
        else:
            raise FileNotFoundError(f"Manual {file} could not be found.")

    def run_generator(self, commands, code_name, output_file, extra_output_extensions) -> bool:
        prepare_sandbox_dir(self.problem_dir)

        # preprocess
        for command in commands:
            if command[0] == "manual":
                command[0] = "/usr/bin/cat"
                for i in range(1, len(command)):
                    command[i] = self._replace_with_manual(command[i])
            else:
                command[0] = self._replace_with_executable(command[0])

        sandbox_dir = os.path.join(self.problem_dir, SANDBOX_PATH)
        file_out_name = f"{code_name}.gen.out"
        file_err_names = []
        sandbox_output_file = os.path.join(sandbox_dir, file_out_name)

        generator_processes: list[Process] = []
        prev_proc = None

        # Launch each command, chaining stdin/stdout
        for i, command in enumerate(commands, 1):

            file_err_name = f"{code_name}.gen.err.{i}" if len(commands) > 1 else f"{code_name}.gen.err"
            sandbox_output_err = os.path.join(sandbox_dir, file_err_name)
            file_err_names.append(file_err_name)

            # For the first command, stdin is inherited (None)
            stdin = prev_proc.stdout if prev_proc else None

            # For the last command, stdout goes to the file; otherwise to a pipe
            if i == len(commands):
                stdout_redirect = sandbox_output_file
            else:
                stdout_redirect = None

            proc = Process(command,
                           preexec_fn=lambda: os.chdir(sandbox_dir),
                           stdin=stdin,
                           stdout=subprocess.PIPE,
                           stdout_redirect=stdout_redirect,
                           stderr_redirect=sandbox_output_err,
                           time_limit=self.time_limit,
                           memory_limit=self.memory_limit)

            # We can close the previous stdout in the parent,
            # allowing the child to receive EOF when it’s done
            if prev_proc:
                prev_proc.stdout.close()

            generator_processes.append(proc)
            prev_proc = proc

        generator_processes[-1].stdout.close()
        wait_procs(generator_processes)

        prepare_logs_dir(self.problem_dir)
        prepare_tests_dir(self.problem_dir)

        try:
            # Move tests
            shutil.move(os.path.join(sandbox_dir, file_out_name), os.path.join(self.problem_dir, TESTS_PATH, output_file))
            # Move logs
            for file_err_name in file_err_names:
                shutil.move(os.path.join(sandbox_dir, file_err_name), os.path.join(self.problem_dir, LOGS_PATH, file_err_name))
        except FileNotFoundError:
            return False

        for process in generator_processes:
            if process.returncode != 0:
                return False
        return True
