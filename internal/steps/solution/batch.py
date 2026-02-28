import os
import shutil

from pathlib import Path

from internal.context import TMTContext, SandboxDirectory
from internal.process import Process, wait_procs
from internal.compilation import compile_single, get_run_single_command
from internal.outcomes import (
    EvaluationOutcome,
    EvaluationResult,
    CompilationOutcome,
    CompilationResult,
)
from internal.steps.utils import requires_sandbox

from .base import SolutionStep


class BatchSolutionStep(SolutionStep):
    def __init__(
        self,
        *,
        context: TMTContext,
        sandbox: SandboxDirectory | None,
        is_generation: bool,
        submission_files: list[str],
    ):
        super().__init__(
            context=context,
            sandbox=sandbox,
            is_generation=is_generation,
            submission_files=submission_files,
        )

    def clean_up(self):
        pass

    @requires_sandbox
    def compile_solution(self) -> CompilationResult:
        if self.sandbox is None:
            raise RuntimeError("")
        
        if len(self.submission_files) != 1:
            return CompilationResult(
                verdict=CompilationOutcome.FAILED,
                exit_status=-1,
                standard_error="Batch task only supports single file submission.",
            )
        

        workdir = self.sandbox.solution_compilation
        workdir.clean()

        files = self.submission_files
        if self.grader is not None:
            files.append(self.context.path.replace_with_grader(self.grader))
        files = [self.context.path.replace_with_solution(f) for f in files]

        comp_result = compile_single(
            context=self.context,
            directory=workdir.path,
            sources=files,
            executable_filename_base=self.executable_name_base,
            executable_stack_size_mib=self.memory_limit_mib,
        )

        if comp_result.verdict is CompilationOutcome.SUCCESS:
            if comp_result.produced_file is None:
                raise FileNotFoundError("Compilation did not produce solution")

        comp_result.dump_to_logs(self.log_directory, "solution")
        return comp_result

    @requires_sandbox
    def run_solution(self, code_name: str) -> EvaluationResult:
        """
        This function only returns FileNotFoundError for execution error.
        """
        os.makedirs(self.log_directory, exist_ok=True)
        workdir = self.sandbox.solution_invocation
        workdir.clean()

        file_in_name = self.context.construct_input_filename(code_name)
        file_out_name = self.context.construct_output_filename(code_name)
        file_err_name = f"{code_name}.sol.err"

        testcase_input = os.path.join(self.context.path.testcases, file_in_name)
        sandbox_input_file = workdir.file(file_in_name)
        sandbox_output_file = workdir.file(file_out_name)
        sandbox_error_file = workdir.file(file_err_name)

        no_output_file = False

        shutil.copy(testcase_input, sandbox_input_file)

        # TODO: noramlly judge should use pipe for I/O, which might make some subtle differences
        # currently, for convenience, it is from file but we should support both modes.
        solution_exec_command = get_run_single_command(
            context=self.context,
            directory=self.sandbox.solution_compilation.subdir("build").path,
            executable_filename_base=self.executable_name_base,
            executable_stack_size_mib=self.memory_limit_mib,
        )
        solution = Process(
            solution_exec_command,
            preexec_fn=lambda: os.chdir(workdir.path),
            stdin_redirect=sandbox_input_file,
            stdout_redirect=sandbox_output_file,
            stderr_redirect=sandbox_error_file,
            time_limit_sec=self.time_limit_sec,
            memory_limit_mib=self.memory_limit_mib,
            output_limit_mib=self.output_limit_mib,
        )
        wait_procs([solution])

        if Path(sandbox_input_file).exists():
            os.unlink(sandbox_input_file)

        # Move logs
        Path(sandbox_error_file).touch()
        shutil.move(sandbox_error_file, os.path.join(self.log_directory, file_err_name))

        # Move output
        if Path(sandbox_output_file).exists():
            if self.is_generation:
                shutil.copy(
                    sandbox_output_file,
                    os.path.join(self.context.path.testcases, file_out_name),
                )
        else:
            no_output_file = True

        result = EvaluationResult(
            verdict=EvaluationOutcome.RUN_SUCCESS,
            output_file=sandbox_output_file,
        )
        result.fill_from_solution_process(solution)

        if no_output_file:
            result.verdict = EvaluationOutcome.NO_FILE
        elif self.is_solution_abormal_exit(solution, result):
            pass

        return result
