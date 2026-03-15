import os
import shutil


from internal.context import CheckerType, TMTContext, SandboxDirectory
from internal.exceptions import TMTMissingFileError, TMTInvalidConfigError
from internal.compilation import (
    make_compile_target,
    compile_single,
    make_clean,
    get_run_single_command,
)
from internal.formatting import Formatter
from internal.process import Process, wait_procs
from internal.steps.utils import requires_sandbox
from internal.outcomes import (
    EvaluationOutcome,
    EvaluationResult,
    CompilationOutcome,
    CompilationResult,
    ExecutionOutcome,
    GenerationResult,
    eval_outcome_to_grade_outcome,
)

from .base import CheckerStep


class ICPCCheckerStep(CheckerStep):
    def __init__(self, *, context: TMTContext, sandbox: SandboxDirectory | None):
        self.use_default_checker = (
            context.config.checker is None
            or context.config.checker.type == CheckerType.DEFAULT
        )
        if not self.use_default_checker:
            if context.config.checker is None:
                raise TMTInvalidConfigError("Config section `checker` is not present.")
            if context.config.checker.filename is None:
                raise TMTInvalidConfigError(
                    "Config option `checker.filename` is not present."
                )
            if not context.path.has_checker_directory():
                raise TMTMissingFileError(filetype="Directory", filename="checker")

            checker_name = context.config.checker.filename
        else:
            checker_name = "(default)"

        super().__init__(context, sandbox, checker_name)
        self.limits = context.config  # shorthand
        self.compiled_checker_path: str | None = None

    def check_unused_checker(self, formatter: Formatter) -> bool:
        if self.context.path.has_checker_directory() and self.use_default_checker:
            formatter.println(
                formatter.ANSI_YELLOW,
                "Warning: Directory 'checker' exists but it is not used by this problem. Check problem.yaml or remove the directory.",
                formatter.ANSI_RESET,
            )
            return True
        return False

    @requires_sandbox
    def compile(self) -> CompilationResult:
        workdir = self.sandbox.checker_compilation
        workdir.clean()

        if self.use_default_checker:
            # In this case we have no checker directory, therefore, we will build the default checker
            # in sandbox/checker instead
            compile_result = compile_single(
                context=self.context,
                directory=workdir.path,
                sources=[self.context.path.default_checker_icpc],
                executable_filename_base="checker",
                executable_stack_size_mib=self.limits.trusted_step_memory_limit_mib,
            )
        else:
            compile_result = make_compile_target(
                context=self.context,
                directory=self.context.path.checker,
                sources=[self.context.config.checker.filename],
                target="checker",
                executable_stack_size_mib=self.limits.trusted_step_memory_limit_mib,
            )

        # Finally, if success, ...
        if compile_result.verdict is CompilationOutcome.SUCCESS:
            if compile_result.produced_file is None:
                raise FileNotFoundError("Compilation did not produce checker")
            self.compiled_checker_path = compile_result.produced_file

        return compile_result

    def clean_up(self):
        make_clean(directory=self.context.path.checker)

    @requires_sandbox
    def run_checker_during_gen(
        self,
        result: GenerationResult,
        sol_result: EvaluationResult | None,
        codename: str,
    ):
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

        workdir = self.sandbox.checker
        workdir.clean()

        copied_testcase_output = workdir.file(os.path.basename(testcase_answer))
        shutil.copy(testcase_answer, copied_testcase_output)

        checker_result = self._run_without_clean(
            self.context.config.checker.arguments,
            EvaluationResult(
                output_file=testcase_answer
                if sol_result is None
                else sol_result.output_file
            ),
            testcase_input,
            testcase_answer,
        )
        result.output_validation = eval_outcome_to_grade_outcome(checker_result)
        result.reason = checker_result.reason
        return checker_result

    def run_checker(
        self,
        arguments: list[str] | None,
        evaluation_record: EvaluationResult,
        input_file: str,
        answer_file: str,
    ) -> EvaluationResult:
        self.sandbox.checker.clean()
        return self._run_without_clean(
            arguments, evaluation_record, input_file, answer_file
        )

    def _run_without_clean(
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
        workdir = self.sandbox.checker
        workdir.clean()

        feedback_dir = workdir.subdir("feedback_dir")
        feedback_dir.create()

        assert self.compiled_checker_path is not None
        checker_exec_command = get_run_single_command(
            context=self.context,
            directory=os.path.dirname(self.compiled_checker_path),
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
            checker_exec_command
            + [input_file, answer_file, feedback_dir.path + os.sep]
            + arguments,
            preexec_fn=lambda: os.chdir(workdir.path),
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
        checker_feedback_file = feedback_dir.file("judgemessage.txt")
        if os.path.isfile(checker_feedback_file):
            with open(checker_feedback_file, "r") as f:
                evaluation_record.reason = f.readline().strip()

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
