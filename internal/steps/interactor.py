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
from internal.steps.solution import SolutionStep
from internal.outcome import (
    EvaluationOutcome,
    EvaluationResult,
    CompilationOutcome,
    CompilationResult,
)


class InteractorStep:
    """Implements ICPC interactor compilation and execution."""

    def __init__(self, *, context: TMTContext):
        self.context = context

    def prepare_sandbox(self) -> None:
        os.makedirs(self.context.path.sandbox_interactor, exist_ok=True)

    def clean_up(self):
        make_clean(directory=self.context.path.interactor)

    def compile(self) -> CompilationResult:
        if self.context.path.has_interactor_directory():
            comp_result = make_compile_targets(
                context=self.context,
                directory=self.context.path.interactor,
                sources=[self.context.config.interactor.filename],
                target="interactor",
                executable_stack_size_mib=self.context.config.trusted_step_memory_limit_mib,
            )

            shutil.copy(
                comp_result.produced_file,
                self.context.path.sandbox_interactor,
            )

            return comp_result
        return CompilationResult(
            CompilationOutcome.FAILED, "`interactor' directory not found."
        )

    def run_solution(
        self,
        solution_step: SolutionStep,
        code_name: str,
    ) -> EvaluationResult:
        # TODO use solution_step.xxx instead of self.context.config.soution xxx
        """
        This function only returns FileNotFoundError for execution error.
        """
        os.makedirs(solution_step.log_directory, exist_ok=True)

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
        if solution_step.is_generation:
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
            executable_filename_base=solution_step.executable_name_base,
            executable_stack_size_mib=solution_step.memory_limit_mib,
        )
        solution = Process(
            solution_exec_command,
            preexec_fn=solution_preexec_fn,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr_redirect=sandbox_solution_err_file,
            time_limit_sec=solution_step.time_limit_sec,
            memory_limit_mib=solution_step.memory_limit_mib,
            output_limit_mib=solution_step.output_limit_mib,
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
                solution_step.time_limit_sec * 2,
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
            os.path.join(solution_step.log_directory, file_interactor_err_name),
        )
        Path(sandbox_solution_err_file).touch()
        shutil.move(
            sandbox_solution_err_file,
            os.path.join(solution_step.log_directory, file_sol_err_name),
        )

        interactor_feedback_logs = os.path.join(
            solution_step.log_directory, f"{code_name}.interactor.feedback"
        )
        if os.path.isdir(interactor_feedback_logs):
            shutil.rmtree(interactor_feedback_logs)
        shutil.copytree(
            sandbox_interactor_feedback_dir,
            os.path.join(
                solution_step.log_directory, f"{code_name}.interactor.feedback"
            ),
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
        elif solution_step.is_solution_abormal_exit(solution, result):
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
