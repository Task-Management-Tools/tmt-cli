import os
from abc import ABC, abstractmethod

from internal.context import TMTContext, SandboxDirectory
from internal.outcomes import EvaluationResult, CompilationResult


class CheckerStep(ABC):
    def __init__(self, context: TMTContext, sandbox: SandboxDirectory | None):
        self.context = context
        self.sandbox = sandbox
        if self.sandbox:
            self.sandbox.checker.create()

    @abstractmethod
    def compile(self) -> CompilationResult:
        raise NotImplementedError

    @abstractmethod
    def run_checker(
        self,
        arguments: list[str],
        evaluation_record: EvaluationResult,
        input_file: str,
        answer_file: str,
    ) -> EvaluationResult:
        raise NotImplementedError
