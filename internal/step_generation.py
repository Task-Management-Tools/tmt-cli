import os
import shutil
import subprocess
from pathlib import Path

from internal.context import TMTContext
from internal.compilation_makefile import compile_with_make
from internal.runner import Process, pre_wait_procs, wait_procs
from internal.outcome import CompilationResult, ExecutionResult, ExecutionOutcome


class GenerationStep:
    def __init__(self, context: TMTContext):
        self.context = context
        self.limits = context.config # for short hand reference

    def compile(self) -> CompilationResult:
        return compile_with_make(makefile_path=self.context.path.makefile_normal,
                                 directory=self.context.path.generator,
                                 compile_time_limit_sec=self.limits.trusted_compile_time_limit_sec,
                                 compile_memory_limit_mib=self.limits.trusted_compile_memory_limit_mib,
                                 executable_stack_size_mib=self.limits.trusted_step_memory_limit_mib)

    def prepare_sandbox(self):
        self.context.path.mkdir_sandbox()

    def run_generator(self, commands: list[list[str]], code_name: str, extra_output_exts: list[str]) -> ExecutionResult:
        """
        This function only raises Exception for internal errors.
        """

        input_file = self.context.construct_input_filename(code_name)
        input_extra_files = [self.context.construct_test_filename(code_name, ext) for ext in extra_output_exts]

        try:
            self.context.path.mkdir_logs()
            self.context.path.mkdir_testcases()
        except Exception as err:
            print("Could not create logs and testcases directory.")
            raise err

        try:
            # preprocess
            for command in commands:
                if command[0] == "manual":
                    command[0] = "/usr/bin/cat"
                    for i in range(1, len(command)):
                        command[i] = self.context.path.replace_with_manual(command[i])
                else:
                    command[0] = self.context.path.replace_with_generator(command[0])

            file_err_names = []

            sandbox_output_file = os.path.join(self.context.path.sandbox, input_file)
            Path(sandbox_output_file).touch()
            for filename in input_extra_files:
                (Path(self.context.path.sandbox) / filename).touch()

            generator_processes: list[Process] = []
            prev_proc = None

            pre_wait_procs()
            # Launch each command, chaining stdin/stdout
            try:
                for i, command in enumerate(commands, 1):

                    file_err_name = f"{code_name}.gen.err.{i}" if len(commands) > 1 else f"{code_name}.gen.err"
                    sandbox_output_err = os.path.join(self.context.path.sandbox, file_err_name)
                    file_err_names.append(file_err_name)

                    # For the first command, stdin is inherited (None)
                    stdin = prev_proc.stdout if prev_proc else None

                    # For the last command, stdout goes to the file; otherwise to a pipe
                    if i == len(commands):
                        stdout_redirect = sandbox_output_file
                    else:
                        stdout_redirect = None

                    proc = Process(command,
                                   preexec_fn=lambda: os.chdir(self.context.path.sandbox),
                                   stdin=stdin,
                                   stdout=subprocess.PIPE,
                                   stdout_redirect=stdout_redirect,
                                   stderr_redirect=sandbox_output_err,
                                   time_limit=self.limits.trusted_step_time_limit_sec,
                                   memory_limit=self.limits.trusted_step_memory_limit_mib)

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

            # Move tests
            shutil.move(os.path.join(self.context.path.sandbox, input_file),
                        os.path.join(self.context.path.testcases, input_file))
            # Move extra files
            for filename in input_extra_files:
                shutil.move(os.path.join(self.context.path.sandbox, filename),
                            os.path.join(self.context.path.testcases, filename))
            # Move logs
            for file_err_name in file_err_names:
                shutil.move(os.path.join(self.context.path.sandbox, file_err_name),
                            os.path.join(self.context.path.logs, file_err_name))

            for process in generator_processes:
                if process.is_timedout:
                    return ExecutionResult(ExecutionOutcome.TIMEDOUT,
                                           f"Generator command {commands} timed-out (time consumed: {process.wall_clock_time}).\n"
                                           "If this is expected, consider raising trusted step time limit.")
                if process.status != 0:
                    return ExecutionResult(ExecutionOutcome.CRASHED,
                                           f"Generator command {process.args} crashed (exit status: {process.status}).\n"
                                            "This could be out-of-memory crash, see trusted step memory limit for more information.")

        except FileNotFoundError as err:
            return ExecutionResult(ExecutionOutcome.CRASHED,
                                    f"File {err.filename} not found: {err.strerror}")

        return ExecutionResult(ExecutionOutcome.SUCCESS)
