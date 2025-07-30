import os
import shutil
import pathlib

from internal.globals import context
from internal.step_checker import CheckerStep
from internal.runner import Process, pre_wait_procs, wait_procs
from internal.outcome import EvaluationOutcome, EvaluationResult, CompilationOutcome, CompilationResult


class ICPCCheckerStep(CheckerStep):
    def __init__(self):

        super().__init__(makefile_path=context.path.makefile_checker,
                         time_limit=context.config.trusted_step_time_limit,
                         memory_limit=context.config.trusted_step_memory_limit)

    def compile(self) -> CompilationResult:

        if context.path.has_checker_directory():
            compile_result = self.compile_with_make(context.path.checker)
        else:
            # In this case we have no checker directory, therefore, we will build the default checker
            # in sandbox/checker instead, that is working_dir.sandbox_checker
            checker_path = pathlib.Path(context.path.script_dir) / "internal/checkers/icpc_default_validator.cc"
            shutil.copy(checker_path, os.path.join(context.path.sandbox_checker))
            compile_result = self.compile_with_make(context.path.sandbox_checker)

        # Finally, if success, we move the checker into the sandbox, preparing to invoke it.
        return compile_result

    def prepare_sandbox(self):
        context.path.mkdir_sandbox_checker()

    def run_checker(self, arguments: list[str],
                    evaluation_record: EvaluationResult, input_file: str, answer_file: str) -> EvaluationResult:

        # In ICPC mode we do not need to check anything
        if evaluation_record.verdict is not EvaluationOutcome.RUN_SUCCESS:
            evaluation_record.checker_run = False
            return evaluation_record

        # We must create a directory for judge feedbacks
        # TODO: generate a name that will not clash with other files
        feedback_dir = os.path.join(context.path.sandbox_solution, "feedback_dir")
        if not os.path.isdir(feedback_dir):
            os.mkdir(feedback_dir)

        checker = os.path.join(context.path.sandbox_checker, "checker")
        # the output validator is invoked via
        # $ <output_validator_program> input_file answer_file feedback_dir [additional_arguments] < output_file [ > team_input ]
        # we will ignore the [ > team_input ] part, since this only happens for interactive mode.

        pre_wait_procs()
        checker_process = Process([checker, input_file, answer_file, feedback_dir] + arguments,
                                  stdin_redirect=evaluation_record.output_file,
                                  stdout=None,
                                  stderr=None,
                                  time_limit=self.time_limit,
                                  memory_limit=self.memory_limit)
        wait_procs([checker_process])

        # the interesting files in the directory are:
        #  - nextpass.in: the input for the next pass, the checker must success to run the next pass
        #  - score.txt, score_multiplier.txt: the first is a solid number, while the second behaves like CMS.
        #       if neither of them presents, it is treated as full score!
        #  - judgemessage.txt: feedback to the judges, we should report this in our CLI.
        #  - teammessage.txt: feedback to the teams, normally this is not visible just ignore it
        #  - judgeimage.<ext>, teamimage.<ext>: we cannot display any of them in the CLI, so ignore them

        # TODO: actually support these things
        if checker_process.is_timedout:
            evaluation_record.verdict = EvaluationOutcome.CHECKER_CRASHED
        elif checker_process.is_signaled_exit:
            evaluation_record.verdict = EvaluationOutcome.CHECKER_CRASHED
        elif checker_process.exit_code == 42:
            evaluation_record.verdict = EvaluationOutcome.ACCEPTED
        else:
            evaluation_record.verdict = EvaluationOutcome.WRONG
            if os.path.getsize(evaluation_record.output_file) == 0:
                evaluation_record.verdict = EvaluationOutcome.NO_OUTPUT

        evaluation_record.checker_run = True
        return evaluation_record
        # Do remember to take 42 exit code as sucess and any other as fail (incorrect).
