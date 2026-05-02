import shutil
from pathlib import Path
import tempfile
from abc import ABC, abstractmethod
from typing import Generator

from internal.formatting import Formatter
from internal.context import TMTContext

from .operations import ExportOperation, ExportResult, ExportResultEnum


class FolderFormatExporter(ABC):
    """Base class for folder format conversion"""

    def __init__(self, output_path: str):
        self.output_path = output_path

    @abstractmethod
    def setup_operations(
        self, context: TMTContext
    ) -> Generator[ExportOperation, None, None]:
        pass

    def export(
        self, formatter: Formatter, context: TMTContext, create_zip: bool = True
    ) -> bool:
        # TODO: it should generally return the result list, but it currently returns bool for convenicence
        """Export folder format"""

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
                    return False
                output_dir.mkdir()
            else:
                if Path(self.output_path).exists():
                    formatter.println(
                        formatter.ANSI_RED,
                        f"Error: path {self.output_path} already exists.",
                        formatter.ANSI_RESET,
                    )
                    return False
                output_dir = Path(temp_dir)

            # Execute all operations
            ops = list(self.setup_operations(context))
            name_length = max(len(operation.target_name) for operation in ops) + 2

            res_list: list[ExportResult] = []
            for operation in ops:
                formatter.print(" " * 4)
                formatter.print_fixed_width(operation.target_name, width=name_length)
                res = operation.execute(context, output_dir)

                match res.result:
                    case ExportResultEnum.SUCCESS:
                        color, text = formatter.ANSI_GREEN, "OK"
                    case ExportResultEnum.WARNING:
                        color, text = formatter.ANSI_YELLOW, "WARN"
                    case ExportResultEnum.SKIPPED:
                        color, text = formatter.ANSI_GREY, "SKIP"
                    case ExportResultEnum.FAILURE:
                        color, text = formatter.ANSI_RED, "FAIL"
                    case _:
                        raise ValueError(
                            f"export: Unknown ExportResultEnum {res.result}"
                        )

                formatter.print_fixed_width(
                    "[", color, text, formatter.ANSI_RESET, "]", width=8
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
                res_list.append(res)

            if any(res.result == ExportResultEnum.FAILURE for res in res_list):
                return False

            # Handle output
            if create_zip:
                formatter.println("Creating zip file...")
                with tempfile.NamedTemporaryFile() as temp_file:
                    shutil.make_archive(temp_file.name, "zip", output_dir)
                    shutil.copy2(temp_file.name + ".zip", self.output_path)

                formatter.println("Export completed.")
            else:
                formatter.println("Export completed.")

            return True
