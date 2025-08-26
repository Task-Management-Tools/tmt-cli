import os

from internal.context import TMTContext
from internal.outcome import EvaluationResult, CompilationResult


class CheckerStep():
    def __init__(self, context: 'TMTContext'):
        self.context = context

    def compile(self) -> CompilationResult:
        raise NotImplementedError

    def prepare_sandbox(self):
        os.makedirs(self.context.path.sandbox_checker, exist_ok=True)

    def run_checker(self, arguments: list[str],
                    evaluation_record: EvaluationResult, input_file: str, answer_file: str) -> EvaluationResult:
        raise NotImplementedError