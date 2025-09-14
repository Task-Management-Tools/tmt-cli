import os
import shutil
import signal
import subprocess
from pathlib import Path

from internal.context import TMTContext
from internal.runner import Process, wait_procs
from internal.compilation import (
    make_compile_targets,
    make_clean,
    compile_single,
    get_run_single_command,
)
from internal.outcome import (
    EvaluationOutcome,
    EvaluationResult,
    CompilationOutcome,
    CompilationResult,
)

from .base import SolutionStep


class InteractiveICPCSolutionStep(SolutionStep):
    """Implements ICPC interactive problem evaluation."""

    def __init__(
        self, *, context: TMTContext, is_generation: bool, submission_files: list[str]
    ):
        super().__init__(
            context=context,
            is_generation=is_generation,
            submission_files=submission_files,
        )

    @classmethod
    def has_interactor(cls):
        return True

    @classmethod
    def skip_checker(cls):
        return True

    def prepare_sandbox(self):
        os.makedirs(self.context.path.sandbox_solution, exist_ok=True)
        os.makedirs(self.context.path.sandbox_interactor, exist_ok=True)

    def clean_up(self):
        make_clean(directory=self.context.path.interactor)

    def compile_solution(self) -> CompilationResult:
        if len(self.submission_files) != 1:
            return CompilationResult(
                verdict=CompilationOutcome.FAILED,
                exit_status=-1,
                standard_error="ICPC-style interactive task only supports single file submission.",
            )

        self.context.path.empty_directory(self.context.path.sandbox_solution)
        comp_result = compile_single(
            context=self.context,
            directory=self.context.path.sandbox_solution,
            sources=self.submission_files,
            executable_filename_base=self.executable_name_base,
            executable_stack_size_mib=self.memory_limit_mib,
        )
        comp_result.dump_to_logs(self.log_directory, "solution")
        return comp_result

    def compile_interactor(self) -> CompilationResult:
        if self.context.path.has_interactor_directory():
            comp_result = make_compile_targets(
                context=self.context,
                directory=self.context.path.interactor,
                sources=[self.context.config.interactor_filename],
                target="interactor",
                executable_stack_size_mib=self.context.config.trusted_step_memory_limit_mib,
            )

            shutil.copy(
                comp_result.produced_file,
                self.context.path.sandbox_interactor,
            )

            comp_result.dump_to_logs(self.log_directory, "interactor")
            return comp_result
        return CompilationResult(
            CompilationOutcome.FAILED, "`interactor' directory not found."
        )

    def run_solution(self, code_name: str) -> EvaluationResult:
        """
        This function only returns FileNotFoundError for execution error.

        If store_output is specified, then we create an empty file as dummy output file.
        """
        os.makedirs(self.log_directory, exist_ok=True)

        file_in_name = self.context.construct_input_filename(code_name)
        file_out_name = self.context.construct_output_filename(code_name)
        file_sol_err_name = f"{code_name}.sol.err"
        file_interactor_err_name = f"{code_name}.interactor.err"

        testcase_input = os.path.join(self.context.path.testcases, file_in_name)
        testcase_answer = os.path.join(self.context.path.testcases, file_out_name)
        sandbox_interactor_input_file = os.path.join(
            self.context.path.sandbox_interactor, file_in_name
        )
        sandbox_interactor_answer_file = os.path.join(
            self.context.path.sandbox_interactor, file_out_name
        )
        sandbox_interactor_err_file = os.path.join(
            self.context.path.sandbox_interactor, file_interactor_err_name
        )
        sandbox_interactor_feedback_dir = (
            os.path.join(self.context.path.sandbox_interactor, "feedback_dir") + os.sep
        )
        sandbox_solution_err_file = os.path.join(
            self.context.path.sandbox_solution, file_sol_err_name
        )

        # Create dummy output
        if self.is_generation:
            with open(testcase_answer, "w+b"):
                pass  # Truncate the file

        shutil.copy(testcase_input, sandbox_interactor_input_file)
        shutil.copy(testcase_answer, sandbox_interactor_answer_file)

        if not os.path.isdir(sandbox_interactor_feedback_dir):
            os.mkdir(sandbox_interactor_feedback_dir)
        self.context.path.empty_directory(sandbox_interactor_feedback_dir)

        def solution_preexec_fn():
            os.chdir(self.context.path.sandbox_solution)
            signal.signal(signal.SIGPIPE, signal.SIG_IGN)

        solution_exec_command = get_run_single_command(
            context=self.context,
            directory=self.context.path.sandbox_solution,
            executable_filename_base=self.executable_name_base,
            executable_stack_size_mib=self.memory_limit_mib,
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
            os.chdir(self.context.path.sandbox_interactor)
            signal.signal(signal.SIGPIPE, signal.SIG_IGN)

        interactor_exec_command = get_run_single_command(
            context=self.context,
            directory=self.context.path.sandbox_interactor,
            executable_filename_base="interactor",
            executable_stack_size_mib=self.context.config.trusted_step_memory_limit_mib,
        )
        interactor_exec_args = [
            sandbox_interactor_input_file,
            sandbox_interactor_answer_file,
            sandbox_interactor_feedback_dir,
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
            sandbox_interactor_err_file,
            os.path.join(self.log_directory, file_interactor_err_name),
        )
        Path(sandbox_solution_err_file).touch()
        shutil.move(
            sandbox_solution_err_file,
            os.path.join(self.log_directory, file_sol_err_name),
        )

        interactor_feedback_logs = os.path.join(
            self.log_directory, f"{code_name}.interactor.feedback"
        )
        if os.path.isdir(interactor_feedback_logs):
            shutil.rmtree(interactor_feedback_logs)
        shutil.copytree(
            sandbox_interactor_feedback_dir,
            os.path.join(self.log_directory, f"{code_name}.interactor.feedback"),
        )

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
        elif self.is_solution_abormal_exit(solution, result):
            pass
        # Now, we can check if the solution is actually correct
        elif interactor.exit_code == 42:
            result.verdict = EvaluationOutcome.ACCEPTED
        else:
            result.verdict = EvaluationOutcome.WRONG

            # See ICPCCheckerStep.
            interactor_feedback_file = (
                Path(sandbox_interactor_feedback_dir) / "judgemessage.txt"
            )
            if interactor_feedback_file.is_file():
                with open(interactor_feedback_file, "r") as f:
                    result.checker_reason = f.readline().strip()

        shutil.rmtree(sandbox_interactor_feedback_dir)

        return result
