import os
import shutil
import subprocess

from internal.compilation_makefile import compile_with_make, clean_with_make
from internal.context import TMTContext
from internal.runner import Process, wait_procs
from internal.outcome import CompilationResult, GenerationResult, ExecutionOutcome


class GenerationStep:
    def __init__(self, context: TMTContext):
        self.context = context
        self.limits = context.config  # for short hand reference
        self.workdir = self.context.path.sandbox_generation

    def compile(self) -> CompilationResult:
        comp_result = compile_with_make(
            makefile_path=self.context.path.makefile_normal,
            directory=self.context.path.generator,
            context=self.context,
            executable_stack_size_mib=self.limits.trusted_step_memory_limit_mib,
        )
        comp_result.dump_to_logs(self.context.path.logs_generation, "generator")
        return comp_result

    def prepare_sandbox(self):
        os.makedirs(self.workdir, exist_ok=True)

    def clean_up(self):
        clean_with_make(
            makefile_path=self.context.path.makefile_normal,
            directory=self.context.path.generator,
            context=self.context,
        )

    def run_generator(
        self, commands: list[list[str]], code_name: str, extra_output_exts: list[str]
    ) -> GenerationResult:
        """
        This function only raises Exception for internal errors.
        """
        # Unhandled: they are internal errors
        os.makedirs(self.context.path.logs_generation, exist_ok=True)
        os.makedirs(self.context.path.testcases, exist_ok=True)

        testcase_extra = [
            self.context.construct_test_filename(code_name, ext)
            for ext in extra_output_exts
        ]

        result = GenerationResult()
        generates_output = (
            False  # TODO: should be True when config answer_generation is generator.
        )
        try:
            # Filenames
            testcase_input = self.context.construct_input_filename(code_name)
            testcase_output = self.context.construct_output_filename(code_name)
            sandbox_testcase_input = os.path.join(
                self.context.path.sandbox_generation, testcase_input
            )
            sandbox_testcase_output = os.path.join(
                self.context.path.sandbox_generation, testcase_output
            )

            sandbox_testcase_extra = []
            sandbox_logs = []

            for file in testcase_extra:
                sandbox_file = os.path.join(self.workdir, file)
                sandbox_testcase_extra.append(sandbox_file)

            start_parsing_index = 0
            # Preprocess: replace manual
            if commands[0][0] == "manual":
                if len(commands[0]) == 2:
                    commands[0] = [
                        "cat",
                        self.context.path.replace_with_manual(commands[0][1]),
                    ]
                    start_parsing_index = 1
                elif len(commands[0]) == 3:
                    commands = [
                        [
                            "cp",
                            self.context.path.replace_with_manual(commands[0][2]),
                            sandbox_testcase_output,
                        ],
                        [
                            "cat",
                            self.context.path.replace_with_manual(commands[0][1]),
                        ],
                    ] + commands[1:]
                    start_parsing_index = 2
                    result.is_output_forced = True

            # Preprocess: replace manual files
            for command in commands[start_parsing_index:]:
                if not command[0].startswith(os.sep):
                    command[0] = self.context.path.replace_with_generator(command[0])

            # Launch each command, chaining stdin/stdout
            generator_processes: list[Process] = []
            prev_proc = None

            try:
                for i, command in enumerate(commands, 1):
                    sandbox_err_file = os.path.join(
                        self.workdir,
                        f"{code_name}.gen.{i}.err"
                        if len(commands) > 1
                        else f"{code_name}.gen.err",
                    )
                    sandbox_logs.append(sandbox_err_file)

                    # For the first command, stdin is closed (None)
                    stdin = None
                    if prev_proc is not None:
                        stdin = prev_proc.stdout

                    # For the last command, stdout goes to the file; otherwise to a pipe
                    stdout_redirect = (
                        sandbox_testcase_input if i == len(commands) else None
                    )

                    proc = Process(
                        command,
                        preexec_fn=lambda: os.chdir(self.workdir),
                        stdin=stdin,
                        stdout=subprocess.PIPE,
                        stdout_redirect=stdout_redirect,
                        stderr_redirect=sandbox_err_file,
                        time_limit_sec=self.limits.trusted_step_time_limit_sec,
                        memory_limit_mib=self.limits.trusted_step_memory_limit_mib,
                    )

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

            assert generator_processes[-1].stdout is not None
            generator_processes[-1].stdout.close()
            wait_procs(generator_processes)

            # Move testcase input
            shutil.move(
                sandbox_testcase_input,
                os.path.join(self.context.path.testcases, testcase_input),
            )
            # If testcase output was generated, use this output
            if os.path.exists(sandbox_testcase_output) and os.path.isfile(
                sandbox_testcase_output
            ):
                shutil.move(
                    sandbox_testcase_output,
                    os.path.join(self.context.path.testcases, testcase_output),
                )
                generates_output = True
                if sandbox_testcase_output in sandbox_testcase_extra:
                    sandbox_testcase_extra.remove(sandbox_testcase_output)

            # Move extra files
            for file in sandbox_testcase_extra:
                shutil.move(
                    file,
                    os.path.join(self.context.path.testcases, os.path.basename(file)),
                )

            # Move logs
            for file in sandbox_logs:
                shutil.move(
                    file,
                    os.path.join(
                        self.context.path.logs_generation, os.path.basename(file)
                    ),
                )

            # Check generation program status
            result.input_generation = ExecutionOutcome.SUCCESS

            for i, process in enumerate(generator_processes):
                if process.is_timedout:
                    result.input_generation = ExecutionOutcome.TIMEDOUT

                    for command in commands:
                        command[0] = os.path.basename(command[0])
                    full_command = " | ".join(
                        [" ".join(command) for command in commands]
                    )
                    result.reason = (
                        f"Generator command `{full_command}' timed-out (time consumed: {process.wall_clock_time_sec:3f}). "
                        "If this is expected, consider raising trusted step time limit."
                    )

                elif process.status != 0:
                    result.input_generation = ExecutionOutcome.CRASHED

                    command = commands[i]
                    command[0] = os.path.basename(command[0])

                    if process.is_signaled_exit:
                        result.reason = (
                            f"Generator command `{' '.join(command)}' crashed (killed by signal {process.exit_signal}). "
                            "This could be out-of-memory crash, see trusted step memory limit for more information."
                        )
                    else:
                        result.reason = (
                            f"Generator command `{' '.join(command)}' crashed (exit status {process.exit_code}). "
                            "This could be out-of-memory crash, see trusted step memory limit for more information."
                        )

        # If at any point some curcial file is missing, then the generation step must be wrong.
        except FileNotFoundError as err:
            result.input_generation = ExecutionOutcome.FAILED
            result.reason = f"File {err.filename} not found: {err.strerror}"

        if generates_output:
            result.output_generation = ExecutionOutcome.SKIPPED_SUCCESS
        return result
