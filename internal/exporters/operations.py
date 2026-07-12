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
    """
    Dataclass for holding result of each export operation.

    Attributes:
        result (ExportResultEnum): Overall outcome of this export operation.
        target_list (list[str]): A list containing all exported targets.
        target_compressed (str | None): An optional string representing the compressed list of the targets exported.
        msg (str): Extra message for export failures and warnings.
    """

    result: ExportResultEnum
    target_list: list[str] = dataclasses.field(default_factory=list)
    target_compressed: str | None = None
    msg: str = ""


class ExportOperation(ABC):
    """Base class for different types of export operations."""

    @classmethod
    def _format_os_errors(cls, err_list: list[OSError], context: TMTContext):
        """
        Formats a list of OSErrors into a list, based on their errno.

        Args:
            err_list (list[OSError]): A list of OSError to be formatted.
            context: (TMTContext): The current TMTContext for inferring path information.
        """
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
        """
        Forms a complete ExportResult indicating failure, with messages formatted from a list of OSErrors.
        This function calls :meth:`_format_os_errors` to produce the error message.

        Args:
            err_list (list[OSError]): A list of OSError to be formatted.
            context: (TMTContext): The current TMTContext for inferring path information.
        """
        return ExportResult(
            ExportResultEnum.FAILURE, msg=cls._format_os_errors(err_list, context)
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
    """
    Simply copy file export operation.

    Attributes:
        name (str): Display name of this operation.
        src (str | os.PathLike[str]): Source file. If it is a relative path, it is considered relative to the problem root.
        dst (str | os.PathLike[str]): Target file. It should always be a relative path.
    """

    name: str
    src: str | os.PathLike[str]
    dst: str | os.PathLike[str]

    @property
    def target_name(self) -> str:
        return self.name

    def execute(self, context: TMTContext, zipfile: ZipFileHander):
        source = Path(context.path.problem_dir) / self.src

        try:
            zipfile.write_file(self.dst, source)
        except OSError as e:
            return self.result_from_os_errors([e], context)

        return ExportResult(ExportResultEnum.SUCCESS, target_list=[os.fspath(self.src)])


@dataclasses.dataclass
class CopyTestcaseOperation(ExportOperation):
    """
    Copies test cases and remaps file extensions.

    Attributes:
        name (str): Display name of this operation.
        codenames (list[str]): A list of codenames of the test cases to be exported.
        dst (str | os.PathLike[str]): Target directory. It should always be a relative path.
        ext_mapping (dict[str, str]): A mapping contains all expected extensions and the exported extension.
    """

    name: str
    codenames: list[str]
    dst: str | os.PathLike[str]
    ext_mapping: dict[str, str]

    @property
    def target_name(self) -> str:
        return self.name

    def execute(self, context: TMTContext, zipfile: ZipFileHander):
        errs: list[OSError] = []
        missing: list[str] = []

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
            testsets: dict[str, list[str]] = defaultdict(list)
            for codename in self.codenames:
                if "-" not in codename:
                    testsets[codename] = []
                else:
                    testset, _, index = codename.rpartition("-")
                    testsets[testset].append(index)
            target_compressed = ", ".join(
                f"{testset}-{{{','.join(indicies)}}}"
                if len(indicies) >= 2
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
    """
    Copy files with a glob pattern; optionally filters by regex.

    Attributes:
        name (str): Display name of this operation.
        glob_root (str): An absolute path serve as the glob root.
        dst (str | os.PathLike[str]): Target directory. It should always be a relative path.
        recursive (str): Whether the glob should be recursive. Default True.
        regex_pattern (str | None): If provided, the globbed filename (everything after the glob_root) must match this regex to be exported.
    """

    def __init__(
        self,
        name: str,
        glob_root: str,
        dst: str | os.PathLike[str],
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
    """
    Dump a file into the exported archive.

    Attributes:
        name (str | None): Display name of this operation; if None, default to the filename.
        dst (str | os.PathLike[str]): Target file. It should always be a relative path.
        src (str | Callable[[TMTContext, BinaryIO], ExportResult]):
            If `src` is a string, it is dumped to the file.
            Otherwise, src must be a function taking tuple[TMTContext, BinaryIO] and returns a ExportResult.
            The operation will call this function to dump into the file, useful for lazily construct file contents and/or extra error handling.
    """

    def __init__(
        self,
        *,
        name: str | None = None,
        dst: str | os.PathLike[str],
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
        return str(self.name)

    def execute(self, context: TMTContext, zipfile: ZipFileHander):

        if hasattr(self, "content"):
            try:
                zipfile.write_str(self.dst, self.content)
            except OSError as e:
                return self.result_from_os_errors([e], context)
            return ExportResult(ExportResultEnum.SUCCESS, target_list=[str(self.dst)])
        else:
            try:
                with zipfile.open(self.dst, "w") as f:
                    return self.func(context, f)
            except OSError as e:
                return self.result_from_os_errors([e], context)


@dataclasses.dataclass
class ExportErrorOperation(ExportOperation):
    """
    Produce an error when executed.
    Useful for precondition failure, unabling to produce a meaningful export operation.

    Attributes:
        name (str): Display name of this operation.
        msg (str): The error message of the failure to be produced.
    """

    name: str
    msg: str

    @property
    def target_name(self) -> str:
        return self.name

    def execute(self, *args, **kwargs):
        return ExportResult(ExportResultEnum.FAILURE, msg=self.msg)
