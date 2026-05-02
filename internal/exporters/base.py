import shutil
from pathlib import Path
import tempfile

from internal.formatting import Formatter
from internal.context import TMTContext

from .operations import (
    ExportOperation,
    CopyFileOperation,
    RegexCopyOperation,
    ExportResultEnum,
)


class FolderFormatExporter:
    """Base class for folder format conversion"""

    def __init__(self, output_path: str):
        self.output_path = output_path
        self.operations: list[ExportOperation] = []

    def add_copy_operation(self, name: str, source_path: str, target_path: str) -> None:
        """Add a simple file copy operation"""
        operation = CopyFileOperation(name, source_path, target_path)
        self.operations.append(operation)

    def add_regex_copy_operation(
        self, name: str, pattern: str, target_folder: str, glob_hint: str | None = None
    ) -> None:
        """
        Add a regex-based file copy operation
        """
        self.operations.append(
            RegexCopyOperation(name, pattern, target_folder, glob_hint)
        )

    def export(
        self, formatter: Formatter, context: TMTContext, create_zip: bool = True
    ) -> None:
        """Export folder format"""

        name_length = (
            max(len(operation.target_name) for operation in self.operations) + 2
        )

        formatter.println(f"Exporting {self.output_path}...")

        # Create temporary directory for conversion
        with tempfile.TemporaryDirectory() as temp_dir:
            if not create_zip:
                output_dir = Path(self.output_path)
                if output_dir.exists():
                    formatter.println(
                        formatter.ANSI_RED,
                        f"Error: path {self.output_path} already exists.",
                        formatter.ANSI_RESET,
                    )
                    return
                output_dir.mkdir()
            else:
                if Path(self.output_path).exists():
                    formatter.println(
                        formatter.ANSI_RED,
                        f"Error: path {self.output_path} already exists.",
                        formatter.ANSI_RESET,
                    )
                    return
                output_dir = Path(temp_dir)

            # Execute all operations
            for operation in self.operations:
                formatter.print(" " * 4)
                formatter.print_fixed_width(operation.target_name, width=name_length)
                res = operation.execute(context, output_dir)
                match res.result:
                    case ExportResultEnum.SUCCESS:
                        formatter.print(
                            "[",
                            formatter.ANSI_GREEN,
                            "OK",
                            formatter.ANSI_RESET,
                            "]    ",
                        )
                    case ExportResultEnum.WARNING:
                        formatter.print(
                            "[",
                            formatter.ANSI_YELLOW,
                            "WARN",
                            formatter.ANSI_RESET,
                            "]  ",
                        )
                    case ExportResultEnum.SKIPPED:
                        formatter.print(
                            "[",
                            formatter.ANSI_GREY,
                            "SKIP",
                            formatter.ANSI_RESET,
                            "]  ",
                        )
                    case ExportResultEnum.FAILURE:
                        formatter.print(
                            "[", formatter.ANSI_RED, "FAIL", formatter.ANSI_RESET, "]  "
                        )

                # TODO: always expand full if verbose=true
                if len(res.target_list) > 8:
                    formatter.print(
                        ", ".join(res.target_list[:7])
                        + f", ..., {res.target_list[-1]} (total {len(res.target_list)})"
                    )
                else:
                    formatter.print(", ".join(res.target_list))
                formatter.print(res.msg)
                formatter.println()

            # Handle output
            if create_zip:
                formatter.println("Creating zip file...")
                with tempfile.NamedTemporaryFile() as temp_file:
                    shutil.make_archive(temp_file.name, "zip", output_dir)
                    shutil.copy2(temp_file.name + ".zip", self.output_path)

                formatter.println("Export completed.")
            else:
                formatter.println("Export completed.")
