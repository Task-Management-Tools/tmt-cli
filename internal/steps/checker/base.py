from abc import ABC, abstractmethod

from internal.context import TMTContext, SandboxDirectory
from internal.outcomes import EvaluationResult, CompilationResult


class CheckerStep(ABC):
    def __init__(
        self, context: TMTContext, sandbox: SandboxDirectory | None, checker_name: str
    ):
        self.context = context
        self.sandbox = sandbox
        if self.sandbox:
            self.sandbox.checker.create()
            self.sandbox.checker_compilation.create()
        self.checker_name = checker_name

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
