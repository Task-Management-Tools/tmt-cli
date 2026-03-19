import os
import shutil

from pathlib import Path
import signal
import subprocess

from internal.compilation.makefile import make_clean, make_compile_target
from internal.exceptions import TMTInvalidConfigError, TMTMissingFileError
from internal.process import Process, wait_procs
from internal.compilation import get_run_single_command
from internal.outcomes import (
    EvaluationOutcome,
    EvaluationResult,
    CompilationOutcome,
    CompilationResult,
)
from internal.steps.utils import CompilationJob, CompilationSlot, requires_sandbox

from .batch import BatchSolutionStep


class ICPCInteractiveSolutionStep(BatchSolutionStep):
    """
    Implements ICPC-style interactive solution evaluation step.

    Requires executable "interactor".
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.sandbox:
            self.workdir = self.sandbox.interactor
            self.workdir.create()
        if not self.context.path.has_interactor_directory():
            raise TMTMissingFileError(filetype="Directory", filename="interactor")
        if self.context.config.interactor is None:
            raise TMTInvalidConfigError(
                "Config section `interactor` is not present in problems.yaml."
            )
        if self.context.config.interactor.filename is None:
            raise TMTInvalidConfigError(
                "Config option `interactor.filename` is not present in problems.yaml."
            )
        self.interactor_name = self.context.config.interactor.filename

    def clean_up(self):
        super().clean_up()
        make_clean(directory=self.context.path.interactor)

    @requires_sandbox
    def compilation_jobs(self):
        yield CompilationJob(
            CompilationSlot.SOLUTION,
            self.compile_solution,
            ", ".join(os.path.basename(file) for file in self.submission_files),
        )
        yield CompilationJob(
            CompilationSlot.INTERACTOR, self.compile_interactor, self.interactor_name
        )

    @requires_sandbox
    def compile_interactor(self) -> CompilationResult:
        comp_result = make_compile_target(
            context=self.context,
            directory=self.context.path.interactor,
            sources=[self.context.config.interactor.filename],
            target="interactor",
            executable_stack_size_mib=self.context.config.trusted_step_memory_limit_mib,
        )

        if comp_result.verdict is CompilationOutcome.SUCCESS:
            if comp_result.produced_file is None:
                raise TMTMissingFileError(
                    filetype="interactor (executable)",
                    filename=os.path.splitext(self.context.config.interactor.filename)[
                        0
                    ],
                )

        return comp_result

    @requires_sandbox
    def run_solution(self, code_name: str) -> EvaluationResult:
        """
        This function only returns FileNotFoundError for execution error.
        """
        self.workdir.clean()

        file_in_name = self.context.construct_input_filename(code_name)
        file_out_name = self.context.construct_output_filename(code_name)
        file_sol_err_name = f"{code_name}.sol.err"
        file_interactor_err_name = f"{code_name}.interactor.err"

        testcase_input = os.path.join(self.context.path.testcases, file_in_name)
        testcase_answer = os.path.join(self.context.path.testcases, file_out_name)
        sandbox_interactor_input_file = self.workdir.file(file_in_name)
        sandbox_interactor_answer_file = self.workdir.file(file_out_name)
        sandbox_interactor_err_file = self.workdir.file(file_interactor_err_name)
        sandbox_interactor_feedback_dir = self.workdir.subdir("feedback_dir")
        sandbox_solution_err_file = self.sandbox.solution_invocation.file(
            file_sol_err_name
        )

        # Create dummy output
        if self.is_generation:
            with open(testcase_answer, "w+b"):
                pass  # Truncate the file

        shutil.copy(testcase_input, sandbox_interactor_input_file)
        shutil.copy(testcase_answer, sandbox_interactor_answer_file)

        sandbox_interactor_feedback_dir.create()

        def solution_preexec_fn():
            os.chdir(self.sandbox.solution_invocation.path)
            signal.signal(signal.SIGPIPE, signal.SIG_IGN)

        solution_sandbox_build_dir = self.sandbox.solution_compilation.subdir(
            "build"
        ).path
        solution_exec_command = get_run_single_command(
            context=self.context,
            directory=solution_sandbox_build_dir,
            executable_filename_base=self.executable_name_base,
            executable_stack_size_mib=self.memory_limit_mib,
        )
        if solution_exec_command is None:
            raise TMTMissingFileError(
                filetype="solution (executable)",
                filename=self.executable_name_base,
                among_str=solution_sandbox_build_dir,
            )
        solution = Process(
            solution_exec_command,
            preexec_fn=solution_preexec_fn,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr_redirect=sandbox_solution_err_file,
            time_limit_sec=self.time_limit_sec,
            memory_limit_mib=self.memory_limit_mib,
            output_limit_mib=self.output_limit_mib,
        )

        def interactor_preexec_fn():
            os.chdir(self.workdir.path)
            signal.signal(signal.SIGPIPE, signal.SIG_IGN)

        interactor_exec_command = get_run_single_command(
            context=self.context,
            directory=self.context.path.interactor_build,
            executable_filename_base="interactor",
            executable_stack_size_mib=self.context.config.trusted_step_memory_limit_mib,
        )
        assert interactor_exec_command is not None
        interactor_exec_args = [
            sandbox_interactor_input_file,
            sandbox_interactor_answer_file,
            sandbox_interactor_feedback_dir.path + os.sep,  # required in ICPC format
        ]
        interactor = Process(
            interactor_exec_command + interactor_exec_args,
            preexec_fn=interactor_preexec_fn,
            stdin=solution.stdout,
            stdout=solution.stdin,
            stderr_redirect=sandbox_interactor_err_file,
            time_limit_sec=max(
                self.time_limit_sec * 2,
                self.context.config.trusted_step_time_limit_sec,
            )
            + 1,
            memory_limit_mib=self.context.config.trusted_step_memory_limit_mib,
            output_limit_mib=self.context.config.trusted_step_output_limit_mib,
        )

        assert solution.stdin is not None and solution.stdout is not None
        solution.stdin.close()
        solution.stdout.close()

        wait_procs([solution, interactor])

        if Path(sandbox_interactor_input_file).exists():
            os.unlink(sandbox_interactor_input_file)
        if Path(sandbox_interactor_answer_file).exists():
            os.unlink(sandbox_interactor_answer_file)

        # Move logs
        Path(sandbox_interactor_err_file).touch()
        shutil.move(
            sandbox_interactor_err_file, self.context.log_file(file_interactor_err_name)
        )
        Path(sandbox_solution_err_file).touch()
        shutil.move(sandbox_solution_err_file, self.context.log_file(file_sol_err_name))

        interactor_feedback_logs = self.context.log_file(
            f"{code_name}.interactor.feedback"
        )
        if os.path.isdir(interactor_feedback_logs):
            shutil.rmtree(interactor_feedback_logs)
        shutil.copytree(sandbox_interactor_feedback_dir.path, interactor_feedback_logs)

        result = EvaluationResult(
            verdict=EvaluationOutcome.RUN_SUCCESS, output_file=None
        )
        result.fill_from_solution_process(solution)

        # First, we check if the interactor crashed
        if interactor.is_timedout:
            result.verdict = EvaluationOutcome.CHECKER_TIMEDOUT
        elif interactor.is_signaled_exit:
            result.verdict = EvaluationOutcome.CHECKER_CRASHED
        # else, we check if solution executed successfully
        elif self.is_solution_abormal_exit(result):
            pass
        # Now, we can check if the solution is actually correct
        elif interactor.exit_code == 42:
            result.verdict = EvaluationOutcome.ACCEPTED
        else:
            result.verdict = EvaluationOutcome.WRONG

            # See ICPCCheckerStep.
            interactor_feedback_file = (
                Path(sandbox_interactor_feedback_dir.path) / "judgemessage.txt"
            )
            if interactor_feedback_file.is_file():
                with open(interactor_feedback_file, "r") as f:
                    result.reason = f.readline().strip()

        return result
