import os
import shutil
from pathlib import Path

from internal.context import JudgeConvention, TMTContext
from internal.compilation_makefile import compile_with_make
from internal.outcome import CompilationResult, ExecutionResult, ExecutionOutcome
from internal.runner import Process, pre_wait_procs, wait_procs


class ValidationStep:
    def __init__(self, context: TMTContext):
        self.context = context
        self.limits = context.config  # for short hand reference
        self.workdir = self.context.path.sandbox_validation

    def compile(self) -> CompilationResult:
        return compile_with_make(directory=self.context.path.validator,
                                 compiler=self.context.compiler,
                                 compile_flags=self.context.compile_flags,
                                 makefile_path=self.context.path.makefile_normal,
                                 compile_time_limit_sec=self.limits.trusted_compile_time_limit_sec,
                                 compile_memory_limit_mib=self.limits.trusted_compile_memory_limit_mib,
                                 executable_stack_size_mib=self.limits.trusted_step_memory_limit_mib)

    def prepare_sandbox(self):
        os.makedirs(self.workdir, exist_ok=True)

    def run_validator(self, commands: list[list[str]], code_name: str, extra_input_exts: list[str]) -> ExecutionResult:
        """
        commands should contain all validators all at once (without piping the input file).
        extra_input_ext specifies a list of input extensions, which are the extra files generated through the generator stage.

        This function should not raise any error except for the internal logic failed.
        """
        os.makedirs(self.context.path.logs_generation, exist_ok=True)
        # There might be failed validation files lingering in the filesystem; remove them.
        self.context.path.empty_directory(self.workdir)

        input_filename = self.context.construct_input_filename(code_name)
        expected_exitcode = 42 if self.context.config.judge is JudgeConvention.ICPC else 0
        
        try:
            # Preprocess, could raise FileNotFound error in case validator does not exist
            for command in commands:
                command[0] = self.context.path.replace_with_validator(command[0])

            valid = True
            failed_command = None
            try:
                for i, command in enumerate(commands, 1):
                    if len(commands) == 1:
                        file_out_name = f"{code_name}.val.out"
                        file_err_name = f"{code_name}.val.err"
                    else:
                        file_out_name = f"{code_name}.val.{i}.out"
                        file_err_name = f"{code_name}.val.{i}.err"

                    sandbox_output_file = os.path.join(self.workdir, file_out_name)
                    sandbox_error_file = os.path.join(self.workdir, file_err_name)

                    # Copy input and extra inputs
                    sandbox_input_file = os.path.join(self.workdir, input_filename)
                    shutil.copy(os.path.join(self.context.path.testcases, input_filename),
                                sandbox_input_file)
                    sandbox_extra_files = []
                    for ext in extra_input_exts:
                        extra_filename = self.context.construct_test_filename(code_name, ext)
                        sandbox_extra_file = os.path.join(self.workdir, extra_filename)
                        shutil.copy(os.path.join(self.context.path.testcases, extra_filename),
                                    sandbox_extra_file)
                        sandbox_extra_files.append(sandbox_extra_file)

                    sigset = pre_wait_procs()
                    validator = Process(command,
                                        preexec_fn=lambda: os.chdir(self.workdir),
                                        stdin_redirect=sandbox_input_file,
                                        stdout_redirect=sandbox_output_file,
                                        stderr_redirect=sandbox_error_file,
                                        time_limit_sec=self.limits.trusted_step_time_limit_sec,
                                        memory_limit_mib=self.limits.trusted_step_memory_limit_mib)

                    wait_procs([validator], sigset)

                    # Clean up input and extra files
                    for file in [sandbox_input_file] + sandbox_extra_files:
                        if os.path.exists(file):
                            os.unlink(file)

                    # Touch both output and error, in case they are removed
                    Path(sandbox_output_file).touch()
                    Path(sandbox_error_file).touch()
                    shutil.move(sandbox_output_file,
                                os.path.join(self.context.path.logs_generation, file_out_name))
                    shutil.move(sandbox_error_file,
                                os.path.join(self.context.path.logs_generation, file_err_name))

                    if validator.is_timedout:
                        return ExecutionResult(ExecutionOutcome.TIMEDOUT,
                                               f"Validator command {command} timed-out (time consumed: {validator.wall_clock_time_sec}).\n"
                                               "If this is expected, consider raising trusted step time limit.")
                    if validator.is_signaled_exit:
                        return ExecutionResult(ExecutionOutcome.CRASHED,
                                               f"Validator command {command} aborted with signal (exit signal: {validator.exit_signal}).\n"
                                               "This could be out-of-memory crash, see trusted step memory limit for more information.")

                    elif validator.exit_code != expected_exitcode:
                        valid = False
                        failed_command = command
                        break

            except FileNotFoundError as exception:
                # We can simply raise, since there will be no processes left
                raise exception

            if valid:
                return ExecutionResult(ExecutionOutcome.SUCCESS)
            else:
                failed_command[0] = os.path.basename(failed_command[0])
                with open(os.path.join(self.context.path.logs, file_err_name), 'r') as f:
                    lines = f.readlines()
                    lastline = lines[-1].rstrip('\n') if lines else None
                if lastline is None:
                    return ExecutionResult(ExecutionOutcome.FAILED, f"Validation failed on validation command `{' '.join(failed_command)}'."
                                           f" (expecting exitcode {expected_exitcode})")
                else:
                    return ExecutionResult(ExecutionOutcome.FAILED, lastline)

        except FileNotFoundError as err:
            return ExecutionResult(ExecutionOutcome.CRASHED,
                                   f"File {err.filename} not found: {err.strerror}")
