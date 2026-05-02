import re
import enum
import glob
import shutil
import dataclasses
from pathlib import Path
from abc import ABC, abstractmethod
from typing import Callable, TextIO

from internal.context import TMTContext


class ExportResultEnum(enum.Enum):
    SUCCESS = 0
    WARNING = 1
    SKIPPED = 2
    FAILURE = 3


@dataclasses.dataclass
class ExportResult:
    result: ExportResultEnum
    target_list: list[str] = dataclasses.field(default_factory=list)
    msg: str = ""


class ExportOperation(ABC):
    """Base class for different types of conversion operations"""

    @property
    @abstractmethod
    def target_name(self) -> None:
        """Execute the conversion operation"""
        pass

    @abstractmethod
    def execute(self, context: TMTContext, output_folder: Path) -> ExportResult:
        """Execute the conversion operation"""
        pass


class CopyFileOperation(ExportOperation):
    """Simple file copy operation"""

    def __init__(self, name: str, source_path: str, target_path: str):
        self.name = name
        self.source_path = source_path
        self.target_path = target_path

    @property
    def target_name(self) -> str:
        return self.name

    def execute(self, context: TMTContext, output_folder: Path):
        source = Path(context.path.problem_dir) / Path(self.source_path)
        target = output_folder / Path(self.target_path)

        # Ensure target directory exists
        target.parent.mkdir(parents=True, exist_ok=True)

        if source.exists():
            shutil.copy2(source, target)
            return ExportResult(
                ExportResultEnum.SUCCESS, target_list=[self.source_path]
            )
        else:
            return ExportResult(ExportResultEnum.WARNING)
            f"Source {self.source_path} does not exist"


class CopyFilelistOperation(ExportOperation):
    def __init__(
        self,
        name: str,
        source_lists: list[str],
        target_dir: str,
        rename_func: Callable[[str], str] = lambda x: x,
    ):
        self.name = name
        self.source_lists = source_lists
        self.target_dir = target_dir
        self.rename_func = rename_func

    @property
    def target_name(self) -> str:
        return self.name

    def execute(self, context: TMTContext, output_folder: Path):
        missing_srcs: list[str] = []
        for source_path in self.source_lists:
            source = Path(context.path.problem_dir) / Path(source_path)
            target = (
                output_folder / Path(self.target_dir) / self.rename_func(source_path)
            )
            if not source.exists():
                missing_srcs.append(source)
                continue

            # Ensure target directory exists
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

        if len(missing_srcs):
            return ExportResult(
                ExportResultEnum.FAILURE,
                msg=f"Source {', '.join(missing_srcs)} does not exist",
            )
        else:
            return ExportResult(ExportResultEnum.SUCCESS, target_list=self.source_lists)


@dataclasses.dataclass
class CopyTestcaseOperation(CopyFilelistOperation):
    name: str
    codenames: list[str]
    target_dir: str
    ext_mapping: dict[str, str]

    @property
    def target_name(self) -> str:
        return self.name

    def execute(self, context: TMTContext, output_folder: Path):
        target_directory = output_folder / Path(self.target_dir)

        target_directory.mkdir(parents=True, exist_ok=True)
        missing_srcs: dict[str, list[str]] = {}
        for codename in self.codenames:
            for orig_ext, target_ext in self.ext_mapping.items():
                source = Path(context.path.testcases) / (codename + orig_ext)
                target = target_directory / (codename + target_ext)

                if not source.exists():
                    if codename not in missing_srcs:
                        missing_srcs[codename] = []
                    missing_srcs[codename].append(orig_ext)
                    continue

                shutil.copy2(source, target)

        if len(missing_srcs):
            return ExportResult(
                ExportResultEnum.FAILURE,
                msg=f"Testcases {', '.join(missing_srcs.keys())} are missing",
            )
        elif len(self.codenames) == 0:
            return ExportResult(ExportResultEnum.WARNING, msg="No testcase matches")
        else:
            return ExportResult(ExportResultEnum.SUCCESS, target_list=self.codenames)


class RegexCopyOperation(ExportOperation):
    """Copy files matching regex pattern"""

    def __init__(
        self, name: str, pattern: str, target_path: str, glob_hint: str | None
    ):
        self.name = name
        self.pattern = re.compile(pattern)
        self.target_path = target_path
        self.glob_hint = glob_hint

    @property
    def target_name(self) -> str:
        return self.name

    def execute(self, context: TMTContext, output_folder: Path):
        target_dir = output_folder / Path(self.target_path)
        target_dir.mkdir(parents=True, exist_ok=True)

        # Find all matching files recursively
        matching_files: list[Path] = []
        for file_path in glob.iglob(
            self.glob_hint or "**",
            root_dir=context.path.problem_dir,
            include_hidden=True,
            recursive=True,
        ):
            full_path = Path(context.path.problem_dir) / file_path
            if full_path.is_file() and self.pattern.fullmatch(file_path):
                matching_files.append(full_path.relative_to(context.path.problem_dir))

        if not matching_files:
            return ExportResult(ExportResultEnum.SKIPPED)
            "Cannot find any matched files"

        for file_path in matching_files:
            target_name = file_path.name

            target_file = target_dir / Path(target_name)
            target_file.parent.mkdir(parents=True, exist_ok=True)

            # Simple copy (ignoring supplementary files files in default behavior)
            shutil.copy2(file_path, target_file)

        return ExportResult(ExportResultEnum.SUCCESS)


class DumpFileOperation(ExportOperation):
    """Custom file processing operation"""

    def __init__(
        self,
        target_path: str,
        content: str | Callable[[TMTContext, TextIO], ExportResult],
    ):
        self.target_path = target_path
        if isinstance(content, str):
            self.content = content
        else:
            self.func = content

    @property
    def target_name(self) -> str:
        return self.target_path

    def execute(self, context: TMTContext, output_folder: Path):

        target = output_folder / Path(self.target_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        if hasattr(self, "content"):
            target.write_bytes(self.content.encode())
            return ExportResult(ExportResultEnum.SUCCESS)
        else:
            with target.open("w") as f:
                return self.func(context, f)
