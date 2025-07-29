from internal.step_meta_makefile import MetaMakefileCompileStep
from internal.step_solution import EvaluationResult


class CheckerStep(MetaMakefileCompileStep):
    def __init__(self, problem_dir: str, makefile_path: str,
                 time_limit: float = 10_000, memory_limit: int = 4 * 1024 * 1024):
        super().__init__(problem_dir=problem_dir,
                         makefile_path=makefile_path,
                         time_limit=time_limit,
                         memory_limit=memory_limit)

    def compile(self) -> tuple[str, str, bool]:
        pass

    def prepare_sandbox(self):
        self.working_dir.mkdir_sandbox_checker()

    def run_checker(self, arguments: list[str],
                    evaluation_record: EvaluationResult, input_file: str, answer_file: str) -> EvaluationResult:
        pass