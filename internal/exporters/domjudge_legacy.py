import re
import shutil

import yaml
import os
from pathlib import Path
from typing import TextIO

from internal.context.config import CheckerType
from internal.compilation.languages import languages, LanguageCpp, LanguagePython3
from internal.context import TMTContext
from internal.verify.verdicts_parser import ExpectedVerdict, parse_verdicts

from .base import FolderFormatExporter
from .operations import (
    CopyFileOperation,
    ExportOperation,
    DumpFileOperation,
    CopyTestcaseOperation,
    ExportResult,
    ExportResultEnum,
    RegexCopyOperation,
)


class DOMJudgeSubmissionsOperation(ExportOperation):
    verdict_mapping = {
        ExpectedVerdict.RUNTIME_ERROR: "run_time_error",
        ExpectedVerdict.TIME_LIMIT_EXCEEDED: "time_limit_exceeded",
        ExpectedVerdict.WRONG_ANSWER: "wrong_answer",
        ExpectedVerdict.ACCEPTED: "accepted",
        # in legacy format, there is no other possibilties;
        # however, DOMjudge 8.2 supports additional verdicts, so we use this extra one
        # all other wrong submissions falls to rejected as in ICPC 2025-09 format.
        ExpectedVerdict.OUTPUT_LIMIT: "output_limit",
    }

    def __init__(self):
        pass

    @property
    def target_name(self) -> str:
        return "Submissions"

    def execute(self, context: TMTContext, output_folder: Path):
        verdicts = parse_verdicts(context)

        mappings = []
        missings = []
        files: set[str] = set()
        for entry in verdicts:
            verdicts_folder = "unknown"
            if entry.judge_verdict is not None:
                # TODO: add warning for unknown judge verdict
                verdicts_folder = entry.judge_verdict
            else:
                wrong_verdict_count = 0
                use_rejected = False
                for verdict in entry.verdict.must:
                    if verdict in self.verdict_mapping:
                        verdicts_folder = self.verdict_mapping[verdict]
                    else:
                        use_rejected = True

                    if verdict != ExpectedVerdict.ACCEPTED:
                        wrong_verdict_count += 1

                if wrong_verdict_count > 1 or use_rejected:
                    verdicts_folder = "rejected"

            # flatten the directory, if it does
            final_filename = os.path.basename(entry.filename)
            if final_filename in files:
                i = 2
                while f"{final_filename}-{i}" in files:
                    i += 1
                final_filename = f"{final_filename}-{i}"

            if final_filename == entry.filename:
                mappings.append(entry.filename)
            else:
                mappings.append(f"{entry.filename} -> {verdicts_folder}")

            original_path = Path(context.path.solutions) / entry.filename
            target_path = (
                output_folder / "submissions" / verdicts_folder / final_filename
            )

            if not original_path.exists():
                missings.append(entry.filename)
            else:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(original_path, target_path)

        if len(missings):
            return ExportResult(
                ExportResultEnum.WARNING,
                msg=f"Solutions {', '.join(missings)} not found",
            )
        return ExportResult(ExportResultEnum.SUCCESS, msg=", ".join(mappings))


