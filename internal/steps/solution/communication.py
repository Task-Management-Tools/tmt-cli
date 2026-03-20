import os
import shutil

from pathlib import Path
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
from internal.steps.checker.cms import CMSCheckerStep
from internal.steps.utils import CompilationJob, CompilationSlot, requires_sandbox

from .batch import BatchSolutionStep


class CommunicationSolutionStep(BatchSolutionStep):
    """
    Implements Communication solution evaluation step based on CMS (contest management system).

    Requires executable "manager", accepts optional argument in config indicating whether the participant's program interacts via standatd I/O.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.sandbox:
            self.sandbox.manager.create()

        if not self.context.path.has_manager_directory():
            raise TMTMissingFileError(filetype="Directory", filename="manager")

        if self.context.config.manager is None:
            raise TMTInvalidConfigError(
                "Config section `manager` is not present in problems.yaml."
            )
        if self.context.config.manager.filename is None:
            raise TMTInvalidConfigError(
                "Config option `manager.filename` is not present in problems.yaml."
            )
        if self.context.config.checker is not None:
            raise TMTInvalidConfigError(
                "Config section `checker` should not be present in Communication tasks."
            )
        if self.context.config.solution.num_procs is None:
            raise TMTInvalidConfigError(
                "Config option `solution.num_procs` is not present in problems.yaml."
            )
        if self.context.config.solution.use_fifo is None:
            raise TMTInvalidConfigError(
                "Config option `solution.use_fifo` is not present in problems.yaml."
            )

        self.manager_name = self.context.config.manager.filename
        self.num_procs = self.context.config.solution.num_procs
        self.use_fifo = self.context.config.solution.use_fifo

    def clean_up(self):
        super().clean_up()
        make_clean(directory=self.context.path.manager)

    @requires_sandbox
    def compilation_jobs(self):
        yield CompilationJob(
            CompilationSlot.SOLUTION,
            self.compile_solution,
            ", ".join(os.path.basename(file) for file in self.submission_files),
        )
        yield CompilationJob(
            CompilationSlot.MANAGER, self.compile_manager, self.manager_name
        )

    @requires_sandbox
    def compile_manager(self) -> CompilationResult:
        # TODO maybe we want to check that the target is directly executable because it may cause problems in CMS
        comp_result = make_compile_target(
            context=self.context,
            directory=self.context.path.manager,
            sources=[self.context.config.manager.filename],
            target="manager",
            executable_stack_size_mib=self.context.config.trusted_step_memory_limit_mib,
        )

        if comp_result.verdict is CompilationOutcome.SUCCESS:
            if comp_result.produced_file is None:
                raise TMTMissingFileError(
                    filetype="manager (executable)",
                    filename=os.path.splitext(self.context.config.manager.filename)[0],
                )
        return comp_result

    @requires_sandbox
    def run_solution(self, code_name: str) -> EvaluationResult:
        """
        This function only returns FileNotFoundError for execution error.
        """
        self.sandbox.manager.clean()
        self.sandbox.solution_invocation.clean()

        input_filename = os.path.join(
            self.context.path.testcases,
            self.context.construct_input_filename(code_name),
        )
        # Unused for now
        # output_filename = os.path.join(
        #     self.context.path.testcases,
        #     self.context.construct_output_filename(code_name),
        # )

        manager_in_filename = self.sandbox.manager.file(f"{code_name}.manager.in")
        manager_out_filename = self.sandbox.manager.file(f"{code_name}.manager.out")
        manager_err_filename = self.sandbox.manager.file(f"{code_name}.manager.err")

        shutil.copy(input_filename, manager_in_filename)

        solution_err_filename = [
            self.sandbox.solution_invocation.file(f"{code_name}.sol.{i}.err")
            for i in range(self.num_procs)
        ]
        solution_m2s_fifo_filename = [
            self.sandbox.solution_invocation.file(f"mgr2sol.{i}.fifo")
            for i in range(self.num_procs)
        ]
        solution_s2m_fifo_filename = [
            self.sandbox.solution_invocation.file(f"sol2mgr.{i}.fifo")
            for i in range(self.num_procs)
        ]

        Path(manager_out_filename).touch()
        for fifo in solution_m2s_fifo_filename + solution_s2m_fifo_filename:
            os.mkfifo(fifo)

        # Find the way to run each process first:
        solution_sandbox_build_dir = self.sandbox.solution_compilation.subdir(
            "build"
        ).path
        solution_exec_command = get_run_single_command(
            context=self.context,
            directory=solution_sandbox_build_dir,
            executable_filename_base=self.executable_name_base,
            executable_stack_size_mib=self.memory_limit_mib,
        )
        assert solution_exec_command is not None

        manager_exec_command = get_run_single_command(
            context=self.context,
            directory=self.context.path.manager_build,
            executable_filename_base="manager",
            executable_stack_size_mib=self.context.config.trusted_step_memory_limit_mib,
        )
        assert manager_exec_command is not None

        # Define the pre-exec setups, then actually run:

        def solution_preexec_fn(i: int):
            def preexec_fn():
                os.chdir(self.sandbox.solution_invocation.path)
                if not self.use_fifo:
                    # This might never end if the manager is not cooperative...
                    # Manually redirect since it has to precisely match the CMS's behavior
                    stdin_redirect = os.open(solution_m2s_fifo_filename[i], os.O_RDONLY)
                    stdout_redirect = os.open(
                        solution_s2m_fifo_filename[i], os.O_WRONLY
                    )
                    os.dup2(stdin_redirect, 0)
                    os.close(stdin_redirect)
                    os.dup2(stdout_redirect, 1)
                    os.close(stdout_redirect)

            return preexec_fn

        def manager_preexec_fn():
            os.chdir(self.sandbox.manager.path)

        manager_exec_args: list[str] = []
        for i in range(self.num_procs):
            manager_exec_args.append(solution_s2m_fifo_filename[i])
            manager_exec_args.append(solution_m2s_fifo_filename[i])

        manager = Process(
            manager_exec_command + manager_exec_args,
            preexec_fn=manager_preexec_fn,
            stdin_redirect=manager_in_filename,
            stdout_redirect=manager_out_filename,
            stderr_redirect=manager_err_filename,
            time_limit_sec=max(
                # Add 3 because our implementation adds at most 2 second to wall clock limit
                (self.time_limit_sec + 3) * self.num_procs,
                self.context.config.trusted_step_time_limit_sec,
            ),
            memory_limit_mib=self.context.config.trusted_step_memory_limit_mib,
            output_limit_mib=self.context.config.trusted_step_output_limit_mib,
        )

        solutions: list[Process] = []
        for i in range(self.num_procs):
            solution_exec_args = []

            if self.use_fifo:
                solution_exec_args += [
                    solution_m2s_fifo_filename[i],
                    solution_s2m_fifo_filename[i],
                ]
            if self.num_procs > 1:
                solution_exec_args.append(str(i))

            solution = Process(
                solution_exec_command + solution_exec_args,
                preexec_fn=solution_preexec_fn(i),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr_redirect=solution_err_filename[i],
                time_limit_sec=self.time_limit_sec,
                memory_limit_mib=self.memory_limit_mib,
                output_limit_mib=self.output_limit_mib,
            )
            solution.stdin.close()
            solution.stdout.close()
            solutions.append(solution)

        wait_procs(solutions + [manager])

        # Save logs
        def copy_to_log(abs_path: str):
            Path(abs_path).touch()
            shutil.copy(abs_path, self.context.log_file(os.path.basename(abs_path)))

        copy_to_log(manager_out_filename)
        copy_to_log(manager_err_filename)
        for i in range(self.num_procs):
            copy_to_log(solution_err_filename[i])

        # Get verdict
        result = EvaluationResult(
            verdict=EvaluationOutcome.RUN_SUCCESS, output_file=manager_out_filename
        )
        for solution in solutions:
            result.fill_from_solution_process(solution)

        # First, we check if the manager crashed
        if manager.is_timedout:
            result.verdict = EvaluationOutcome.MANAGER_TIMEOUT
        elif manager.is_signaled_exit or manager.exit_code:
            result.verdict = EvaluationOutcome.MANAGER_CRASHED
        # else, we check if solution executed successfully
        elif self.is_solution_abormal_exit(result):
            pass
        # We read the standard manager output to determine the result:
        else:
            score, verdict, display, reason = CMSCheckerStep.parse_std_manager_output(
                manager_out_filename, manager_err_filename, False
            )

            result.score = score
            result.verdict = verdict
            result.override_verdict_display = display
            result.reason = result.reason or reason or ""

        return result
