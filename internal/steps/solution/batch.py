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
        self.submission_format = [self.context.config.short_name]

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
        def compile_fail(reason: str) -> CompilationResult:
            return CompilationResult(
                verdict=CompilationOutcome.FAILED,
                exit_status=-1,
                standard_error=reason,
            )

        sources = list(
            map(self.context.path.replace_with_solution, self.submission_files)
        )
        for source in sources:
            if not Path(source).exists() or not Path(source).is_file():
                return compile_fail(
                    f"Source file {os.path.basename(source)} is not a file."
                )

        if len(self.submission_files) != len(self.submission_format):
            return compile_fail(
                f"Submission file count mismatch (found {len(self.submission_files)}, expect {len(self.submission_format)})."
            )

        workdir = self.sandbox.solution_compilation
        workdir.clean()

        # Replace the solution file with absolute path, then we try to add grader if the config exists
        source_rename = [
            f + os.path.splitext(s)[1] for f, s in zip(self.submission_format, sources)
        ]
        headers = []
        graders = []

        lang_type = recognize_language(sources, self.context)
        if lang_type is None:
            return compile_fail(
                f"Source files {' ,'.join(map(os.path.basename, sources))} are not recognized by any language."
            )

        # TODO: what is the specification of graders in ICPC format?
        if self.grader is not None:
            lang = lang_type(self.context)
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
                return compile_fail(
                    f"Grader of language {lang.name} is not found in directory {grader_dir.relative_to(os.getcwd())}."
                )

            del lang
        del lang_type

        workdir.clean()
        comp_result = compile_single(
            context=self.context,
            directory=workdir.path,
            sources=graders + sources,
            source_rename=[None] * len(graders) + source_rename,
            headers=headers,
            executable_filename_base=self.executable_name_base,
            executable_stack_size_mib=self.memory_limit_mib,
        )

        if (
            comp_result.verdict is CompilationOutcome.SUCCESS
            and comp_result.produced_file is None
        ):
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

        result = EvaluationResult(
            verdict=EvaluationOutcome.RUN_SUCCESS,
            output_file=sandbox_output_file,
        )
        result.fill_from_solution_process(solution)

        if not Path(sandbox_output_file).exists():
            result.verdict = EvaluationOutcome.NO_FILE
            result.output_file = None

        elif self.is_solution_abormal_exit(result):
            pass

        return result
