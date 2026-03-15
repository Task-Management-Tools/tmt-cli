import signal
from abc import ABC, abstractmethod
from typing import Generator

from internal.context import TMTContext, SandboxDirectory
from internal.outcomes import (
    EvaluationResult,
    EvaluationOutcome,
)
from internal.steps.utils import CompilationJob


class SolutionStep(ABC):
    def __init__(
        self,
        *,
        context: TMTContext,
        sandbox: SandboxDirectory | None,
        is_generation: bool,
        submission_files: list[str],
    ):
        self.context = context
        self.sandbox = sandbox
        if self.sandbox:
            self.sandbox.solution_compilation.create()
            self.sandbox.solution_invocation.create()

        self.executable_name_base = self.context.config.short_name
        # TODO: if is_generation, moves the output (and remove save_output in run_solution method)
        if is_generation:
            self.time_limit_sec = self.context.config.trusted_step_time_limit_sec
            self.memory_limit_mib = self.context.config.trusted_step_memory_limit_mib
            self.output_limit_mib = self.context.config.trusted_step_output_limit_mib
            self.is_generation = True
            self.log_directory = context.path.logs_generation
        else:
            self.time_limit_sec = self.context.config.solution.time_limit_sec
            self.memory_limit_mib = self.context.config.solution.memory_limit_mib
            self.output_limit_mib = self.context.config.solution.output_limit_mib
            self.is_generation = False
            self.log_directory = context.path.logs_invocation

        self.submission_files = submission_files
        self.grader = context.config.solution.grader_name

    @abstractmethod
    def compilation_jobs(self) -> Generator[CompilationJob, None, None]:
        """
        Returns a list of compilation jobs to run to prepare for the judging process.
        """
        raise NotImplementedError

    @abstractmethod
    def clean_up(self):
        pass

    @abstractmethod
    def run_solution(self, code_name: str) -> EvaluationResult:
        """
        Runs solution for input file code_name.
        If is_generation is True, then stores the output to testcase.
        Otherwise, keep the output in the sandbox and report the file in EvaluationResult.
        """
        raise NotImplementedError

    def is_solution_abormal_exit(self, eval_res: EvaluationResult) -> bool:
        """
        Determine whether the solution didn't terminate normally.
        Returns True if not, and fills respective EvaluationOutcome eval_res.

        Args:
            eval_res (EvaluationResult): The EvaluationResult to be filled.
        """

        if eval_res.max_memory_kib > self.memory_limit_mib * 1024:
            eval_res.verdict = EvaluationOutcome.RUNERROR_MEMORY
        if eval_res.cpu_time_sec > self.time_limit_sec:
            eval_res.verdict = EvaluationOutcome.TIMEOUT
        elif eval_res.wall_clock_time_sec > self.time_limit_sec:
            eval_res.verdict = EvaluationOutcome.TIMEOUT_WALL
        elif eval_res.exit_signal == signal.SIGXFSZ:
            eval_res.verdict = EvaluationOutcome.OUTPUT_LIMIT
        elif eval_res.exit_signal == signal.SIGXCPU:  # this can happen
            eval_res.verdict = EvaluationOutcome.TIMEOUT
        elif eval_res.exit_signal != 0:
            eval_res.verdict = EvaluationOutcome.RUNERROR_SIGNAL
            eval_res.reason = (
                f"Execution killed by signal ({signal.strsignal(eval_res.exit_signal)})"
            )
        elif eval_res.exit_code != 0:
            eval_res.verdict = EvaluationOutcome.RUNERROR_EXITCODE
            eval_res.reason = f"Execution exited with exit code {eval_res.exit_code}"
        else:
            return False
        return True