class DOMJudgeLegacyExporter(FolderFormatExporter):
    """DOMjudge 8+ exporter implementation, based on ICPC legacy package format."""

    def __init__(self, output_path: str):
        super().__init__(output_path)

    def yaml_builder(self, context: TMTContext, f: TextIO) -> ExportResult:

        config = context.config
        output_yaml = {
            "problem_format_version": "legacy",
            "name": config.title,
            "author": "anonymous",  # TODO if we support author and licensing
            "license": "unknown",  # TODO
            "limits": {},
        }

        # Limits
        # we include this time_limit because DOMjudge 9.0+ parses this,
        # but it is not reliable in this format. DOMjudge 8.0+ uses .time_limit file.
        output_yaml["limits"]["time_limit"] = config.solution.time_limit_sec
        output_yaml["limits"]["memory"] = config.solution.memory_limit_mib
        output_yaml["limits"]["output"] = config.solution.output_limit_mib

        # Checker/Interactor
        # ICPC legacy format only allows:
        # default, custom (checker), custom interactive (interactive)
        if config.interactor:
            output_yaml["validation"] = "custom interactive"
        elif config.checker:
            match config.checker.type:
                case CheckerType.DEFAULT:
                    output_yaml["validation"] = "default"
                case CheckerType.CUSTOM:
                    output_yaml["validation"] = "custom"
                case _:
                    return ExportResult(
                        ExportResultEnum.FAILURE,
                        msg=f"Unknown checker type: {config.checker.type}",
                    )

            if config.checker.arguments:
                output_yaml["validator_flags"] = " ".join(config.checker.arguments)

        yaml.dump(output_yaml, stream=f)
        return ExportResult(ExportResultEnum.SUCCESS)

    def setup_operations(self, context: TMTContext):

        # Metadata -> problem.yaml
        yield DumpFileOperation("problem.yaml", self.yaml_builder)
        # DOMjudge extension: .timelimit works with version 7.0+ (maybe even earlier)
        # problem.yaml:limits.time_limit works only with version 9.0+, so this is always present as a fallback

        yield DumpFileOperation(
            ".timelimit", str(context.config.solution.time_limit_sec)
        )

        # Statements -> problem_statement/
        yield RegexCopyOperation(
            "Problem statements",
            r"statement/.*\.pdf",
            "problem_statement",
            "statement/*",
        )

        # Attachments... TODO

        # Test data -> data/sample/, data/secret/
        # in legacy package, only sample and secret can exist
        # TODO: hint (.hint), description (.desc), illustration (.png, .jpg, .jpeg, .svg)
        # TODO: interaction (.interaction)
        samples_testset = context.recipe.testsets.get("samples")
        samples = (
            [] if samples_testset is None else samples_testset.get_all_test_names()
        )
        hidden = context.recipe.get_all_test_names()
        for sample in samples:
            hidden.remove(sample)

        yield CopyTestcaseOperation(
            name="Test cases: samples",
            codenames=samples,
            target_dir="data/sample",
            ext_mapping={
                context.config.input_extension: ".in",
                context.config.output_extension: ".ans",
            },
        )
        yield CopyTestcaseOperation(
            name="Test cases: hidden",
            codenames=hidden,
            target_dir="data/secret",
            ext_mapping={
                context.config.input_extension: ".in",
                context.config.output_extension: ".ans",
            },
        )

        # Submissions -> submissions/
        yield DOMJudgeSubmissionsOperation()

        # Validators -> input_validators/
        # For input validators, the standard actually requires an executable,
        # but DOMjudge don't care, so we simply include the sources
        # TODO emit error when validators for specific testset presents; it is impossible under this format
        all_exts = sum(
            (lang(context).source_extensions for lang in languages), start=[]
        )
        all_exts_re = "|".join(re.escape(ext) for ext in all_exts)
        yield RegexCopyOperation(
            "Input validators",
            rf"validator/[^/]*(?:{all_exts_re})",
            "input_validators/",
            "validator/*",
        )

        # For output validators, the standard actually requires an executable,
        # but DOMjudge accepts C source (.c), C++ source (.cpp/.cc/.C), Java source (.java), and Python source (.py, .py2, .py3).
        # Thus, we export the source here and map file extension if required
        # These assertion ensures that we don't need to add remaps
        assert set([".cpp", ".cc", ".C"]).issuperset(
            LanguageCpp(context).source_extensions
        )
        assert set([".py", ".py2", ".py3"]).issuperset(
            LanguagePython3(context).source_extensions
        )

        # Checker & Interactor -> output_validators/
        # export them only if config says so, add header if we do want that
        if context.config.checker and context.config.checker.type is CheckerType.CUSTOM:
            yield CopyFileOperation(
                "Checker",
                "checker/" + context.config.checker.filename,
                "output_validators/" + context.config.checker.filename,
            )
            yield RegexCopyOperation(
                "Checker headers", r"include\/.*", "output_validators/", "include/**"
            )
        if context.config.interactor:
            yield CopyFileOperation(
                "Interactor",
                "interactor/" + context.config.interactor.filename,
                "output_validators/" + context.config.interactor.filename,
            )
            yield RegexCopyOperation(
                "Interactor headers", r"include\/.*", "output_validators/", "include/**"
            )
