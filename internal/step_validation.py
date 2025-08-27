import os
import shutil
from pathlib import Path

from internal.compilation_makefile import compile_with_make
from internal.config import JudgeConvention
from internal.context import TMTContext
from internal.outcome import CompilationResult, GenerationResult, ExecutionOutcome
from internal.runner import Process, pre_wait_procs, wait_procs


class ValidationStep:
    def __init__(self, context: 'TMTContext'):
        self.context = context
        self.limits = context.config  # for short hand reference
        self.workdir = self.context.path.sandbox_validation

    def compile(self) -> CompilationResult:
        comp_result = compile_with_make(makefile_path=self.context.path.makefile_normal,
                                        directory=self.context.path.validator,
                                        context=self.context,
                                        executable_stack_size_mib=self.limits.trusted_step_memory_limit_mib)
        comp_result.dump_to_logs(self.context.path.logs_generation, "validator")
        return comp_result

    def prepare_sandbox(self):
        os.makedirs(self.workdir, exist_ok=True)

    def run_validator(self, result: GenerationResult, commands: list[list[str]], code_name: str, extra_input_exts: list[str]) -> None:
        """
        commands should contain all validators all at once (without piping the input file).
        extra_input_ext specifies a list of input extensions, which are the extra files generated through the generator stage.

        This function should not raise any error except for the internal logic failed.
        """
        # Prepare directories
        os.makedirs(self.context.path.logs_generation, exist_ok=True)
        os.makedirs(self.workdir, exist_ok=True)
        # There might be failed validation files lingering in the filesystem; remove them.
        self.context.path.empty_directory(self.workdir)

        input_filename = self.context.construct_input_filename(code_name)
        expected_exitcode = 42 if self.context.config.judge is JudgeConvention.ICPC else 0

        try:
            # Preprocess, could raise FileNotFound error in case validator does not exist
            for command in commands:
                command[0] = self.context.path.replace_with_validator(command[0])

            try:
                for i, command in enumerate(commands, 1):
                    # Prepare files
                    if len(commands) == 1:
                        output_filename = f"{code_name}.val.out"
                        error_filename = f"{code_name}.val.err"
                    else:
                        output_filename = f"{code_name}.val.{i}.out"
                        error_filename = f"{code_name}.val.{i}.err"

                    sandbox_input_file = os.path.join(self.workdir, input_filename)
                    sandbox_output_file = os.path.join(self.workdir, output_filename)
                    sandbox_error_file = os.path.join(self.workdir, error_filename)

                    # Copy input and extra inputs
                    shutil.copy(os.path.join(self.context.path.testcases, input_filename),
                                sandbox_input_file)
                    sandbox_extra_files = []
                    for ext in extra_input_exts:
                        extra_filename = self.context.construct_test_filename(code_name, ext)
                        sandbox_extra_file = os.path.join(self.workdir, extra_filename)
                        shutil.copy(os.path.join(self.context.path.testcases, extra_filename),
                                    sandbox_extra_file)
                        sandbox_extra_files.append(sandbox_extra_file)

                    # Run validator
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
                                os.path.join(self.context.path.logs_generation, output_filename))
                    shutil.move(sandbox_error_file,
                                os.path.join(self.context.path.logs_generation, error_filename))

                    # Check if validator succeed
                    if validator.is_timedout:
                        result.input_validation = ExecutionOutcome.TIMEDOUT
                        result.reason = (
                            f"Validator command {command} timed-out (time consumed: {validator.wall_clock_time_sec}). "
                            "If this is expected, consider raising trusted step time limit."
                        )
                        return result

                    elif validator.is_signaled_exit:
                        result.input_validation = ExecutionOutcome.CRASHED
                        result.reason = (
                            f"Validator command {command} aborted with signal (exit signal: {validator.exit_signal}). "
                            "This could be out-of-memory crash, see trusted step memory limit for more information."
                        )
                        return result

                    elif validator.exit_code != expected_exitcode:
                        result.input_validation = ExecutionOutcome.FAILED

                        command[0] = os.path.basename(command[0])

                        with open(os.path.join(self.context.path.logs_generation, error_filename), 'r') as f:
                            lines = f.readlines()
                            lastline = lines[-1].rstrip('\n') if lines else None

                        if lastline is None:
                            result.reason = (
                                f"Validation failed on validation command `{' '.join(command)}': "
                                f"expecting exitcode {expected_exitcode}"
                            )
                        else:
                            result.reason = lastline
                        return result

            except FileNotFoundError as exception:
                # We can simply raise, since there will be no processes left
                raise exception

            result.input_validation = ExecutionOutcome.SUCCESS
            return result
        
        except FileNotFoundError as err:
            result.input_validation = ExecutionOutcome.CRASHED
            result.reason = f"File {err.filename} not found: {err.strerror}"
            return result
