import glob
import json
import os
from pathlib import Path
import shutil

from internal.compilation import languages, recognize_language
from internal.context.config import (
    CheckerType,
    JudgeConvention,
    ProblemType,
    SolutionType,
    TMTConfig,
)
from internal.context import TMTContext

from .base import FolderFormatExporter
from .operations import (
    CopyFileOperation,
    CopyTestcaseOperation,
    DumpFileOperation,
    ExportOperation,
    ExportResult,
    ExportResultEnum,
    RegexCopyOperation,
)


class GraderExportOperation(ExportOperation):
    """Base class for different types of conversion operations"""

    @property
    def target_name(self) -> None:
        return "Graders"

    def execute(self, context: TMTContext, output_folder: Path) -> ExportResult:
        if context.config.solution.type is not SolutionType.GRADER:
            return ExportResult(ExportResultEnum.SKIPPED)

        graders = []
        for file_path in glob.iglob(
            "graders/*",
            root_dir=context.path.problem_dir,
            include_hidden=True,
            recursive=True,
        ):
            if os.path.splitext(file_path)[0] != context.config.solution.grader_name:
                continue

            lang = recognize_language([file_path], context)
            if lang is not None:
                full_path = Path(context.path.problem_dir) / file_path
                target_file = "graders/grader" + lang(context).source_extensions[0]
                target_path = output_folder / target_file
                target_path.parent.mkdir(parents=True, exist_ok=True)

                shutil.copy2(full_path, target_path)
                graders.append(lang(context).source_extensions[0])

        if len(graders) == 0:
            return ExportResult(ExportResultEnum.FAILURE, msg="No graders found")
        else:
            return ExportResult(ExportResultEnum.SUCCESS, target_list=graders)


class SubtaskConfigExportOperation(ExportOperation):
    """Base class for different types of conversion operations"""

    @property
    def target_name(self) -> None:
        return "Subtask configs"

    def execute(self, context: TMTContext, output_folder: Path) -> ExportResult:
        subtasks = context.recipe.subtasks.values()
        id_width = len(str(len(subtasks) - 1))

        file_list = []
        for id, subtask in enumerate(subtasks, 0):
            json_name = f"subtasks/{str(id).zfill(id_width)}-{subtask.name}.json"
            json_full_path = output_folder / json_name
            json_full_path.parent.mkdir(parents=True, exist_ok=True)
            with open(json_full_path, "w") as j:
                json.dump(
                    {"score": subtask.score, "testcases": subtask.get_all_test_names()},
                    j,
                )
            file_list.append(json_name)
        return ExportResult(ExportResultEnum.SUCCESS, target_list=file_list)


class CMSTPSExporter(FolderFormatExporter):
    """CMS TPS format exporter implementation"""

    def __init__(self, output_path: str):
        super().__init__(output_path)

    def construct_problem_json(self, config: TMTConfig):
        task_type_params = {}
        match config.problem_type:
            case ProblemType.BATCH:
                if config.solution.type == SolutionType.GRADER:
                    task_type_params["Batch_compilation"] = "grader"
                else:
                    task_type_params["Batch_compilation"] = "alone"

            case ProblemType.COMMUNICATION:
                task_type_params["Communication_num_processes"] = (
                    config.solution.num_procs
                )

            case ProblemType.OUTPUT_ONLY:
                pass

            case _:
                assert False, (
                    "construct_problem_json: Unknown problem type in CMS exporter"
                )
        task_type_params = {
            "task_type_parameters_" + k: v for k, v in task_type_params.items()
        }

        problem_json = {}
        problem_json["code"] = config.short_name
        problem_json["name"] = config.title
        problem_json["feedback_level"] = "oi_restricted"

        if config.problem_type == ProblemType.BATCH:
            problem_json["task_type"] = "Batch"
        elif config.problem_type == ProblemType.COMMUNICATION:
            problem_json["task_type"] = "Communication"
        elif config.problem_type == ProblemType.OUTPUT_ONLY:
            problem_json["task_type"] = "OutputOnly"

        problem_json["score_precision"] = 2
        problem_json["time_limit"] = config.solution.time_limit_sec
        problem_json["memory_limit"] = config.solution.memory_limit_bytes
        problem_json["task_type_params"] = json.dumps(task_type_params)
        return json.dumps(problem_json)

    def setup_operations(self, context: TMTContext):
        config = context.config
        assert config.judge_convention == JudgeConvention.CMS

        yield DumpFileOperation(
            src=self.construct_problem_json(config), dst="problem.json"
        )

        yield CopyTestcaseOperation(
            name="Test cases",
            codenames=context.recipe.get_all_test_names(),
            dst="tests",
            ext_mapping={
                config.input_extension: ".in",
                config.output_extension: ".out",
            },
        )

        yield RegexCopyOperation(
            "Problem statements",
            r"statement/.*\.pdf",
            "statements",
            "statement/*",
        )

        if config.checker and config.checker.type == CheckerType.CUSTOM:
            if (
                recognize_language([config.checker.filename], context)
                != languages.LanguageCpp
            ):
                raise ValueError(
                    "Checker must be written in C++ to accomodate the TPS importer."
                )
            yield CopyFileOperation(
                "Comparator",
                f"checker/{config.checker.filename}",
                "checker/checker.cpp",
            )
            yield RegexCopyOperation(
                "Comparator headers", r"include\/.*", "checker/", "include/**"
            )

        if config.manager:
            if (
                recognize_language([config.manager.filename], context)
                != languages.LanguageCpp
            ):
                raise ValueError(
                    "Manager must be written in C++ to accomodate the TPS importer."
                )
            yield CopyFileOperation(
                "Manager", f"manager/{config.manager.filename}", "graders/manager.cpp"
            )
            yield RegexCopyOperation(
                "Manager headers", r"include\/.*", "graders/", "include/**"
            )

        # TODO: report error when graders contain other files called manager.cpp
        # TODO: report warning/error when graders contain other in nested directory
        yield GraderExportOperation()
        # if context.config.solution.grader_name:
        #     self.add_regex_copy_operation(
        #         r"^graders/[^/]*",
        #         "graders",
        #         rename_func=self.filter_graders,
        #     )

        if Path(context.path.public_filelist).exists():
            yield CopyFileOperation(
                "Attachment",
                f"public/{config.short_name}.zip",
                f"attachments/{config.short_name}.zip",
            )

        yield SubtaskConfigExportOperation()
