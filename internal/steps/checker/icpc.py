import os


from internal.context import TMTContext, SandboxDirectory
from internal.compilation import (
    make_compile_target,
    compile_single,
    make_clean,
    get_run_single_command,
)
from internal.process import Process, wait_procs
from internal.steps.utils import requires_sandbox
from internal.outcomes import (
    EvaluationOutcome,
    EvaluationResult,
    CompilationOutcome,
    CompilationResult,
)

from .base import CheckerStep


class ICPCCheckerStep(CheckerStep):
    def __init__(self, *, context: TMTContext, sandbox: SandboxDirectory | None):
        super().__init__(context, sandbox)

        self.limits = context.config  # shorthand
        self.compiled_checker_path: str | None = None

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
    def run_checker(
        self,
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
        self.sandbox.checker.clean()
        feedback_dir = self.sandbox.checker.subdir("feedback_dir")
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

        checker_process = Process(
            checker_exec_command
            + [input_file, answer_file, feedback_dir.path + os.sep]
            + self.arguments,
            preexec_fn=lambda: os.chdir(self.sandbox.checker.path),
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
