import os
import pathlib
import shutil

from pathlib import Path

from internal.compilation.utils import recognize_language
from internal.process import Process, wait_procs
from internal.compilation import compile_single, get_run_single_command
from internal.outcomes import (
    EvaluationOutcome,
    EvaluationResult,
    CompilationOutcome,
    CompilationResult,
)
from internal.steps.utils import CompilationJob, CompilationSlot, requires_sandbox

from .base import SolutionStep


class BatchSolutionStep(SolutionStep):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def clean_up(self):
        pass

    @requires_sandbox
    def compilation_jobs(self):
        yield CompilationJob(
            CompilationSlot.SOLUTION,
            self.compile_solution,
            ", ".join(os.path.basename(file) for file in self.submission_files),
        )

    @requires_sandbox
    def compile_solution(self) -> CompilationResult:
        if len(self.submission_files) != 1:
            return CompilationResult(
                verdict=CompilationOutcome.FAILED,
                exit_status=-1,
                standard_error="Batch task only supports single file submission.",
            )

        workdir = self.sandbox.solution_compilation
        workdir.clean()

        lang_type = recognize_language(self.submission_files, self.context)
        if lang_type is None:
            return CompilationResult(
                verdict=CompilationOutcome.FAILED,
                exit_status=-1,
                standard_error=f"Source files {self.submission_files} are not recognized by any language.",
            )

        # Replace the solution file with absolute path, then we try to add grader if the config exists
        # TODO: what is the specification of graders in ICPC format?
        sources = self.submission_files
        sources = [self.context.path.replace_with_solution(f) for f in sources]
        headers = []

        if self.grader is not None:
            lang = lang_type(self.context)
            graders = []
            grader_dir = pathlib.Path(self.context.path.grader) / lang.id

            # We only iterate the immediate files in the directory, because most of the time the judge won't support nested directories in the graders
            for file in grader_dir.iterdir():
                if not file.is_file():
                    continue
                base, ext = os.path.splitext(os.path.basename(file))
                if base == self.grader and ext in lang.source_extensions:
                    graders.append(str(file.absolute()))
                else:
                    headers.append(str(file.absolute()))
            if len(graders) == 0:
                return CompilationResult(
                    verdict=CompilationOutcome.FAILED,
                    exit_status=-1,
                    standard_error=f"Grader of language {lang.name} is not found in directory {grader_dir.relative_to(os.getcwd())}.",
                )
            
            sources += graders
            del lang
        del lang_type

        comp_result = compile_single(
            context=self.context,
            directory=workdir.path,
            sources=sources,
            headers=headers,
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
