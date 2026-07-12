import glob
import json
from pathlib import Path
from typing import Any

from internal.zip_handler import ZipFileHander
from internal.compilation import languages, recognize_language
from internal.context.config import (
    CheckerType,
    JudgeConvention,
    ProblemType,
    SolutionType,
    TMTConfig,
)
from internal.context import TMTContext

from .base import BaseExporter
from .operations import (
    CopyFileOperation,
    CopyTestcaseOperation,
    DumpFileOperation,
    ExportErrorOperation,
    ExportOperation,
    ExportResult,
    ExportResultEnum,
    GlobCopyOperation,
)


class GraderExportOperation(ExportOperation):
    """Exports grader and headers for TPS format."""

    @property
    def target_name(self) -> str:
        return "Graders"

    def execute(self, context: TMTContext, zipfile: ZipFileHander) -> ExportResult:
        if context.config.solution.type is not SolutionType.GRADER:
            return ExportResult(ExportResultEnum.SKIPPED)

        graders = []
        errs: list[OSError] = []

        for file_path in glob.iglob(
            "*",
            root_dir=context.path.graders,
        ):
            src = Path(context.path.graders) / file_path
            dst = Path("graders") / file_path
            if src.stem == context.config.solution.grader_name and (
                lang := recognize_language([str(src)], context)
            ):
                ext = lang(context).source_extensions[0]
                dst = Path("graders") / ("grader" + ext)

            try:
                zipfile.write_file(dst, src)
            except OSError as e:
                errs.append(e)
            graders.append(str(dst))

        if errs:
            return self.result_from_os_errors(errs, context)
        if not graders:
            return ExportResult(ExportResultEnum.FAILURE, msg="No graders found")
        return ExportResult(ExportResultEnum.SUCCESS, target_list=graders)


class SubtaskConfigExportOperation(ExportOperation):
    """Export subtask configs for TPS format."""

    @property
    def target_name(self) -> str:
        return "Subtask configs"

    def execute(self, context: TMTContext, zipfile: ZipFileHander) -> ExportResult:
        subtasks = context.recipe.subtasks.values()
        id_width = len(str(len(subtasks) - 1))

        file_list = []
        json_names = []
        errs: list[OSError] = []

        for id, subtask in enumerate(subtasks, 0):
            json_name = f"{str(id).zfill(id_width)}-{subtask.name}.json"
            json_path = Path("subtasks") / json_name

            # shouldn't take too much space, fine to do it in memory
            data = json.dumps(
                {"score": subtask.score, "testcases": subtask.get_all_test_names()}
            )
            try:
                with zipfile.open(json_path, "w") as f:
                    f.write(data.encode())
            except OSError as e:
                errs.append(e)

            file_list.append(str(json_path))
            json_names.append(json_name)

        if errs:
            return self.result_from_os_errors(errs, context)

        # target_compressed=f"subtasks/{{{','.join(json_names)}}}"
        return ExportResult(ExportResultEnum.SUCCESS, target_list=file_list)


class CMSTPSExporter(BaseExporter):
    description = "TPS export format for CMS"

    def construct_problem_json(self, config: TMTConfig):
        task_type_params: dict[str, Any] = {}
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

        problem_json: dict[str, Any] = {}
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
        if config.judge_convention is not JudgeConvention.CMS:
            yield ExportErrorOperation(
                name="Judge convention check",
                msg="CMS-TPS exporter only supports CMS judge convention",
            )
            return

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

        yield GlobCopyOperation(
            "Problem statements",
            context.path.statement,
            "statements",
            regex_pattern=r".*\.pdf",
            recursive=False,
        )

        if config.checker and config.checker.type == CheckerType.CUSTOM:
            assert config.checker.filename is not None
            checker_lang = recognize_language([config.checker.filename], context)
            if checker_lang is not languages.LanguageCpp:
                yield ExportErrorOperation(
                    "Comparator",
                    "Checker must be written in C++ to accomodate the TPS importer.",
                )
            else:
                yield CopyFileOperation(
                    "Comparator",
                    f"checker/{config.checker.filename}",
                    "checker/checker.cpp",
                )
                yield GlobCopyOperation(
                    "Comparator headers", context.path.include, "checker/"
                )

        if config.manager:
            manager_lang = recognize_language([config.manager.filename], context)
            if manager_lang is not languages.LanguageCpp:
                yield ExportErrorOperation(
                    "Manager",
                    "Manager must be written in C++ to accomodate the TPS importer.",
                )
            else:
                yield CopyFileOperation(
                    "Manager",
                    f"manager/{config.manager.filename}",
                    "graders/manager.cpp",
                )
                yield GlobCopyOperation(
                    "Manager headers", context.path.include, "graders/"
                )

        yield GraderExportOperation()

        if Path(context.path.public_filelist).exists():
            yield CopyFileOperation(
                "Attachment",
                f"public/{config.short_name}.zip",
                f"attachments/{config.short_name}.zip",
            )

        yield SubtaskConfigExportOperation()
