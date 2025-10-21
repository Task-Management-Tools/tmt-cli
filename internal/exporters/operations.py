import re
import shutil
from pathlib import Path
from abc import ABC, abstractmethod
from typing import Callable, List, Optional, IO

from internal.formatting import Formatter
from internal.context import TMTContext


class ConversionOperation(ABC):
    """Base class for different types of conversion operations"""

    @abstractmethod
    def execute(
        self, formatter: Formatter, context: TMTContext, output_folder: Path
    ) -> None:
        """Execute the conversion operation"""
        pass


class CopyFileOperation(ConversionOperation):
    """Simple file copy operation"""

    def __init__(self, source_path: str, target_path: str):
        self.source_path = source_path
        self.target_path = target_path

    def target_name(self) -> str:
        return self.target_path

    def execute(
        self, formatter: Formatter, context: TMTContext, output_folder: Path
    ) -> None:
        source = Path(context.path.problem_dir) / Path(self.source_path)
        target = output_folder / Path(self.target_path)

        # Ensure target directory exists
        target.parent.mkdir(parents=True, exist_ok=True)

        if source.exists():
            shutil.copy2(source, target)
            formatter.println(
                "[", formatter.ANSI_GREEN, "OK", formatter.ANSI_RESET, "]"
            )
        else:
            formatter.println(
                "[",
                formatter.ANSI_YELLOW,
                "WARN",
                formatter.ANSI_RESET,
                "]",
                f" Source {self.source_path} does not exist",
            )


class CustomFileOperation(ConversionOperation):
    """Custom file processing operation"""

    def __init__(
        self,
        source_paths: List[str],
        target_path: str,
        processor_func: Callable[[Formatter, TMTContext, List[Path], IO], None],
    ):
        self.source_paths = source_paths
        self.target_path = target_path
        self.processor_func = processor_func

    def target_name(self) -> str:
        return self.target_path

    def execute(
        self, formatter: Formatter, context: TMTContext, output_folder: Path
    ) -> None:
        source_files = []
        for path in self.source_paths:
            source_file = Path(context.path.problem_dir) / Path(path)
            if source_file.exists():
                source_files.append(source_file)
            else:
                formatter.println(
                    "[",
                    formatter.ANSI_YELLOW,
                    "WARN",
                    formatter.ANSI_RESET,
                    "]",
                    f" Source {path} does not exist",
                )
                return

        target = output_folder / Path(self.target_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        with open(target, "w") as output_file:
            self.processor_func(formatter, context, source_files, output_file)
        formatter.println("[", formatter.ANSI_GREEN, "OK", formatter.ANSI_RESET, "]")


class RegexCopyOperation(ConversionOperation):
    """Copy files matching regex pattern"""

    def __init__(
        self,
        pattern: str,
        target_path: str,
        keep_original_name: bool = True,
        rename_func: Optional[
            Callable[[Formatter, TMTContext, Path, List[Path]], str]
        ] = None,
        custom_func: Optional[
            Callable[[Formatter, TMTContext, Path, List[Path], IO], None]
        ] = None,
        supplementary_files: Optional[List[str]] = None,
    ):
        self.pattern = re.compile(pattern)
        self.target_path = target_path
        self.keep_original_name = keep_original_name
        self.rename_func = rename_func
        self.custom_func = custom_func
        self.supplementary_files = supplementary_files or []

    def target_name(self) -> str:
        return self.target_path + "/ (" + self.pattern.pattern + ")"

    def execute(
        self, formatter: Formatter, context: TMTContext, output_folder: Path
    ) -> None:
        target_dir = output_folder / Path(self.target_path)
        target_dir.mkdir(parents=True, exist_ok=True)

        # Find all matching files recursively
        matching_files = []
        for file_path in Path(context.path.problem_dir).rglob(
            "*", recurse_symlinks=True
        ):
            if file_path.is_file() and self.pattern.search(
                str(file_path.relative_to(context.path.problem_dir))
            ):
                matching_files.append(file_path)

        if not matching_files:
            formatter.println(
                "[",
                formatter.ANSI_YELLOW,
                "WARN",
                formatter.ANSI_RESET,
                "]",
                " Cannot find any matched files",
            )
            return

        # Collect supplementary source files
        supplementary_files = []
        for source_path in self.supplementary_files:
            source_file = Path(context.path.problem_dir) / Path(source_path)
            if source_file.exists():
                supplementary_files.append(source_file)
            else:
                formatter.println(
                    "[",
                    formatter.ANSI_YELLOW,
                    "WARN",
                    formatter.ANSI_RESET,
                    "]",
                    f" Supplementary file {source_path} does not exist",
                )
                return

        for file_path in matching_files:
            if self.keep_original_name:
                target_name = file_path.name
            else:
                if self.rename_func:
                    target_name = self.rename_func(
                        formatter, context, file_path, supplementary_files
                    )
                else:
                    target_name = file_path.name

            target_file = target_dir / Path(target_name)
            target_file.parent.mkdir(parents=True, exist_ok=True)

            if self.custom_func:
                with open(target_file, "w") as output_file:
                    self.custom_func(
                        formatter,
                        context,
                        file_path,
                        supplementary_files,
                        output_file,
                    )
            else:
                # Simple copy (ignoring supplementary files files in default behavior)
                shutil.copy2(file_path, target_file)

        formatter.println("[", formatter.ANSI_GREEN, "OK", formatter.ANSI_RESET, "]")


class ExternalFileOperation(ConversionOperation):
    """Copy external files (not from input folder)"""

    def __init__(self, external_path: str, target_path: str):
        self.external_path = Path(external_path)
        self.target_path = target_path

    def target_name(self) -> str:
        return self.target_path

    def execute(
        self, formatter: Formatter, context: TMTContext, output_folder: Path
    ) -> None:
        target = output_folder / Path(self.target_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        if self.external_path.exists():
            if self.external_path.is_file():
                shutil.copy2(self.external_path, target)
            elif self.external_path.is_dir():
                shutil.copytree(self.external_path, target, dirs_exist_ok=True)
            formatter.println(
                "[", formatter.ANSI_GREEN, "OK", formatter.ANSI_RESET, "]"
            )
        else:
            formatter.println(
                "[",
                formatter.ANSI_YELLOW,
                "WARN",
                formatter.ANSI_RESET,
                "]",
                f" Source {self.external_path} does not exist",
            )
