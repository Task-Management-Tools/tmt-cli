import os
import shutil
import pathlib


from internal.context import CheckerType, TMTContext
from internal.compilation import (
    make_compile_targets,
    make_clean,
    get_run_single_command,
)
from internal.process import Process, wait_procs
from internal.outcomes import (
    EvaluationOutcome,
    EvaluationResult,
    CompilationOutcome,
    CompilationResult,
    ExecutionOutcome,
    eval_outcome_to_grade_outcome,
)

from .base import CheckerStep


class ICPCCheckerStep(CheckerStep):
    def __init__(self, context: TMTContext):
        super().__init__(context)
        self.limits = context.config  # shorthand
        self.use_default_checker = (
            context.config.checker is None
            or context.config.checker.type == CheckerType.DEFAULT
            or not context.path.has_checker_directory()
        )

    def compile(self) -> CompilationResult:
        if self.use_default_checker:
            # In this case we have no checker directory, therefore, we will build the default checker
            # in sandbox/checker instead
            checker_name = self.context.path.default_checker_icpc
            shutil.copy(checker_name, self.context.path.sandbox_checker)

            compile_result = make_compile_targets(
                context=self.context,
                directory=self.context.path.sandbox_checker,
                sources=[os.path.basename(checker_name)],
                target="checker",
                executable_stack_size_mib=self.limits.trusted_step_memory_limit_mib,
            )
        else:
            if not self.context.path.has_checker_directory():
                raise FileNotFoundError("Directory `checker` is not present.")
            if (
                self.context.config.checker is None
                or self.context.config.checker.filename is None
            ):
                raise ValueError("Checker config should be present")

            compile_result = make_compile_targets(
                context=self.context,
                directory=self.context.path.checker,
                sources=[self.context.config.checker.filename],
                target="checker",
                executable_stack_size_mib=self.limits.trusted_step_memory_limit_mib,
            )

        # Finally, if success, we move the checker into the sandbox, preparing to invoke it.
        if compile_result.verdict is CompilationOutcome.SUCCESS:
            if compile_result.produced_file is None:
                raise FileNotFoundError("Compilation did not produce checker")
            shutil.copy(
                compile_result.produced_file,
                self.context.path.sandbox_checker,
            )

        return compile_result

    def prepare_sandbox(self):
        super().prepare_sandbox()

    def clean_up(self):
        make_clean(directory=self.context.path.checker)

    def run_checker_during_gen(self, result, codename):
        if result.output_generation not in [
            ExecutionOutcome.SUCCESS,
            ExecutionOutcome.SKIPPED_SUCCESS,
        ] or result.input_validation not in [
            ExecutionOutcome.SUCCESS,
            ExecutionOutcome.SKIPPED_SUCCESS,
        ]:
            result.output_validation = ExecutionOutcome.SKIPPED
            return

        if result.is_output_forced:
            if not self.context.config.checker.check_forced_output:
                result.output_validation = ExecutionOutcome.SKIPPED_SUCCESS
                return
        else:  # generated output
            if not self.context.config.checker.check_generated_output:
                result.output_validation = ExecutionOutcome.SKIPPED_SUCCESS
                return
        testcase_input = os.path.join(
            self.context.path.testcases,
            self.context.construct_input_filename(codename),
        )
        testcase_answer = os.path.join(
            self.context.path.testcases,
            self.context.construct_output_filename(codename),
        )

        copied_testcase_output = os.path.join(
            self.context.path.sandbox_checker,
            os.path.basename(testcase_answer),
        )
        shutil.copy(testcase_answer, copied_testcase_output)

        checker_result = self.run_checker(
            self.context.config.checker.arguments,
            EvaluationResult(output_file=copied_testcase_output),
            testcase_input,
            testcase_answer,
        )
        result.output_validation = eval_outcome_to_grade_outcome(checker_result)
        result.reason = checker_result.checker_reason
        return checker_result

    def run_checker(
        self,
        arguments: list[str] | None,
        evaluation_record: EvaluationResult,
        input_file: str,
        answer_file: str,
    ) -> EvaluationResult:
        # In ICPC mode we do not need to check anything
        if evaluation_record.verdict is not EvaluationOutcome.RUN_SUCCESS:
            evaluation_record.checker_run = False
            return evaluation_record

        # We must create a directory for judge feedbacks
        # TODO: generate a name that will not clash with other files
        feedback_dir = (
            os.path.join(self.context.path.sandbox_solution, "feedback_dir") + os.sep
        )
        if not os.path.isdir(feedback_dir):
            os.mkdir(feedback_dir)

        checker_exec_command = get_run_single_command(
            context=self.context,
            directory=self.context.path.sandbox_checker,
            executable_filename_base="checker",
            executable_stack_size_mib=self.limits.trusted_step_memory_limit_mib,
        )
        assert checker_exec_command is not None
        # the output validator is invoked via
        # $ <output_validator_program> input_file answer_file feedback_dir [additional_arguments] < output_file [ > team_input ]
        # we will ignore the [ > team_input ] part, since this only happens for interactive mode.

        if arguments is None:
            arguments = []
        checker_process = Process(
            checker_exec_command + [input_file, answer_file, feedback_dir] + arguments,
            stdin_redirect=evaluation_record.output_file,
            stdout=None,
            stderr=None,
            time_limit_sec=self.limits.trusted_step_time_limit_sec,
            memory_limit_mib=self.limits.trusted_step_memory_limit_mib,
            output_limit_mib=self.limits.trusted_step_output_limit_mib,
        )
        wait_procs([checker_process])

        # the interesting files in the directory are:
        #  - nextpass.in: the input for the next pass, the checker must succeed to run the next pass
        #  - score.txt, score_multiplier.txt: the first is a solid number, while the second behaves like CMS.
        #       if neither of them presents, it is treated as full score!
        #  - judgemessage.txt: feedback to the judges, we should report this in our CLI.
        #  - teammessage.txt: feedback to the teams, normally this is not visible just ignore it
        #  - judgeimage.<ext>, teamimage.<ext>: we cannot display any of them in the CLI, so ignore them
        checker_feedback_file = pathlib.Path(feedback_dir) / "judgemessage.txt"
        if (checker_feedback_file).is_file():
            with open(checker_feedback_file, "r") as f:
                evaluation_record.checker_reason = f.readline().strip()

        if checker_process.is_timedout:
            evaluation_record.verdict = EvaluationOutcome.CHECKER_TIMEDOUT
        elif checker_process.is_signaled_exit:
            evaluation_record.verdict = EvaluationOutcome.CHECKER_CRASHED
        elif checker_process.exit_code == 42:
            evaluation_record.verdict = EvaluationOutcome.ACCEPTED
        else:
            evaluation_record.verdict = EvaluationOutcome.WRONG
            if (
                evaluation_record.output_file is None
                or os.path.getsize(evaluation_record.output_file) == 0
            ):
                evaluation_record.verdict = EvaluationOutcome.NO_OUTPUT

        return evaluation_record
