import yaml
import re
from pathlib import Path
from typing import List

from internal.context.config import CheckerType, TMTConfig
from internal.formatting import Formatter
from internal.context import TMTContext
from internal.verify.verdicts_parser import ExpectedVerdict, parse_verdicts

from .base import FolderFormatExporter
from .operations import DumpFileOperation


class DOMJudgeLegacyExporter(FolderFormatExporter):
    """DOMjudge 8+ exporter implementation, based on ICPC legacy package format."""

    def __init__(self, formatter: Formatter, context: TMTContext, output_path: str):
        super().__init__(output_path)
        self.setup_operations(formatter, context)

    def yaml_builder(self, config: TMTConfig):

        output_yaml = {
            "problem_format_version": "legacy",
            "name": config.title,
            "author": "anonymous",  # TODO if we support author and licesing
            "license": "unknown",  # TODO
            "limits": {},
        }

        # Limits
        # we include this time_limit because DOMjudge 9.0+ parses this,
        # but it is not reliable in this format. DOMjudge 8.0+ uses .time_limit file.
        output_yaml["limits"]["time_limit"] = config.solution.time_limit_sec
        output_yaml["limits"]["memory"] = config.solution.memory_limit_mib
        output_yaml["limits"]["output"] = config.solution.output_limit_mib
        # remaining fields:
        # time_multiplier, time_safety_margin
        # compilation_time: 60
        # compilation_memory: 2048
        # validation_time: 60
        # validation_memory: 2048
        # validation_output: 8

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
                    # TODO properly emit error when it is implemented in tmt-export
                    raise ValueError(f"Unknown checker type: {config.checker.type}")

            if config.checker.arguments:
                output_yaml["validator_flags"] = " ".join(config.checker.arguments)

        return yaml.dump(output_yaml)

    def setup_operations(self, formatter: Formatter, context: TMTContext):
        """Setup conversion operations"""

        # Metadata -> problem.yaml
        self.operations.append(
            DumpFileOperation("problem.yaml", self.yaml_builder(context.config))
        )

        # Statements -> problem_statement/
        self.add_regex_copy_operation(r"^statement/.*\.pdf", "problem_statement")

        # Attachments... TODO

        # Test data -> data/sample/, data/secret/
        # in legacy package, only sample and secret can exist
        # TODO: hint (.hint), description (.desc), illustration (.png, .jpg, .jpeg, .svg)
        # TODO: interaction (.interaction)

        self.add_regex_copy_operation(
            rf"^testcases/[0-9]+-samples-[0-9]+\{context.config.input_extension}",
            "data/sample",
        )
        self.add_regex_copy_operation(
            rf"^testcases/[0-9]+-samples-[0-9]+\{context.config.output_extension}",
            "data/sample",
        )
        self.add_regex_copy_operation(
            rf"^testcases/(?![0-9]+-samples-[0-9]+).*\{context.config.input_extension}",
            "data/secret",
        )
        self.add_regex_copy_operation(
            rf"^testcases/(?![0-9]+-samples-[0-9]+).*\{context.config.output_extension}",
            "data/secret",
        )

        # Submissions -> submissions/
        verdicts = parse_verdicts(context)

        def recognize_verdict(
            formatter: Formatter,
            context: TMTContext,
            matched_file: Path,
            supplementary_files: List[Path],
        ) -> str:
            verdicts_folder = "unknown"
            idx = matched_file.parts.index("solutions")
            file_name = Path(*matched_file.parts[idx + 1 :])

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

            for solution in verdicts:
                if solution.filename != str(file_name):
                    continue
                if solution.judge_verdict is not None:
                    # TODO: add warning for unknown judge verdict
                    verdicts_folder = solution.judge_verdict
                else:
                    wrong_verdict_count = 0
                    use_rejected = False
                    for verdict in solution.verdict.must:
                        if verdict in verdict_mapping:
                            verdicts_folder = verdict_mapping[verdict]
                        if verdict != ExpectedVerdict.ACCEPTED:
                            wrong_verdict_count += 1
                            if verdict not in verdict_mapping:
                                use_rejected = True
                    if wrong_verdict_count > 1 or use_rejected:
                        verdicts_folder = "rejected"

            return str(Path(verdicts_folder) / file_name)

        self.add_regex_copy_operation(
            r"^solutions/.*\..*",
            "submissions",
            rename_func=recognize_verdict,
            supplementary_files=["verdicts.yaml"],
        )

        # TODO: for input/output validators, the standard actually requires an executable
        # for these cases, we must
        # Validators -> input_validators/
        # TODO: quote
        # An input validator program must be an application (executable or interpreted) capable of being invoked with a command line call.
        # if necessary, hooks this to compile input_validators and copy the binaries.
        # TODO emit error when validators for specific testset presents; it is impossible under this format

        # Checker & Interactor -> output_validators/
        # export them only if config says so, add header if we do want that
        if context.config.checker.type is CheckerType.CUSTOM:
            self.add_regex_copy_operation(
                r"^checker/" + re.escape(context.config.checker.filename),
                "output_validators/",
            )
            self.add_regex_copy_operation(r"^include/.*", "output_validators/")
        if context.config.interactor:
            self.add_regex_copy_operation(
                r"^interactor/" + re.escape(context.config.interactor.filename),
                "output_validators/",
            )
            self.add_regex_copy_operation(r"^include/.*", "output_validators/")

        # DOMjudge extension: .timelimit works with version 7.0+ (maybe even earlier)
        # problem.yaml:limits.time_limit works only with version 9.0+, so this is always present as a fallback
        self.operations.append(
            DumpFileOperation(".timelimit", str(context.config.solution.time_limit_sec))
        )
