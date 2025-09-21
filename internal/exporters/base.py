import shutil
from pathlib import Path
from typing import Callable, List, Optional, IO
import tempfile

from internal.formatting import Formatter
from internal.context import TMTContext

from .operations import (
    ConversionOperation,
    CopyFileOperation,
    CustomFileOperation,
    RegexCopyOperation,
    ExternalFileOperation,
)


class FolderFormatExporter:
    """Base class for folder format conversion"""

    def __init__(self, output_path: str):
        self.output_path = output_path
        self.operations: List[ConversionOperation] = []

    def add_copy_operation(self, source_path: str, target_path: str) -> None:
        """Add a simple file copy operation"""
        operation = CopyFileOperation(source_path, target_path)
        self.operations.append(operation)

    def add_custom_operation(
        self,
        source_paths: List[str],
        target_path: str,
        processor_func: Callable[[List[Path], IO], None],
    ) -> None:
        """Add a custom file processing operation"""
        operation = CustomFileOperation(source_paths, target_path, processor_func)
        self.operations.append(operation)

    def add_regex_copy_operation(
        self,
        pattern: str,
        target_folder: str,
        keep_original_name: bool = True,
        rename_func: Optional[Callable[[List[Path], List[Path]], str]] = None,
        custom_func: Optional[Callable[[List[Path], List[Path], IO], None]] = None,
        additional_sources: Optional[List[str]] = None,
    ) -> None:
        """
        Add a regex-based file copy operation

        Args:
            pattern: Regex pattern to match files
            target_folder: Target folder name
            keep_original_name: Whether to keep original filenames (ignored if rename_func provided)
            rename_func: Function that takes (matched_files, supplementary_files) and returns target filename
            custom_func: Function that takes (matched_files, supplementary_files, output_file)
            additional_sources: List of additional file paths from problem director to include
        """
        operation = RegexCopyOperation(
            pattern,
            target_folder,
            keep_original_name,
            rename_func,
            custom_func,
            additional_sources,
        )
        self.operations.append(operation)

    def add_external_file_operation(self, external_path: str, target_path: str) -> None:
        """Add an external file copy operation"""
        operation = ExternalFileOperation(external_path, target_path)
        self.operations.append(operation)

    def export(
        self, formatter: Formatter, context: TMTContext, create_zip: bool = True
    ) -> None:
        """Export folder format"""

        name_length = (
            max(len(operation.target_name()) for operation in self.operations) + 2
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
                formatter.print_fixed_width(operation.target_name(), width=name_length)
                operation.execute(formatter, context, output_dir)

            # Handle output
            if create_zip:
                formatter.println("Creating zip file...")
                with tempfile.NamedTemporaryFile() as temp_file:
                    shutil.make_archive(temp_file.name, "zip", output_dir)
                    shutil.copy2(temp_file.name + ".zip", self.output_path)

                formatter.println("Export completed.")
            else:
                formatter.println("Export completed.")
