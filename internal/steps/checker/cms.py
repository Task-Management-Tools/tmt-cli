from internal.outcome import (
    EvaluationOutcome,
    EvaluationResult,
    CompilationOutcome,
    CompilationResult,
)

from .base import CheckerStep


class CMSCheckerStep(CheckerStep):
    def __init__(
        self, problem_dir: str, makefile_path: str, time_limit: float, memory_limit: int
    ):
        super().__init__(
            problem_dir=problem_dir,
            makefile_path=makefile_path,
            time_limit=time_limit,
            memory_limit=memory_limit,
        )

    def compile(self) -> CompilationResult:
        if self.working_dir.has_checker_directory():
            compile_result = self.compile_with_make(self.working_dir.checker)
        else:
            # In this case we have no checker directory, therefore, we will run the default checker
            # (the white diff) in sandbox/checker instead, therefore no compilation is required.
            return CompilationResult(CompilationOutcome.SUCCESS)

    def prepare_sandbox(self):
        super().prepare_sandbox()

    def run_checker(
        self,
        arguments: list[str],
        evaluation_record: EvaluationResult,
        input_file: str,
        answer_file: str,
    ) -> EvaluationResult:
        # In CMS mode we do not need to check anything
        if evaluation_record.verdict is not EvaluationOutcome.RUN_SUCCESS:
            return evaluation_record

        # the output validator is invoked via
        # $ checker input_file answer_file output_file > score 2> reason
        # the reason can be one of translate:success, translate:wrong, or translate:partial, and they should be translated.
        # only the first line is taken, but the second line is used for TPS

        # Non-zero return value should be treated as crash.
