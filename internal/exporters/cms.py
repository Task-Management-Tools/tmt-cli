import json
import os
import re
from pathlib import Path

from internal.compilation import languages
from internal.compilation.utils import recognize_language
from internal.context.config import CheckerType, JudgeConvention, ProblemType
from internal.formatting import Formatter
from internal.context import TMTContext

from .base import FolderFormatExporter
from .operations import ConversionOperation


class DumpFileOperation(ConversionOperation):
    """Custom file processing operation"""

    def __init__(self, target_path: str, content: str):
        self.target_path = target_path
        self.content = content

    def target_name(self) -> str:
        return self.target_path

    def execute(
        self, formatter: Formatter, context: TMTContext, output_folder: Path
    ) -> None:
        target = output_folder / Path(self.target_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(self.content.encode())
        formatter.println("[", formatter.ANSI_GREEN, "OK", formatter.ANSI_RESET, "]")


class CMSExporter(FolderFormatExporter):
    """CMS exporter implementation"""

    def __init__(self, formatter: Formatter, context: TMTContext, output_path: str):
        super().__init__(output_path)
        self.setup_operations(formatter, context)

    def construct_problem_json(self, context: TMTContext):
        task_type_params = {}
        if context.config.problem_type == ProblemType.BATCH:
            task_type_params["task_type_parameters_Batch_compilation"] = "grader"
        elif context.config.problem_type == ProblemType.COMMUNICATION:
            task_type_params["task_type_parameters_Communication_num_processes"] = (
                context.config.solution.num_procs
            )

        problem_json = {}
        problem_json["code"] = context.config.short_name
        problem_json["name"] = context.config.title
        problem_json["feedback_level"] = "oi_restricted"

        if context.config.problem_type == ProblemType.BATCH:
            problem_json["task_type"] = "Batch"
        elif context.config.problem_type == ProblemType.COMMUNICATION:
            problem_json["task_type"] = "Communication"
        elif context.config.problem_type == ProblemType.OUTPUT_ONLY:
            problem_json["task_type"] = "OutputOnly"

        problem_json["score_precision"] = 2
        problem_json["time_limit"] = context.config.solution.time_limit_sec
        problem_json["memory_limit"] = context.config.solution.memory_limit_bytes
        problem_json["task_type_params"] = json.dumps(task_type_params)
        return json.dumps(problem_json)

    def enforce_file_ext(self, ext: str):
        if not ext.startswith("."):
            raise ValueError("enforce_file_ext: ext must start with a dot.")

        def rename_func(_f, _c, filename: Path, _s):
            return os.path.splitext(filename)[0] + ext

        return rename_func

    def filter_graders(self):
        def rename_func(_f, context: TMTContext, filename: Path, _s):

            filebase, fileext = os.path.splitext(os.path.basename(filename))
            if filebase == context.config.solution.grader_name:
                for lang in languages.languages:
                    if fileext in lang(context).source_extensions:
                        return "grader" + lang.source_extensions[0]
            return filename

        return rename_func

    def setup_operations(self, formatter: Formatter, context: TMTContext):
        assert context.config.judge_convention == JudgeConvention.CMS

        self.operations.append(
            DumpFileOperation("problem.json", self.construct_problem_json(context))
        )
        self.add_regex_copy_operation(
            rf"^testcases/.*{re.escape(context.config.input_extension)}$",
            "tests",
            rename_func=self.enforce_file_ext(".in"),
        )
        self.add_regex_copy_operation(
            rf"^testcases/.*{re.escape(context.config.output_extension)}$",
            "tests",
            rename_func=self.enforce_file_ext(".out"),
        )
        self.add_regex_copy_operation(r"^statement/.*\.pdf$", "statements")

        if context.config.checker and context.config.checker.type == CheckerType.CUSTOM:
            if (
                recognize_language([context.config.checker.filename], context)
                != languages.LanguageCpp
            ):
                raise ValueError(
                    "Checker must be written in C++ to accomodate the TPS importer."
                )
            self.add_copy_operation(
                f"checker/{context.config.checker.filename}", "checker/checker.cpp"
            )
            self.add_regex_copy_operation(r"^include/.*", "checker")

        if context.config.manager:
            if (
                recognize_language([context.config.manager.filename], context)
                != languages.LanguageCpp
            ):
                raise ValueError(
                    "Manager must be written in C++ to accomodate the TPS importer."
                )
            self.add_copy_operation(
                f"manager/{context.config.manager.filename}", "graders/manager.cpp"
            )
            self.add_regex_copy_operation(r"^include/.*", "graders")

        if context.config.solution.grader_name:
            self.add_regex_copy_operation(
                r"^graders/.*",
                "graders",
                rename_func=self.filter_graders(),
            )

        self.add_copy_operation(
            f"public/{context.config.short_name}.zip",
            f"attachments/{context.config.short_name}.zip",
        )

        subtask_id = 0
        subtask_id_width = len(str(len(context.recipe.subtasks) - 1))
        for subtask in context.recipe.subtasks.values():
            subtask_json = json.dumps(
                {"score": subtask.score, "testcases": subtask.get_all_test_names()}
            )
            self.operations.append(
                DumpFileOperation(
                    f"subtasks/{str(subtask_id).zfill(subtask_id_width)}-{subtask.name}.json",
                    subtask_json,
                )
            )
            subtask_id += 1

        # TODO: attachments
