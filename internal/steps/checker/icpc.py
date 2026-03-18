import os
import shutil


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
    """
    CheckerStep class implementing ICPC checker behavior.

    See :class:`CheckerStep`.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.limits = self.context.config  # shorthand
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
        result: EvaluationResult,
        codename: str,
    ) -> EvaluationResult:

        input_file = os.path.join(
            self.context.path.testcases, self.context.construct_input_filename(codename)
        )
        answer_file = os.path.join(
            self.context.path.testcases,
            self.context.construct_output_filename(codename),
        )

        # In ICPC mode we do not need to check anything
        if result.verdict is not EvaluationOutcome.RUN_SUCCESS:
            result.checker_run = False
            return result

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

        checker_out_file = os.path.join(
            self.sandbox.checker.path, f"{codename}.check.out"
        )
        checker_err_file = os.path.join(
            self.sandbox.checker.path, f"{codename}.check.err"
        )

        checker_process = Process(
            checker_exec_command
            + [input_file, answer_file, feedback_dir.path + os.sep]
            + self.arguments,
            preexec_fn=lambda: os.chdir(self.sandbox.checker.path),
            stdin_redirect=result.output_file,
            stdout_redirect=checker_out_file,
            stderr_redirect=checker_err_file,
            time_limit_sec=self.limits.trusted_step_time_limit_sec,
            memory_limit_mib=self.limits.trusted_step_memory_limit_mib,
            output_limit_mib=self.limits.trusted_step_output_limit_mib,
        )
        wait_procs([checker_process])

        shutil.copy(
            checker_out_file,
            os.path.join(self.log_directory, os.path.basename(checker_out_file)),
        )
        shutil.copy(
            checker_err_file,
            os.path.join(self.log_directory, os.path.basename(checker_err_file)),
        )
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
                result.reason = f.readline().strip()
            shutil.copy(
                checker_feedback_file,
                os.path.join(self.log_directory, f"{codename}.check.feedback"),
            )

        if checker_process.is_timedout:
            result.verdict = EvaluationOutcome.CHECKER_TIMEDOUT
        elif checker_process.is_signaled_exit:
            result.verdict = EvaluationOutcome.CHECKER_CRASHED
        elif checker_process.exit_code == 42:
            result.verdict = EvaluationOutcome.ACCEPTED
            result.score = 1.0
        else:
            result.verdict = EvaluationOutcome.WRONG
            if result.output_file is None or os.path.getsize(result.output_file) == 0:
                result.verdict = EvaluationOutcome.NO_OUTPUT

        return result
