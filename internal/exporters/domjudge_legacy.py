import errno
import re
import yaml
import os
from pathlib import Path
from typing import BinaryIO

from internal.zip_handler import ZipFileHander
from internal.context.config import CheckerType, JudgeConvention
from internal.compilation.languages import languages, LanguageCpp, LanguagePython3
from internal.context import TMTContext
from internal.verify.verdicts_parser import ExpectedVerdict, parse_verdicts

from .base import BaseExporter
from .operations import (
    CopyFileOperation,
    ExportErrorOperation,
    ExportOperation,
    DumpFileOperation,
    CopyTestcaseOperation,
    ExportResult,
    ExportResultEnum,
    GlobCopyOperation,
)


class DOMJudgeSubmissionsOperation(ExportOperation):
    """
    Recognizes submission verdicts and remaps submission to appropriate subdirectory.
    This class is based on ICPC legacy format with DOMjudge extensions.
    """

    verdict_mapping = {
        ExpectedVerdict.ACCEPTED: "accepted",
        ExpectedVerdict.WRONG_ANSWER: "wrong_answer",
        ExpectedVerdict.TIME_LIMIT_EXCEEDED: "time_limit_exceeded",
        ExpectedVerdict.RUNTIME_ERROR: "run_time_error",
        # in legacy format, there is no other possibilties;
        # however, DOMjudge 8.2 supports additional verdicts, so we use this extra one
        # all other wrong submissions falls to rejected as in ICPC 2025-09 format.
        # TODO: when no-output is in expected verdict, add it here
        ExpectedVerdict.OUTPUT_LIMIT: "output_limit",
    }

    def __init__(self):
        pass

    @property
    def target_name(self) -> str:
        return "Submissions"

    def execute(self, context: TMTContext, zipfile: ZipFileHander):
        try:
            verdicts = parse_verdicts(context)
        except (
            Exception
        ) as e:  # TODO: fix parse_verdicts so it raises predictable exceptions
            return ExportResult(
                ExportResultEnum.FAILURE,
                msg=f"Error when parsing verdicts.yaml: {e}",
            )

        mappings = []
        missing = []
        unknown_judge_verdict = []
        errs: list[OSError] = []
        files: set[str] = set()

        for entry in verdicts:
            verdicts_folder = "unknown"
            if entry.judge_verdict is not None:
                verdicts_folder = entry.judge_verdict
                if entry.judge_verdict not in self.verdict_mapping:
                    unknown_judge_verdict.append(entry.filename)
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

            # flatten the directory
            # TODO: for multi-file submissions, it should not flatten all of them;
            # but it is currently not supported
            final_filename = base = os.path.basename(entry.filename)
            i = 2
            while final_filename in files:
                final_filename = f"{base}-{i}"
                i += 1

            if final_filename == entry.filename:
                mappings.append(entry.filename)
            else:
                mappings.append(f"{entry.filename} -> {final_filename}")

            original_path = Path(context.path.solutions) / entry.filename
            target_path = Path("submissions") / verdicts_folder / final_filename

            if not original_path.exists():
                missing.append(entry.filename)

            try:
                zipfile.write_file(target_path, original_path)
            except OSError as e:
                print(errs)
                errs.append(e)

        if missing and all(err.errno == errno.ENOENT for err in errs):
            return ExportResult(
                ExportResultEnum.FAILURE,
                msg=f"Missing solutions: {', '.join(missing)}",
            )
        if errs:
            self.result_from_os_errors(errs, context)
        if unknown_judge_verdict:
            return ExportResult(
                ExportResultEnum.WARNING,
                msg="Unknown judge verdict: " + ", ".join(unknown_judge_verdict),
            )
        return ExportResult(ExportResultEnum.SUCCESS, msg=", ".join(mappings))


class DOMJudgeLegacyExporter(BaseExporter):
    description = "DOMjudge 8+ package format, based on ICPC legacy format"

    def yaml_builder(self, context: TMTContext, f: BinaryIO) -> ExportResult:
        """Builds ICPC legacy format problem.yaml"""

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

        yaml.dump(output_yaml, stream=f, encoding="utf-8")
        return ExportResult(ExportResultEnum.SUCCESS)

    def setup_operations(self, context: TMTContext):
        if context.config.judge_convention is not JudgeConvention.ICPC:
            # TODO: DOMjudge's design actually makes it possible to export CMS package format with build and run script
            # implement this when it is relevant
            yield ExportErrorOperation(
                name="Judge convention check",
                msg="DOMjudge legacy exporter only supports ICPC judge convention",
            )
            return

        # Metadata -> problem.yaml
        yield DumpFileOperation(src=self.yaml_builder, dst="problem.yaml")
        # DOMjudge extension: .timelimit works with version 7.0+ (maybe even earlier)
        # problem.yaml:limits.time_limit works only with version 9.0+, so this is always present as a fallback

        yield DumpFileOperation(
            src=str(context.config.solution.time_limit_sec), dst=".timelimit"
        )

        # Statements -> problem_statement/
        yield GlobCopyOperation(
            "Problem statements",
            context.path.statement,
            "problem_statement",
            regex_pattern=r".*\.pdf",
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
            dst="data/sample",
            ext_mapping={
                context.config.input_extension: ".in",
                context.config.output_extension: ".ans",
            },
        )
        yield CopyTestcaseOperation(
            name="Test cases: hidden",
            codenames=hidden,
            dst="data/secret",
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
        yield GlobCopyOperation(
            "Input validators",
            context.path.validator,
            "input_validators/",
            regex_pattern=rf".*(?:{all_exts_re})",
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
            yield GlobCopyOperation(
                "Checker headers", context.path.include, "output_validators/"
            )
        if context.config.interactor:
            yield CopyFileOperation(
                "Interactor",
                "interactor/" + context.config.interactor.filename,
                "output_validators/" + context.config.interactor.filename,
            )
            yield GlobCopyOperation(
                "Interactor headers", context.path.include, "output_validators/"
            )
