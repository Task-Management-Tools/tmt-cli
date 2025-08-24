from internal.globals import context
from internal.outcome import EvaluationResult, CompilationResult


class CheckerStep():
    def __init__(self):
        pass

    def compile(self) -> CompilationResult:
        raise NotImplementedError

    def prepare_sandbox(self):
        context.path.mkdir_sandbox_checker()

    def run_checker(self, arguments: list[str],
                    evaluation_record: EvaluationResult, input_file: str, answer_file: str) -> EvaluationResult:
        raise NotImplementedError