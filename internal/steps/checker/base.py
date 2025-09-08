import os
from abc import ABC, abstractmethod

from internal.context import TMTContext
from internal.outcome import EvaluationResult, CompilationResult


class CheckerStep(ABC):
    def __init__(self, context: TMTContext):
        self.context = context

    @abstractmethod
    def compile(self) -> CompilationResult:
        raise NotImplementedError

    @abstractmethod
    def prepare_sandbox(self):
        os.makedirs(self.context.path.sandbox_checker, exist_ok=True)

    @abstractmethod
    def run_checker(
        self,
        arguments: list[str],
        evaluation_record: EvaluationResult,
        input_file: str,
        answer_file: str,
    ) -> EvaluationResult:
        raise NotImplementedError
