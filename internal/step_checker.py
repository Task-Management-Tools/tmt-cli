from internal.step_meta_makefile import MetaMakefileCompileStep
from internal.step_solution import EvaluationResult


class CheckerStep(MetaMakefileCompileStep):
    def __init__(self, *, makefile_path: str, time_limit: float, memory_limit: int):
        super().__init__(makefile_path=makefile_path,
                         time_limit=time_limit,
                         memory_limit=memory_limit)

    def compile(self) -> tuple[str, str, bool]:
        pass

    def prepare_sandbox(self):
        self.working_dir.mkdir_sandbox_checker()

    def run_checker(self, arguments: list[str],
                    evaluation_record: EvaluationResult, input_file: str, answer_file: str) -> EvaluationResult:
        pass