
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from internal.context import TMTContext
from internal.outcome import EvaluationResult, CompilationResult


class CheckerStep():
    def __init__(self, context: 'TMTContext'):
        self.context = context

    def compile(self) -> CompilationResult:
        raise NotImplementedError

    def prepare_sandbox(self):
        self.context.path.mkdir_sandbox_checker()

    def run_checker(self, arguments: list[str],
                    evaluation_record: EvaluationResult, input_file: str, answer_file: str) -> EvaluationResult:
        raise NotImplementedError