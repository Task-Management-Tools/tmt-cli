import os
import shutil
import subprocess
from pathlib import Path

from internal.globals import context
from internal.step_meta_makefile import MetaMakefileCompileStep
from internal.runner import Process, pre_wait_procs, wait_procs
from internal.utils import make_file_extension


class GenerationStep(MetaMakefileCompileStep):
    def __init__(self):

        super().__init__(makefile_path=context.path.makefile_normal,
                         time_limit=context.config.trusted_step_time_limit,
                         memory_limit=context.config.trusted_step_memory_limit)

    def compile(self) -> tuple[str, str, bool]:
        return self.compile_with_make(context.path.generator)

    def prepare_sandbox(self):
        context.path.mkdir_sandbox()

    def run_generator(self, commands: list[list[str]], code_name: str, extra_output_exts: list[str]) -> bool:
        """
        This function can raise FileNotFoundError (when generator file or expected files do not exist),
        TimeoutError (when the generator timed-out), and ChildProcessError (when the generator crashes).
        """
        # TODO: handle FileNotFoundError and print actual meaningful error in the console.

        input_file = context.construct_input_filename(code_name)
        input_extra_files = [context.construct_test_filename(code_name, ext) for ext in extra_output_exts]

        # preprocess
        for command in commands:
            if command[0] == "manual":
                command[0] = "/usr/bin/cat"
                for i in range(1, len(command)):
                    command[i] = context.path.replace_with_manual(command[i])
            else:
                command[0] = context.path.replace_with_generator(command[0])

        file_err_names = []

        sandbox_output_file = os.path.join(context.path.sandbox, input_file)
        Path(sandbox_output_file).touch()
        for filename in input_extra_files:
            (Path(context.path.sandbox) / filename).touch()

        generator_processes: list[Process] = []
        prev_proc = None

        pre_wait_procs()
        # Launch each command, chaining stdin/stdout
        try:
            for i, command in enumerate(commands, 1):

                file_err_name = f"{code_name}.gen.err.{i}" if len(commands) > 1 else f"{code_name}.gen.err"
                sandbox_output_err = os.path.join(context.path.sandbox, file_err_name)
                file_err_names.append(file_err_name)

                # For the first command, stdin is inherited (None)
                stdin = prev_proc.stdout if prev_proc else None

                # For the last command, stdout goes to the file; otherwise to a pipe
                if i == len(commands):
                    stdout_redirect = sandbox_output_file
                else:
                    stdout_redirect = None

                proc = Process(command,
                               preexec_fn=lambda: os.chdir(context.path.sandbox),
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

        context.path.mkdir_logs()
        context.path.mkdir_testcases()

        try:
            # Move tests
            shutil.move(os.path.join(context.path.sandbox, input_file),
                        os.path.join(context.path.testcases, input_file))
            # Move extra files
            for filename in input_extra_files:
                shutil.move(os.path.join(context.path.sandbox, filename),
                            os.path.join(context.path.testcases, filename))
            # Move logs
            for file_err_name in file_err_names:
                shutil.move(os.path.join(context.path.sandbox, file_err_name),
                            os.path.join(context.path.logs, file_err_name))
        except FileNotFoundError:
            raise exception

        for process in generator_processes:
            if process.is_timedout:
                raise TimeoutError()
            if process.status != 0:
                raise ChildProcessError()
        return True
