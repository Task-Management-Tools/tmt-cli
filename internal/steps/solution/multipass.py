import os
import shutil

from pathlib import Path
import signal

from internal.compilation.makefile import make_clean, make_compile_target
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

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.context.path.has_interactor_directory():
            raise TMTMissingFileError(filetype="Directory", filename="interactor")

        # Pre-condition ensured by config
        assert self.context.config.interactor is not None

        self.interactor_name = self.context.config.interactor.filename
        self.interactor_args = self.context.config.interactor.arguments

        assert self.context.config.solution.max_passes is not None
        self.max_passes = self.context.config.solution.max_passes

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
            sources=[self.interactor_name],
            target="interactor",
            executable_stack_size_mib=self.context.config.trusted_step_memory_limit_mib,
        )

        if comp_result.verdict is CompilationOutcome.SUCCESS:
            if comp_result.produced_file is None:
                raise TMTMissingFileError(
                    filetype="interactor (executable)",
                    filename=os.path.splitext(self.interactor_name)[0],
                )

        return comp_result

    def clean_up(self):
        super().clean_up()
        make_clean(directory=self.context.path.interactor)

    def is_solution_abormal_exit(
        self, eval_res: EvaluationResult, solution: Process
    ) -> bool:
        # Uses per-solution properties instead, need to be called after each solution run

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

        input_file_name = self.context.construct_input_filename(codename)
        output_file_name = self.context.construct_output_filename(codename)
        output_file_name_fmt = self.context.construct_output_filename(codename) + ".{0}"
        solution_err_name_fmt = f"{codename}.sol.err." + "{0}"
        interact_out_name_fmt = f"{codename}.interactor.out." + "{0}"
        interact_err_name_fmt = f"{codename}.interactor.err." + "{0}"

        testcase_input = os.path.join(self.context.path.testcases, input_file_name)
        testcase_answer = os.path.join(self.context.path.testcases, output_file_name)

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
        Path(testcase_answer).touch()
        interactor_feedback_dir = interact_workdir.subdir("feedback_dir")
        interactor_feedback_dir.create()
        interactor_feedback_dir.clean()

        next_input_source = testcase_input
        next_input_movable = False

        solution_runs: list[Process] = []
        interactor_runs: list[Process] = []
        agg_result = EvaluationResult(
            codename=codename, verdict=EvaluationOutcome.RUN_SUCCESS
        )

        def set_interactor_feedback():
            interactor_feedback_file = interactor_feedback_dir.file("judgemessage.txt")
            if os.path.isfile(interactor_feedback_file):
                with open(interactor_feedback_file, "r") as f:
                    agg_result.reason = f.readline().strip()

        for i in range(self.max_passes):
            # Run solution
            solution_out_name = output_file_name_fmt.format(i)
            solution_err_name = solution_err_name_fmt.format(i)

            sandbox_input_file = solution_workdir.file(input_file_name)
            sandbox_output_file = solution_workdir.file(solution_out_name)
            sandbox_error_file = solution_workdir.file(solution_err_name)

            solution_workdir.clean()
            if next_input_movable:
                shutil.move(next_input_source, sandbox_input_file)
            else:
                shutil.copy(next_input_source, sandbox_input_file)

            solution = Process(
                solution_exec_command,
                preexec_fn=lambda: os.chdir(solution_workdir.path),
                stdin_redirect=sandbox_input_file,
                stdout_redirect=sandbox_output_file,
                stderr_redirect=sandbox_error_file,
                time_limit_sec=self.time_limit_sec,
                memory_limit_mib=self.memory_limit_mib,
                output_limit_mib=self.output_limit_mib,
            )
            wait_procs([solution])
            solution_runs.append(solution)
            agg_result.fill_from_solution_process(solution)
            if self.is_solution_abormal_exit(agg_result, solution):
                break

            Path(sandbox_output_file).touch()
            shutil.copy(sandbox_output_file, self.context.log_file(solution_out_name))
            Path(sandbox_error_file).touch()
            shutil.move(sandbox_error_file, self.context.log_file(solution_err_name))

            # Run interactor
            interact_out_name = interact_out_name_fmt.format(i)
            interact_err_name = interact_err_name_fmt.format(i)
            # The name here is relative to the solution, not interactor
            interactor_testcase_input_file = interact_workdir.file(input_file_name)
            interactor_testcase_answer_file = interact_workdir.file(output_file_name)
            interactor_sol_input_file = interact_workdir.file(solution_out_name)
            interactor_output_file = interact_workdir.file(interact_out_name)
            interactor_error_file = interact_workdir.file(interact_err_name)

            # TODO if output limit exceeded?

            shutil.copy(testcase_input, interactor_testcase_input_file)
            shutil.copy(testcase_answer, interactor_testcase_answer_file)
            shutil.copy(sandbox_output_file, interactor_sol_input_file)
            interactor_next_input_path = interactor_feedback_dir.file("nextpass.in")
            if os.path.exists(interactor_next_input_path):
                os.unlink(interactor_next_input_path)
            # <output_validator_program> input_file answer_file feedback_dir [additional_arguments] < team_output
            interactor_required_args = [
                interactor_testcase_input_file,
                interactor_testcase_answer_file,
                interactor_feedback_dir.path + os.sep,  # required in ICPC format
            ]

            interactor = Process(
                interactor_exec_command
                + interactor_required_args
                + self.interactor_args,
                preexec_fn=lambda: os.chdir(interact_workdir.path),
                stdin_redirect=interactor_sol_input_file,
                stdout_redirect=interactor_output_file,
                stderr_redirect=interactor_error_file,
                time_limit_sec=config.trusted_step_time_limit_sec,
                memory_limit_mib=config.trusted_step_memory_limit_mib,
                output_limit_mib=config.trusted_step_output_limit_mib,
            )
            wait_procs([interactor])
            interactor_runs.append(interactor)

            interactor_output_file = interact_workdir.file(
                interact_out_name_fmt.format(i)
            )
            interactor_error_file = interact_workdir.file(
                interact_err_name_fmt.format(i)
            )
            Path(interactor_output_file).touch()
            shutil.copy(
                interactor_output_file, self.context.log_file(interact_out_name)
            )
            Path(interactor_error_file).touch()
            shutil.move(interactor_error_file, self.context.log_file(interact_err_name))

            if interactor.is_timedout:
                agg_result.verdict = EvaluationOutcome.CHECKER_TIMEDOUT
                break
            if interactor.is_signaled_exit:
                agg_result.verdict = EvaluationOutcome.CHECKER_CRASHED
                break

            has_next_input = os.path.exists(interactor_next_input_path)
            # Now, we can check if the solution is actually correct
            if interactor.exit_code != 42:
                if has_next_input:
                    agg_result.verdict = EvaluationOutcome.CHECKER_FAILED
                    agg_result.reason = (
                        "Interactor must not produce next input while exit code != 42"
                    )
                else:
                    agg_result.verdict = EvaluationOutcome.WRONG
                    set_interactor_feedback()
                break

            if has_next_input:
                next_input_source = interactor_next_input_path
                next_input_movable = True
            else:
                agg_result.verdict = EvaluationOutcome.ACCEPTED
                set_interactor_feedback()
                break
        else:
            # max number of pass exceeded
            agg_result.verdict = EvaluationOutcome.CHECKER_FAILED
            agg_result.reason = "Interactor must not produce next input when maximum pass number is reached"

        # Move logs
        interactor_feedback_logs = self.context.log_file(
            f"{codename}.interactor.feedback"
        )
        if os.path.isdir(interactor_feedback_logs):
            shutil.rmtree(interactor_feedback_logs)
        shutil.copytree(interactor_feedback_dir.path, interactor_feedback_logs)

        return agg_result
