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
    def target_name(self) -> str:
        """Execute the conversion operation"""
        pass

    @abstractmethod
    def execute(self, context: TMTContext, output_folder: Path) -> ExportResult:
        """Execute the conversion operation"""
        pass


@dataclasses.dataclass
class CopyFileOperation(ExportOperation):
    """Simple file copy operation"""

    name: str
    src: str
    dst: str

    @property
    def target_name(self) -> str:
        return self.name

    def execute(self, context: TMTContext, output_folder: Path):
        source = Path(context.path.problem_dir) / Path(self.src)
        target = output_folder / Path(self.dst)

        # Ensure target directory exists
        target.parent.mkdir(parents=True, exist_ok=True)

        if source.exists():
            shutil.copy2(source, target)
            return ExportResult(ExportResultEnum.SUCCESS, target_list=[self.src])

        return ExportResult(ExportResultEnum.FAILURE, msg=f"{self.src} does not exist")


@dataclasses.dataclass
class CopyTestcaseOperation(ExportOperation):
    name: str
    codenames: list[str]
    dst: str
    ext_mapping: dict[str, str]

    @property
    def target_name(self) -> str:
        return self.name

    def execute(self, context: TMTContext, output_folder: Path):
        target_directory = output_folder / Path(self.dst)

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

    def __init__(self, name: str, pattern: str, dst: str, glob_hint: str | None):
        self.name = name
        self.pattern = re.compile(pattern)
        self.dst = dst
        self.glob_hint = glob_hint

    @property
    def target_name(self) -> str:
        return self.name

    def execute(self, context: TMTContext, output_folder: Path):
        target_dir = output_folder / Path(self.dst)
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
        *,
        name: str | None = None,
        dst: str,
        src: str | Callable[[TMTContext, TextIO], ExportResult],
    ):
        self.dst = dst
        self.name = name or dst
        if isinstance(src, str):
            self.content = src
        else:
            self.func = src

    @property
    def target_name(self) -> str:
        return self.name

    def execute(self, context: TMTContext, output_folder: Path):

        target = output_folder / Path(self.dst)
        target.parent.mkdir(parents=True, exist_ok=True)

        if hasattr(self, "content"):
            target.write_bytes(self.content.encode())
            return ExportResult(ExportResultEnum.SUCCESS)
        else:
            with target.open("w") as f:
                return self.func(context, f)
