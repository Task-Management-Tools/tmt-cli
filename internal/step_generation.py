import os
import shutil
import subprocess
from pathlib import Path

from internal.step_meta_makefile import MetaMakefileCompileStep
from internal.runner import Process, wait_procs
from internal.utils import make_file_extension


class GenerationStep(MetaMakefileCompileStep):
    def __init__(self, problem_dir: str, makefile_path: str,
                 time_limit: float = 10_000, memory_limit: int = 4 * 1024 * 1024):
        super().__init__(problem_dir=problem_dir,
                         makefile_path=makefile_path,
                         time_limit=time_limit,
                         memory_limit=memory_limit)

    def compile(self) -> tuple[str, str, bool]:
        return self.compile_with_make(self.working_dir.generator)

    def prepare_sandbox(self):
        self.working_dir.mkdir_sandbox()

    def run_generator(self, commands: list[list[str]], code_name: str,
                      output_ext: str, extra_output_exts: list[str]) -> bool:
        """
        This function can raise FileNotFoundError (when generator file or expected files do not exist),
        TimeoutError (when the generator timed-out), and ChildProcessError (when the generator crashes).
        """
        # TODO: handle FileNotFoundError and print actual meaningful error in the console.

        output_ext = make_file_extension(output_ext)
        for i in range(len(extra_output_exts)):
            extra_output_exts[i] = make_file_extension(extra_output_exts[i])

        # preprocess
        for command in commands:
            if command[0] == "manual":
                command[0] = "/usr/bin/cat"
                for i in range(1, len(command)):
                    command[i] = self.working_dir.replace_with_manual(command[i])
            else:
                command[0] = self.working_dir.replace_with_generator(command[0])

        file_out_name = f"{code_name}.out"
        file_extra_out_names = [f"{code_name}{ext}" for ext in extra_output_exts]
        file_err_names = []

        sandbox_output_file = os.path.join(self.working_dir.sandbox, file_out_name)
        Path(sandbox_output_file).touch()
        for file_extra_out_name in file_extra_out_names:
            (Path(self.working_dir.sandbox) / file_extra_out_name).touch()



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

        try:
            # Move tests
            shutil.move(os.path.join(self.working_dir.sandbox, file_out_name),
                        os.path.join(self.working_dir.testcases, f"{code_name}{output_ext}"))
            # Move extra files
            for file_extra_out_name in file_extra_out_names:
                shutil.move(os.path.join(self.working_dir.sandbox, file_extra_out_name),
                            os.path.join(self.working_dir.testcases, file_extra_out_name))
            # Move logs
            for file_err_name in file_err_names:
                shutil.move(os.path.join(self.working_dir.sandbox, file_err_name),
                            os.path.join(self.working_dir.logs, file_err_name))
        except FileNotFoundError:
            raise exception

        for process in generator_processes:
            if process.is_timedout:
                raise TimeoutError()
            if process.status != 0:
                raise ChildProcessError()
        return True
