import os
import shutil

from pathlib import Path
import signal

from internal.compilation.makefile import make_clean, make_compile_target
from internal.context.config.config import ProblemConfigMultipass
from internal.exceptions import TMTMissingFileError
from internal.process import Process, wait_procs
from internal.compilation import get_run_single_command
from internal.outcomes import (
    CompilationOutcome,
    CompilationResult,
    EvaluationOutcome,
    EvaluationResult,
)
from internal.steps.utils import CompilationJob, CompilationSlot, requires_sandbox

from .batch import BatchSolutionStep


class ICPCMultipassSolutionStep(BatchSolutionStep):
    """
    Implements ICPC-style multi-pass solution evaluation step.

    Requires executable "interactor".
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        if not self.context.path.has_interactor_directory():
            raise TMTMissingFileError(filetype="Directory", filename="interactor")

        assert isinstance(self.context.config, ProblemConfigMultipass)
        self.config: ProblemConfigMultipass = self.context.config

    @requires_sandbox
    def compilation_jobs(self):
        yield CompilationJob(
            CompilationSlot.SOLUTION,
            self.compile_solution,
            ", ".join(os.path.basename(file) for file in self.submission_files),
        )
        yield CompilationJob(
            CompilationSlot.INTERACTOR,
            self.compile_interactor,
            self.config.interactor.filename,
        )

    @requires_sandbox
    def compile_interactor(self) -> CompilationResult:
        interactor_filename = self.config.interactor.filename
        comp_result = make_compile_target(
            context=self.context,
            directory=self.context.path.interactor,
            sources=[interactor_filename],
            target="interactor",
            executable_stack_size_mib=self.config.trusted_step_memory_limit_mib,
        )

        if comp_result.verdict is CompilationOutcome.SUCCESS:
            if comp_result.produced_file is None:
                raise TMTMissingFileError(
                    filetype="interactor (executable)",
                    filename=os.path.splitext(interactor_filename)[0],
                )

        return comp_result

    def clean_up(self):
        super().clean_up()
        make_clean(directory=self.context.path.interactor)

    def is_solution_abnormal_exit(
        self, eval_res: EvaluationResult, solution: Process
    ) -> bool:
        """
        Determine whether the solution terminate normally.
        Used when each solution must be considered separately.
        Returns True if not, and fills respective EvaluationOutcome eval_res.

        Args:
            eval_res (EvaluationResult): The EvaluationResult to be filled.
            solution (Process): The relevant solution process result.
        """

        if solution.max_rss_kib > self.memory_limit_mib * 1024:
            eval_res.verdict = EvaluationOutcome.RUNERROR_MEMORY
        if solution.cpu_time_sec > self.time_limit_sec:
            eval_res.verdict = EvaluationOutcome.TIMEOUT
        elif solution.wall_clock_time_sec > self.time_limit_sec:
            eval_res.verdict = EvaluationOutcome.TIMEOUT_WALL
        elif solution.exit_signal == signal.SIGXFSZ:
            eval_res.verdict = EvaluationOutcome.RUNERROR_OUTPUT
        elif solution.exit_signal != 0:
            eval_res.verdict = EvaluationOutcome.RUNERROR_SIGNAL
            eval_res.reason = (
                f"Execution killed by signal ({signal.strsignal(solution.exit_signal)})"
            )
        elif solution.exit_code != 0:
            eval_res.verdict = EvaluationOutcome.RUNERROR_EXITCODE
            eval_res.reason = f"Execution exited with exit code {solution.exit_code}"
        else:
            return False
        return True

    @requires_sandbox
    def run_solution(self, codename: str) -> EvaluationResult:
        """
        This function only returns FileNotFoundError for execution error.
        """
        config = self.context.config

        assert self.sandbox is not None
        solution_workdir = self.sandbox.solution_invocation
        solution_workdir.create()
        interact_workdir = self.sandbox.interactor
        interact_workdir.create()
        interact_workdir.clean()

        fname_testcase_input = self.context.construct_input_filename(codename)
        fname_testcase_answer = self.context.construct_output_filename(codename)
        fname_sol_stdin_fmt = f"{codename}.sol.in.{{0}}"
        fname_sol_stdout_fmt = f"{codename}.sol.out.{{0}}"
        fname_sol_stderr_fmt = f"{codename}.sol.err.{{0}}"
        fname_interact_stdout_fmt = f"{codename}.interactor.out.{{0}}"
        fname_interact_stderr_fmt = f"{codename}.interactor.err.{{0}}"

        solution_exec_command = get_run_single_command(
            context=self.context,
            directory=self.sandbox.solution_compilation.subdir("build").path,
            executable_filename_base=self.executable_name_base,
            executable_stack_size_mib=self.memory_limit_mib,
        )
        assert solution_exec_command is not None
        interactor_exec_command = get_run_single_command(
            context=self.context,
            directory=self.context.path.interactor_build,
            executable_filename_base="interactor",
            executable_stack_size_mib=config.trusted_step_memory_limit_mib,
        )
        assert interactor_exec_command is not None

        # Create dummy answer if it doesn't exist
        f_testcase_input = os.path.join(
            self.context.path.testcases, fname_testcase_input
        )
        f_testcase_answer = os.path.join(
            self.context.path.testcases, fname_testcase_answer
        )
        Path(f_testcase_answer).touch()
        dir_interactor_feedback = interact_workdir.subdir("feedback_dir")
        dir_interactor_feedback.create()
        dir_interactor_feedback.clean()

        def get_interactor_feedback() -> str:
            interactor_feedback_file = dir_interactor_feedback.file("judgemessage.txt")
            if os.path.isfile(interactor_feedback_file):
                with open(interactor_feedback_file, "r") as f:
                    return f.readline().strip()
            return ""

        def remove(src: str):
            if (p := Path(src)).exists():
                p.unlink()

        def copy_to_log(src: str, dst: str | None = None):
            Path(src).touch()
            shutil.copy(src, self.context.log_file(dst or Path(src).name))

        def move_to_log(src: str):
            Path(src).touch()
            shutil.move(src, self.context.log_file(Path(src).name))

        max_passes = self.config.solution.execution.max_passes
        f_next_input = f_testcase_input
        agg_result = EvaluationResult(
            codename=codename, verdict=EvaluationOutcome.RUN_SUCCESS
        )
        for i in range(max_passes):
            # Run solution
            fname_sol_stdin = fname_sol_stdin_fmt.format(i)
            fname_sol_stdout = fname_sol_stdout_fmt.format(i)
            fname_sol_stderr = fname_sol_stderr_fmt.format(i)

            f_sol_stdin = solution_workdir.file(fname_sol_stdin)
            f_sol_stdout = solution_workdir.file(fname_sol_stdout)
            f_sol_stderr = solution_workdir.file(fname_sol_stderr)

            solution_workdir.clean()
            shutil.copy(f_next_input, f_sol_stdin)

            solution = Process(
                solution_exec_command,
                preexec_fn=lambda: os.chdir(solution_workdir.path),
                stdin_redirect=f_sol_stdin,
                stdout_redirect=f_sol_stdout,
                stderr_redirect=f_sol_stderr,
                time_limit_sec=self.time_limit_sec,
                memory_limit_mib=self.memory_limit_mib,
                output_limit_mib=self.output_limit_mib,
            )
            wait_procs([solution])
            agg_result.fill_from_solution_process(solution)
            if self.is_solution_abnormal_exit(agg_result, solution):
                break

            copy_to_log(f_sol_stdout)
            move_to_log(f_sol_stderr)
            del f_sol_stderr

            # Run interactor
            fname_interact_stdout = fname_interact_stdout_fmt.format(i)
            fname_interact_stderr = fname_interact_stderr_fmt.format(i)
            f_interact_testcase_input = interact_workdir.file(fname_testcase_input)
            f_interact_testcase_answer = interact_workdir.file(fname_testcase_answer)
            shutil.copy(f_testcase_input, f_interact_testcase_input)
            shutil.copy(f_testcase_answer, f_interact_testcase_answer)
            f_interact_stdout = interact_workdir.file(fname_interact_stdout)
            f_interact_stderr = interact_workdir.file(fname_interact_stderr)
            f_interact_nextpass = dir_interactor_feedback.file("nextpass.in")

            # <output_validator_program> input_file answer_file feedback_dir [additional_arguments] < team_output
            interactor_required_args = [
                f_interact_testcase_input,
                f_interact_testcase_answer,
                dir_interactor_feedback.path + os.sep,  # required in ICPC format
            ]
            interactor = Process(
                interactor_exec_command
                + interactor_required_args
                + self.config.interactor.arguments,
                preexec_fn=lambda: os.chdir(interact_workdir.path),
                stdin_redirect=f_sol_stdout,
                stdout_redirect=f_interact_stdout,
                stderr_redirect=f_interact_stderr,
                time_limit_sec=config.trusted_step_time_limit_sec,
                memory_limit_mib=config.trusted_step_memory_limit_mib,
                output_limit_mib=config.trusted_step_output_limit_mib,
            )
            wait_procs([interactor])

            remove(f_sol_stdout)
            remove(f_interact_testcase_answer)
            move_to_log(f_interact_stdout)
            move_to_log(f_interact_stderr)

            if interactor.is_timedout:
                agg_result.verdict = EvaluationOutcome.CHECKER_TIMEDOUT
                break
            if interactor.is_signaled_exit:
                agg_result.verdict = EvaluationOutcome.CHECKER_CRASHED
                break

            has_next_input = os.path.exists(f_interact_nextpass)
            # Now, we can check if the solution is actually correct
            if interactor.exit_code != 42:
                if has_next_input:
                    agg_result.verdict = EvaluationOutcome.CHECKER_FAILED
                    agg_result.reason = (
                        "Interactor must not produce next input while exit code != 42"
                    )
                else:
                    agg_result.verdict = EvaluationOutcome.WRONG
                    agg_result.reason = get_interactor_feedback()
                break

            if has_next_input:
                # Move out of the feedbackdir
                f_next_input = interact_workdir.file(fname_sol_stdin_fmt.format(i + 1))
                shutil.move(f_interact_nextpass, f_next_input)
                copy_to_log(f_next_input)
            else:
                agg_result.verdict = EvaluationOutcome.ACCEPTED
                agg_result.score = 1.0
                agg_result.reason = get_interactor_feedback()
                break
        else:
            # max number of pass exceeded
            agg_result.verdict = EvaluationOutcome.CHECKER_FAILED
            agg_result.reason = "Interactor must not produce next input when maximum pass number is reached"

        # Move summary logs
        interactor_feedback_logs = self.context.log_file(
            f"{codename}.interactor.feedback"
        )
        if os.path.isdir(interactor_feedback_logs):
            shutil.rmtree(interactor_feedback_logs)
        shutil.copytree(dir_interactor_feedback.path, interactor_feedback_logs)

        return agg_result
