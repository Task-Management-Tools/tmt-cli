import os
import shutil
import stat
import platform
import subprocess
from .paths import ProblemDirectoryHelper
from .runner import Process, wait_procs


MAKE = "make"
GENERATOR_LIST = "generators"


class GenerationStage:
    def __init__(self, problem_dir: str, makefile_path: str,
                 time_limit: float = 10_000, memory_limit: int = 4 * 1024 * 1024):
        """
        Parameters:
            problem_dir: Absolute path to the problem working directory.
            makefile_path: Absolute path to the compilation Makefile.
            time_limit: Generation stage time limit per task (miliseconds, default: 30s).
            memory_limit: Generation stage memory limit per task (kbytes, default: 4 GB).
        """
        self.working_dir = ProblemDirectoryHelper(problem_dir)
        self.makefile_path = makefile_path
        self.time_limit = time_limit
        self.memory_limit = memory_limit

    def compile_generator(self):
        command = [MAKE, "-s", "-C", self.working_dir.generator, "-f", self.makefile_path]

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
        self.working_dir.mkdir_sandbox()

    def _make_file_extension(self, ext: str):
        if not ext.startswith('.'):
            ext = '.' + ext
        return ext

    def run_generator(self, commands: list[list[str]], code_name: str,
                       output_ext: str, extra_output_exts: list[str]) -> bool:
        """
        This function can raise FileNotFoundError.
        """
        # TODO: handle FileNotFoundError and print actual meaningful error in the console.

        output_ext = self._make_file_extension(output_ext)
        for i in range(len(extra_output_exts)):
            extra_output_exts[i] = self._make_file_extension(extra_output_exts[i])

        # preprocess
        for command in commands:
            if command[0] == "manual":
                command[0] = "/usr/bin/cat"
                for i in range(1, len(command)):
                    command[i] = self.working_dir.replace_with_manual(command[i])
            else:
                command[0] = self.working_dir.replace_with_generator(command[0])

        file_out_name = f"{code_name}.gen.out"
        file_err_names = []
        sandbox_output_file = os.path.join(self.working_dir.sandbox, file_out_name)

        generator_processes: list[Process] = []
        prev_proc = None

        # Launch each command, chaining stdin/stdout
        try:
            for i, command in enumerate(commands, 1):

                file_err_name = f"{code_name}.gen.err.{i}" if len(commands) > 1 else f"{code_name}.gen.err"
                sandbox_output_err = os.path.join(self.working_dir.sandbox, file_err_name)
                file_err_names.append(file_err_name)

                # For the first command, stdin is inherited (None)
                stdin = prev_proc.stdout if prev_proc else None

                # For the last command, stdout goes to the file; otherwise to a pipe
                if i == len(commands):
                    stdout_redirect = sandbox_output_file
                else:
                    stdout_redirect = None

                proc = Process(command,
                            preexec_fn=lambda: os.chdir(self.working_dir.sandbox),
                            stdin=stdin,
                            stdout=subprocess.PIPE,
                            stdout_redirect=stdout_redirect,
                            stderr_redirect=sandbox_output_err,
                            time_limit=self.time_limit,
                            memory_limit=self.memory_limit)

                # Close the unnecessary pipes in the parent,
                # allowing the child to receive EOF when it's done
                if prev_proc:
                    prev_proc.stdout.close()

                generator_processes.append(proc)
                prev_proc = proc

        except FileNotFoundError as exception:
            for proc in generator_processes:
                proc.safe_kill()
            raise exception
        
        generator_processes[-1].stdout.close()
        wait_procs(generator_processes)

        self.working_dir.mkdir_logs()
        self.working_dir.mkdir_testcases()

        # Move extra files
        try:
            # Move tests
            shutil.move(os.path.join(self.working_dir.sandbox, file_out_name), 
                        os.path.join(self.working_dir.testcases, f"{code_name}{output_ext}"))
            # Move logs
            for file_err_name in file_err_names:
                shutil.move(os.path.join(self.working_dir.sandbox, file_err_name), 
                            os.path.join(self.working_dir.logs, file_err_name))
        except FileNotFoundError:
            raise exception

        for process in generator_processes:
            if process.returncode != 0:
                return False
        return True
