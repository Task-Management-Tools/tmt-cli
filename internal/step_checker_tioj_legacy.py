from internal.step_checker import CheckerStep
from internal.outcome import EvaluationOutcome, EvaluationResult, CompilationResult


class CMSCheckerStep(CheckerStep):
    def __init__(self, problem_dir: str, makefile_path: str,
                 time_limit: float, memory_limit: int):
        super().__init__(problem_dir=problem_dir,
                         makefile_path=makefile_path,
                         time_limit=time_limit,
                         memory_limit=memory_limit)

    def compile(self) -> CompilationResult:
        
        if self.working_dir.has_checker_directory():
            compile_result = self.compile_with_make(self.working_dir.checker)
        else: 
            # In this case we have no checker directory, therefore, we will run the default checker
            # (the white diff) in sandbox/checker instead, therefore no compilation is required.
            return "", "", True

    def prepare_sandbox(self):
        self.working_dir.mkdir_sandbox()

    def run_checker(self, arguments: list[str],
                    evaluation_record: EvaluationResult, input_file: str, answer_file: str) -> EvaluationResult:
        
        # In CMS mode we do not need to check anything
        if evaluation_record.verdict is not EvaluationOutcome.RUN_SUCCESS:
            return evaluation_record

        # the output validator is invoked via
        # $ checker output_file input_file answer_file language source_code stage_number 2> reason 

        # output 0 means accepted, otherwise wrong answer.
        # after initial 0, one can optionally output several 
        # SPECJUDGE_OVERRIDE_SCORE score 
        # which overrides score, 
        # SPECJUDGE_OVERRIDE_VERDICT which overrides verdict

        # If this is a multistage problem and "Invoke special judge between stages" is set, 
        # the special judge will be invoked after each stage is completed, and argv[6] will be the 0-based previously completed stage number
        # For all intermediate stages, if the special judge outputs 0, the judging process will continue normally; otherwise, the final result will be WA and all the remaining stages will be skipped. Also, the file argv[1] can be overwritten, and it will be passed down to the next stage's input.
    #     If the verdict is overriden in the intermediate stages, all the remaining stages will be skipped and the final result will be set to that verdict.

#include "testlib.h" (docs) and #include "nlohmann/json.hpp" (docs) are provided for C++ special judge programs. If you're using testlib, note that the argv format of TIOJ is different from that required by the library, thus some preprocessing is needed before calling registerTestlibCmd. 
        # Non-zero return value should be treated as crash.