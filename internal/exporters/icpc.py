import yaml
from pathlib import Path
from typing import List, IO

from internal.formatting import Formatter
from internal.context import TMTContext

from .base import FolderFormatExporter


def yaml_converter(
    formatter: Formatter, context: TMTContext, source_files: List[Path], output_file: IO
) -> None:
    """
    source_files: [proble_yaml]
    """
    output_yaml = {
        "problem_format_version": "2023-07-draft",
        "name": context.config.short_name,
        "author": "anonymous",  # TODO?
        "license": "cc by-sa",  # TODO?
        "limits": {},
    }

    """Setup limits"""
    # time_multipliers:
    #  ac_to_time_limit: 2.0
    #  time_limit_to_tle: 1.5
    output_yaml["limits"]["time_limit"] = context.config.solution.time_limit_sec
    output_yaml["limits"]["memory"] = context.config.solution.memory_limit_mib
    # time_resolution: 1.0
    output_yaml["limits"]["output"] = context.config.solution.output_limit_mib
    # code: 128
    # compilation_time: 60
    # compilation_memory: 2048
    # validation_time: 60
    # validation_memory: 2048
    # validation_output: 8

    """Setup validation"""
    if context.config.checker:
        command = str(context.config.checker.type)
        if context.config.checker.arguments:
            command += " ".join(context.config.checker.arguments)
        output_yaml["validation"] = command
    elif context.config.interactor:
        output_yaml["validation"] = "custom interactive"

    yaml.dump(output_yaml, output_file, sort_keys=False)


class ICPCExporter(FolderFormatExporter):
    """ICPC exporter implementation"""

    def __init__(self, formatter: Formatter, context: TMTContext, output_path: str):
        super().__init__(output_path)
        self.setup_operations(formatter, context)

    def setup_operations(self, formatter: Formatter, context: TMTContext):
        """Setup conversion operations"""

        """Setup problem config file"""
        self.add_custom_operation(["problem.yaml"], "problem.yaml", yaml_converter)

        """Setup statement"""
        self.add_regex_copy_operation(r"^statement/.*\.pdf", "problem_statement")

        """Setup submissions"""

        def recognize_verdict(
            formatter: Formatter,
            context: TMTContext,
            matched_file: Path,
            supplementary_files: List[Path],
        ) -> str:
            verdicts_folder = "unknown"
            idx = matched_file.parts.index("solutions")
            file_name = Path(*matched_file.parts[idx + 1 :])
            try:
                with open(supplementary_files[0], "r") as file:
                    verdicts = yaml.safe_load(file)
            except Exception:
                verdicts = {}

            for file in verdicts:
                if "filename" not in file or "verdict" not in file:
                    continue
                if str(file["filename"]) == str(file_name):
                    if isinstance(file["verdict"], list):
                        verdicts_folder = file["verdict"][0]
                    else:
                        verdicts_folder = file["verdict"]
            return Path(verdicts_folder) / file_name

        self.add_regex_copy_operation(
            r"^solutions/.*\..*",
            "submissions",
            keep_original_name=False,
            rename_func=recognize_verdict,
            supplementary_files=["verdicts.yaml"],
        )

        """Setup output_validators"""
        self.add_regex_copy_operation(
            r"^checker/.*\.(?:cc|cpp)", "output_validators/cpp_validator"
        )
        self.add_regex_copy_operation(
            r"^interactor/.*\.(?:cc|cpp)", "output_validators/cpp_validator"
        )

        """Setup data"""
        self.add_regex_copy_operation(
            rf"^testcases/[0-9]+_samples_[0-9]+\{context.config.input_extension}", "data/sample"
        )
        self.add_regex_copy_operation(
            rf"^testcases/[0-9]+_samples_[0-9]+\{context.config.output_extension}",
            "data/sample",
        )
        self.add_regex_copy_operation(
            rf"^testcases/(?![0-9]+_samples_[0-9]+).*\{context.config.input_extension}",
            "data/secret",
        )
        self.add_regex_copy_operation(
            rf"^testcases/(?![0-9]+_samples_[0-9]+).*\{context.config.output_extension}",
            "data/secret",
        )

        """Setup include headers"""
        """It is hard to detect required headers, so we copy all of them to all possible directories"""
        self.add_regex_copy_operation(
            r"^include/.*\.(?:h|hpp)", "output_validators/cpp_validator"
        )
