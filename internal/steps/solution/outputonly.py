import os
import shutil

import pathlib
import zipfile

from internal.compilation.single import compile_single
from internal.compilation.utils import recognize_language
from internal.outcomes import (
    EvaluationOutcome,
    EvaluationResult,
    CompilationOutcome,
    CompilationResult,
)
from internal.steps.utils import CompilationJob, CompilationSlot, requires_sandbox

from .batch import BatchSolutionStep


class OutputOnlySolutionStep(BatchSolutionStep):
    """
    Implements OutputOnly solution evaluation step based on CMS (contest management system).

    In OutputOnly mode, in addition to submitting a self-contained source file, it supports three formats as follows:
     - A zip file containing all outputs.
     - A directory containing all outputs.
     - A list of text files.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.supplied_output = False

    @requires_sandbox
    def compile_solution(self) -> CompilationResult:
        self.sandbox.solution_compilation.clean()
        self.sandbox.solution_invocation.clean()

        def compile_fail(reason: str) -> CompilationResult:
            return CompilationResult(
                verdict=CompilationOutcome.FAILED,
                exit_status=-1,
                standard_error=reason,
            )

        def found_output_files() -> CompilationResult:
            self.supplied_output = True
            return CompilationResult(
                verdict=CompilationOutcome.SKIPPED,
                standard_error="Submission contains only output files",
            )

        def is_output_file(file: pathlib.Path | zipfile.Path) -> bool:
            return file.is_file() and str(file).endswith(
                self.context.config.output_extension
            )

        sources = self.submission_files

        # Directory mode
        directory = pathlib.Path(sources[0])
        if len(sources) == 1 and directory.is_dir():
            for file in filter(is_output_file, directory.iterdir()):
                shutil.copy(file, self.sandbox.solution_invocation.path)
            return found_output_files()
        del directory

        # The remaining should be all regular files
        for source in map(pathlib.Path, sources):
            if not source.exists() or not source.is_file():
                return compile_fail(
                    f"Submission file {os.path.basename(source)} is not a file.\n"
                    "Submission must be a list of files or a single directory for OutputOnly task."
                )

        # Source code mode
        lang_type = recognize_language(sources, self.context)
        if lang_type is not None:
            if len(sources) != len(self.submission_format):
                return compile_fail(
                    f"Submission source files count mismatch (found {len(sources)}, expect {len(self.submission_format)}) "
                )

            # TODO: does grader really make sense in OutputOnly tasks?
            source_rename = [
                f + os.path.splitext(s)[1]
                for f, s in zip(self.submission_format, sources)
            ]
            comp_result = compile_single(
                context=self.context,
                directory=self.sandbox.solution_compilation.path,
                sources=sources,
                source_rename=source_rename,
                executable_filename_base=self.executable_name_base,
                executable_stack_size_mib=self.memory_limit_mib,
            )
            if (
                comp_result.verdict is CompilationOutcome.SUCCESS
                and comp_result.produced_file is None
            ):
                raise FileNotFoundError("Compilation did not produce solution")

            comp_result.dump_to_logs(self.context.log_directory, "solution")
            return comp_result

        # Duplication check set for the following two cases
        filelist = set()

        # Zip file mode
        if len(sources) == 1 and zipfile.is_zipfile(sources[0]):
            try:
                zip_filename = sources[0]
                with zipfile.ZipFile(zip_filename, "r") as zip_ref:
                    for file in filter(is_output_file, zipfile.Path(zip_ref).iterdir()):
                        # Path traversal?
                        if (
                            os.path.commonpath([str(file), zip_filename])
                            != zip_filename
                        ):
                            continue

                        if file.name in filelist:
                            return compile_fail(
                                f"Duplicated output file {file.name} in submitted ZIP archive."
                            )
                        filelist.add(file.name)
                        out_path = self.sandbox.solution_invocation.file(file.name)

                        with open(out_path, "wb") as f:
                            f.write(file.read_bytes())

                return found_output_files()
            except zipfile.BadZipFile:
                return compile_fail(
                    "Submission source file is not a valid ZIP archive."
                )

        # Output file list mode
        for src in sources:
            basename = os.path.basename(src)
            if not basename.endswith(self.context.config.output_extension):
                continue
            if basename in filelist:
                return compile_fail(
                    f"Duplicated output file {basename} in submitted file lists."
                )
            filelist.add(basename)
            shutil.copy(src, self.sandbox.solution_invocation.path)

        return found_output_files()

    @requires_sandbox
    def compilation_jobs(self):
        yield CompilationJob(
            CompilationSlot.SOLUTION,
            self.compile_solution,
            ", ".join(pathlib.Path(file).parts[-1] for file in self.submission_files),
        )

    @requires_sandbox
    def run_solution(self, codename: str) -> EvaluationResult:
        if self.supplied_output:
            output_file = os.path.join(
                self.sandbox.solution_invocation.path,
                self.context.construct_output_filename(codename),
            )
            if pathlib.Path(output_file).exists():
                return EvaluationResult(
                    codename=codename, output_file=output_file, max_memory_kib=0
                )
            return EvaluationResult(
                codename=codename,
                verdict=EvaluationOutcome.NO_FILE,
                output_file=None,
                max_memory_kib=0,
            )

        else:
            return super().run_solution(codename)
