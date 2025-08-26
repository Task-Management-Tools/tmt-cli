import os
import shutil
import subprocess
from pathlib import Path

from internal.context import TMTContext
from internal.compilation_makefile import compile_with_make
from internal.runner import Process, pre_wait_procs, wait_procs
from internal.outcome import CompilationResult, ExecutionResult, ExecutionOutcome


class GenerationStep:
    def __init__(self, context: 'TMTContext'):
        self.context = context
        self.limits = context.config  # for short hand reference
        self.workdir = self.context.path.sandbox_generation

    def compile(self) -> CompilationResult:
        return compile_with_make(makefile_path=self.context.path.makefile_normal,
                                 compiler=self.context.compiler,
                                 compile_flags=self.context.compile_flags,
                                 directory=self.context.path.generator,
                                 compile_time_limit_sec=self.limits.trusted_compile_time_limit_sec,
                                 compile_memory_limit_mib=self.limits.trusted_compile_memory_limit_mib,
                                 executable_stack_size_mib=self.limits.trusted_step_memory_limit_mib)

    def prepare_sandbox(self):
        os.makedirs(self.workdir, exist_ok=True)

    def run_generator(self, commands: list[list[str]], code_name: str, extra_output_exts: list[str]) -> ExecutionResult:
        """
        This function only raises Exception for internal errors.
        """
        # Unhandled: they are internal errors
        os.makedirs(self.context.path.logs_generation, exist_ok=True)
        os.makedirs(self.context.path.testcases, exist_ok=True)

        produce_files = ([self.context.construct_input_filename(code_name)] +
                         [self.context.construct_test_filename(code_name, ext) for ext in extra_output_exts])

        try:
            # Preprocess: replace generator and replace manual files
            for command in commands:
                if command[0] == "manual":
                    command[0] = "/usr/bin/cat"
                    for i in range(1, len(command)):
                        command[i] = self.context.path.replace_with_manual(command[i])
                else:
                    command[0] = self.context.path.replace_with_generator(command[0])

            sandbox_produce_files = []
            sandbox_logs = []

            for file in produce_files:
                sandbox_file = os.path.join(self.workdir, file)
                sandbox_produce_files.append(sandbox_file)
                Path(sandbox_file).touch()

            generator_processes: list[Process] = []
            prev_proc = None

            sigset = pre_wait_procs()
            # Launch each command, chaining stdin/stdout
            try:
                for i, command in enumerate(commands, 1):

                    sandbox_err_file = os.path.join(self.workdir,
                                                    f"{code_name}.gen.{i}.err" if len(commands) > 1 else
                                                    f"{code_name}.gen.err")
                    sandbox_logs.append(sandbox_err_file)

                    # For the first command, stdin is closed (None)
                    stdin = prev_proc.stdout if prev_proc else None

                    # For the last command, stdout goes to the file; otherwise to a pipe
                    if i == len(commands):
                        stdout_redirect = sandbox_produce_files[0]
                    else:
                        stdout_redirect = None

                    proc = Process(command,
                                   preexec_fn=lambda: os.chdir(self.workdir),
                                   stdin=stdin,
                                   stdout=subprocess.PIPE,
                                   stdout_redirect=stdout_redirect,
                                   stderr_redirect=sandbox_err_file,
                                   time_limit_sec=self.limits.trusted_step_time_limit_sec,
                                   memory_limit_mib=self.limits.trusted_step_memory_limit_mib)

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
            wait_procs(generator_processes, sigset)

            # Move tests & extra files

            for file in sandbox_produce_files:
                shutil.move(file, os.path.join(self.context.path.testcases, os.path.basename(file)))
            # Move logs
            for file in sandbox_logs:
                shutil.move(file, os.path.join(self.context.path.logs_generation, os.path.basename(file)))

            for process in generator_processes:
                if process.is_timedout:
                    for command in commands:
                        command[0] = os.path.basename(command[0])
                    full_command = " | ".join([' '.join(command) for command in commands])
                    return ExecutionResult(ExecutionOutcome.TIMEDOUT,
                                           f"Generator command `{full_command}' timed-out (time consumed: {process.wall_clock_time_sec:3f}).\n"
                                           "If this is expected, consider raising trusted step time limit.")
                if process.status != 0:
                    command = process.args
                    command[0] = os.path.basename(command[0])
                    if process.is_signaled_exit:
                        return ExecutionResult(ExecutionOutcome.CRASHED,
                                               f"Generator command `{' '.join(command)}' crashed (killed by signal {process.exit_signal}).\n"
                                               "This could be out-of-memory crash, see trusted step memory limit for more information.")
                    else:
                        return ExecutionResult(ExecutionOutcome.CRASHED,
                                               f"Generator command `{' '.join(command)}' crashed (exit status {process.exit_code}).\n"
                                               "This could be out-of-memory crash, see trusted step memory limit for more information.")

        except FileNotFoundError as err:
            return ExecutionResult(ExecutionOutcome.FAILED,
                                   f"File {err.filename} not found: {err.strerror}")

        return ExecutionResult(ExecutionOutcome.SUCCESS)
