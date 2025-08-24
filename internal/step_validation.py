import os
import shutil
from pathlib import Path

from internal.context import TMTContext
from internal.utils import make_file_extension
from internal.compilation_makefile import compile_with_make
from internal.outcome import CompilationResult, ExecutionResult, ExecutionOutcome
from internal.runner import Process, pre_wait_procs, wait_procs


class ValidationStep:
    def __init__(self, context: TMTContext):
        self.context = context
        self.limits = context.config # for short hand reference

    def compile(self) -> CompilationResult:
        return compile_with_make(directory=self.context.path.validator,
                                 makefile_path=self.context.path.makefile_normal,
                                 compile_time_limit_sec=self.limits.trusted_compile_time_limit_sec,
                                 compile_memory_limit_mib=self.limits.trusted_compile_memory_limit_mib,
                                 executable_stack_size_mib=self.limits.trusted_step_memory_limit_mib)

    def prepare_sandbox(self):
        self.context.path.mkdir_sandbox()

    def run_validator(self, commands: list[list[str]], code_name: str, extra_input_exts: list[str]) -> ExecutionResult:
        """
        commands should contain all validators all at once (without piping the input file).
        extra_input_ext specifies a list of input extensions, which are the extra files generated through the generator stage.

        This function should not raise any error except for the internal logic failed.
        """

        # TODO: handle FileNotFoundError and print actual meaningful error in the console.

        input_name = self.context.construct_input_filename(code_name)

        try:
            # preprocess, could raise FileNotFound error in case validator does not exist
            for command in commands:
                command[0] = self.context.path.replace_with_validator(command[0])

            # It is fine to use the same output file: we use O_TRUNC so the logs will be the last
            # validator stdout/stderr.
            file_out_name = f"{code_name}.val.out"
            file_err_name = f"{code_name}.val.err"
            sandbox_output_file = os.path.join(self.context.path.sandbox, file_out_name)
            sandbox_error_file = os.path.join(self.context.path.sandbox, file_err_name)
            Path(sandbox_output_file).touch()
            Path(sandbox_error_file).touch()

            valid = True
            failed_command = None
            try:
                for command in commands:
                    # Copy input and extra inputs
                    shutil.copy(os.path.join(self.context.path.testcases, input_name),
                                os.path.join(self.context.path.sandbox, input_name))
                    for ext in extra_input_exts:
                        filename = self.context.construct_test_filename(code_name, ext)
                        shutil.copy(os.path.join(self.context.path.testcases, filename),
                                    os.path.join(self.context.path.sandbox, filename))

                    pre_wait_procs()
                    validator = Process(command,
                                        preexec_fn=lambda: os.chdir(self.context.path.sandbox),
                                        stdin_redirect=os.path.join(self.context.path.sandbox, input_name),
                                        stdout_redirect=sandbox_output_file,
                                        stderr_redirect=sandbox_error_file,
                                        time_limit=self.limits.trusted_step_time_limit_sec,
                                        memory_limit=self.limits.trusted_step_memory_limit_mib)

                    wait_procs([validator])

                    # Clean up files
                    os.unlink(os.path.join(self.context.path.sandbox, input_name))
                    for ext in extra_input_exts:
                        filename = self.context.construct_test_filename(code_name, ext)
                        os.unlink(os.path.join(self.context.path.sandbox, filename))

                    if validator.is_timedout:
                        return ExecutionResult(ExecutionOutcome.TIMEDOUT,
                                               f"Validator command {command} timed-out (time consumed: {validator.wall_clock_time}).\n"
                                               "If this is expected, consider raising trusted step time limit.")
                    if validator.is_signaled_exit:
                        return ExecutionResult(ExecutionOutcome.CRASHED,
                                               f"Validator command {command} aborted with signal (exit signal: {validator.exit_signal}).\n"
                                               "This could be out-of-memory crash, see trusted step memory limit for more information.")

                    elif validator.status != 0:
                        valid = False
                        failed_command = command
                        break

            except FileNotFoundError as exception:
                # We can simply raise, since there will be no processes left
                raise exception

            self.context.path.mkdir_logs()

            try:
                # Move logs
                shutil.move(os.path.join(self.context.path.sandbox, file_out_name),
                            os.path.join(self.context.path.logs, file_out_name))
                shutil.move(os.path.join(self.context.path.sandbox, file_err_name),
                            os.path.join(self.context.path.logs, file_err_name))
            except FileNotFoundError as exception:
                raise exception

            if valid:
                return ExecutionResult(ExecutionOutcome.SUCCESS)
            else:
                return ExecutionResult(ExecutionOutcome.FAILED, f"Validation failed on validation command {failed_command}.")

        except FileNotFoundError as err:
            return ExecutionResult(ExecutionOutcome.CRASHED,
                                   f"File {err.filename} not found: {err.strerror}")
