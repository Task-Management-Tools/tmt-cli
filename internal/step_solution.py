import signal

from abc import ABCMeta, abstractmethod

from internal.outcome import EvaluationResult, EvaluationOutcome, CompilationResult
from internal.runner import Process

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from internal.context import TMTContext


class MetaSolutionStep(metaclass=ABCMeta):
    def __init__(self, *,  context: 'TMTContext', is_generation: bool, submission_files: list[str]):
        self.context = context

        self.executable_name = self.context.config.short_name
        # TODO: if is_generation, moves the output (and remove save_output in run_solution method)
        if is_generation:
            self.time_limit_sec = self.context.config.trusted_step_time_limit_sec
            self.memory_limit_mib = self.context.config.trusted_step_memory_limit_mib
            self.output_limit_mib = self.context.config.trusted_step_output_limit_mib
            self.is_generation = True
            self.log_directory = context.path.logs_generation
        else:
            self.time_limit_sec = self.context.config.time_limit_sec
            self.memory_limit_mib = self.context.config.memory_limit_mib
            self.output_limit_mib = self.context.config.output_limit_mib
            self.is_generation = False
            self.log_directory = context.path.logs_invocation

        self.submission_files = submission_files
        self.grader = None  # TODO: infer from config file (context)

    @classmethod
    def has_interactor(cls):
        return False

    @classmethod
    def has_manager(cls):
        return False

    @classmethod
    def skip_checker(cls):
        return False

    @abstractmethod
    def prepare_sandbox(self):
        pass

    @abstractmethod
    def compile_solution(self) -> CompilationResult:
        pass

    def compile_interactor(self) -> CompilationResult:
        pass

    def compile_manager(self) -> CompilationResult:
        pass

    @abstractmethod
    def run_solution(self, code_name: str) -> EvaluationResult:
        """
        Runs solution for input file code_name. 
        If is_generation is True, then stores the output to testcase.
        Otherwise, keep the output in the sandbox and report the file in EvaluationResult.
        """
        raise NotImplementedError

    def is_solution_abormal_exit(self, process: Process, eval_res: EvaluationResult) -> bool:

        if process.max_rss_kib > self.memory_limit_mib * 1024:
            eval_res.verdict = EvaluationOutcome.RUNERROR_MEMORY
        if process.cpu_time_sec > self.time_limit_sec:
            eval_res.verdict = EvaluationOutcome.TIMEOUT
        elif process.wall_clock_time_sec > self.time_limit_sec:
            eval_res.verdict = EvaluationOutcome.TIMEOUT_WALL
        elif process.exit_signal == signal.SIGXFSZ:
            eval_res.verdict = EvaluationOutcome.OUTPUT_LIMIT
        elif process.exit_signal == signal.SIGXCPU:  # this can happen
            eval_res.verdict = EvaluationOutcome.TIMEOUT
        elif process.exit_signal != 0:
            eval_res.verdict = EvaluationOutcome.RUNERROR_SIGNAL
            eval_res.checker_reason = f"Execution killed by signal ({signal.strsignal(process.exit_signal)})"
        elif process.exit_code != 0:
            eval_res.verdict = EvaluationOutcome.RUNERROR_EXITCODE
            eval_res.checker_reason = f"Execution exited with exit code {process.exit_code}"
        else:
            return False
        return True
