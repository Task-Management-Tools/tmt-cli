import errno
import os
import re
import enum
import glob
import dataclasses
from pathlib import Path
from collections import defaultdict
from abc import ABC, abstractmethod
from typing import Callable, BinaryIO

from internal.zip_handler import ZipFileHander
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
    target_compressed: str | None = None
    msg: str = ""


class ExportOperation(ABC):
    """Base class for different types of export operations."""

    @classmethod
    def format_os_errors(cls, err_list: list[OSError], context: TMTContext):
        err_dict: dict[int, list[OSError]] = defaultdict(list)
        for err in err_list:
            err_dict[err.errno].append(err)

        err_strs = []
        for err_no, errs in err_dict.items():
            files = [
                str(
                    path.relative_to(context.path.problem_dir)
                    if path.is_absolute()
                    else path
                )
                for err in errs
                if err.filename and (path := Path(err.filename))
            ]
            files = list(dict.fromkeys(files))

            suffix = f": {', '.join(files)}" if files else ""
            err_strs.append(os.strerror(err_no) + suffix)

        return "; ".join(err_strs)

    @classmethod
    def result_from_os_errors(cls, err_list: list[OSError], context: TMTContext):
        return ExportResult(
            ExportResultEnum.FAILURE, msg=cls.format_os_errors(err_list, context)
        )

    @property
    @abstractmethod
    def target_name(self) -> str:
        """The name of the export operation."""
        pass

    @abstractmethod
    def execute(self, context: TMTContext, zipfile: ZipFileHander) -> ExportResult:
        """Execute the export operation."""
        pass


@dataclasses.dataclass
class CopyFileOperation(ExportOperation):
    name: str
    src: str
    dst: str

    @property
    def target_name(self) -> str:
        return self.name

    def execute(self, context: TMTContext, zipfile: ZipFileHander):
        source = Path(context.path.problem_dir) / self.src

        try:
            zipfile.write_file(self.dst, source)
        except OSError as e:
            return self.result_from_os_errors([e], context)

        return ExportResult(ExportResultEnum.SUCCESS, target_list=[self.src])


@dataclasses.dataclass
class CopyTestcaseOperation(ExportOperation):
    name: str
    codenames: list[str]
    dst: str
    ext_mapping: dict[str, str]

    @property
    def target_name(self) -> str:
        return self.name

    def execute(self, context: TMTContext, zipfile: ZipFileHander):
        errs: list[OSError] = []
        missing = []

        for codename in self.codenames:
            for orig_ext, target_ext in self.ext_mapping.items():
                source = Path(context.path.testcases) / (codename + orig_ext)
                target = Path(self.dst) / (codename + target_ext)

                # try to identify missing files, since it makes more sense
                # to report for each codename instead of each file
                if not source.exists():
                    if not missing or missing[-1] != codename:
                        missing.append(codename)

                try:
                    zipfile.write_file(target, source)
                except OSError as e:
                    errs.append(e)

        if missing and all(err.errno == errno.ENOENT for err in errs):
            return ExportResult(
                ExportResultEnum.FAILURE,
                msg=f"Missing testcases: {', '.join(missing)}",
            )
        elif errs:
            return self.result_from_os_errors(errs, context)
        elif len(self.codenames) == 0:
            return ExportResult(ExportResultEnum.WARNING, msg="No testcase matches")
        else:
            # This assumption is based on the testcase naming...
            self.codenames.sort()
            testsets = defaultdict(list)
            for codename in self.codenames:
                if "-" not in codename:
                    testsets[codename] = []
                else:
                    testset, _, index = codename.rpartition("-")
                    testsets[testset].append(index)
            target_compressed = ", ".join(
                f"{testset}-{{{','.join(indicies)}}}"
                if indicies
                else f"{testset}-{indicies[0]}"
                if len(indicies) == 1
                else testset
                for testset, indicies in testsets.items()
            )
            return ExportResult(
                ExportResultEnum.SUCCESS,
                target_list=self.codenames,
                target_compressed=target_compressed,
            )


class GlobCopyOperation(ExportOperation):
    """Copy files with a glob pattern; optionally filters by regex."""

    def __init__(
        self,
        name: str,
        glob_root: str,
        dst: str,
        *,
        recursive: bool = True,
        regex_pattern: str | None = None,
    ):

        self.name = name
        self.glob_root = Path(glob_root)
        self.dst = dst
        self.recursive = recursive
        self.regex_pat = (
            re.compile(regex_pattern) if regex_pattern is not None else None
        )

    @property
    def target_name(self) -> str:
        return self.name

    def execute(self, context: TMTContext, zipfile: ZipFileHander):
        # Find all matching files recursively
        matching_files: list[str] = []

        for file_path in glob.iglob(
            "**",
            root_dir=self.glob_root,
            include_hidden=True,
            recursive=self.recursive,
        ):
            full_path = self.glob_root / file_path
            if not full_path.is_file():
                continue
            if self.regex_pat is None or self.regex_pat.fullmatch(file_path):
                matching_files.append(file_path)

        if not matching_files:
            return ExportResult(ExportResultEnum.SKIPPED)

        exported_files: list[str] = []
        errs: list[OSError] = []

        for file_path in matching_files:
            source_file = self.glob_root / file_path
            target_file = Path(self.dst) / file_path
            try:
                zipfile.write_file(target_file, source_file)
                exported_files.append(str(target_file))
            except OSError as e:
                errs.append(e)

        if errs:
            return self.result_from_os_errors(errs, context)
        return ExportResult(ExportResultEnum.SUCCESS, target_list=exported_files)


class DumpFileOperation(ExportOperation):
    """Custom file processing operation"""

    def __init__(
        self,
        *,
        name: str | None = None,
        dst: str,
        src: str | Callable[[TMTContext, BinaryIO], ExportResult],
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

    def execute(self, context: TMTContext, zipfile: ZipFileHander):

        if hasattr(self, "content"):
            try:
                zipfile.write_str(self.dst, self.content)
            except OSError as e:
                return self.result_from_os_errors([e], context)
            return ExportResult(ExportResultEnum.SUCCESS, target_list=[self.dst])
        else:
            try:
                with zipfile.open(self.dst, "w") as f:
                    return self.func(context, f)
            except OSError as e:
                return self.result_from_os_errors([e], context)
