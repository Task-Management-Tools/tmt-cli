import dataclasses
import os
import re
import pathlib
import string
from typing import Callable, TextIO, BinaryIO
from zipfile import ZipFile

from internal.compilation import languages
from internal.context.config import ProblemType
from internal.formatting import Formatter
from internal.context import TMTContext
from internal.context import JudgeConvention


class SafeFormatter(string.Formatter):
    def get_value(self, key, args, kwargs):
        try:
            return super().get_value(key, args, kwargs)
        except (KeyError, AttributeError):
            return "{" + str(key) + "}"

    def get_field(self, field_name, args, kwargs):
        try:
            return super().get_field(field_name, args, kwargs)
        except (KeyError, AttributeError, IndexError, TypeError):
            raise ValueError(f"'{field_name}' is not a valid config attribute")


@dataclasses.dataclass
class ZipOperationResult:
    filename: str | None
    error: str | None = None
    warning: str | None = None


def check_duped_file(zipf: ZipFile, filename: str) -> tuple[bool, str | None]:
    """
    Returns a pair.
    The first component is True if the filename coincides with another file or directory, or any parent is already a file.
    The second component is the reason.

    Args:
        zipf: The file handler to the target zip archive.
        filename: The filename to be tested.
    """
    all_entries = zipf.infolist()

    # Directories end with '/'
    files = [e.filename for e in all_entries if not e.filename.endswith("/")]
    directories = sorted(
        {
            str(parent)
            for n in files
            for parent in pathlib.PurePosixPath(n).parents
            if str(parent) != "."
        }
    )

    if filename in files:
        return True, f"Filename {filename} already exists."
    if filename in directories:
        return True, f"Filename {filename} is a directory."
    while filename := os.path.split(filename)[0]:
        if filename in files:
            return True, f"Parent directory {filename} is a file."
    return False, ""


def raw_public(
    context: TMTContext, zipf: ZipFile, src: str, dest: str
) -> ZipOperationResult:
    """
    Copies the raw file into the zip archive.

    Args:
        context: The current TMTContext.
        zipf: The file handler to the target zip archive.
        src: The filename of the file to be copied, relative to the public directory.
        dest: The destination directory or filename in the target zip archive.
    """

    public_file = pathlib.Path(context.path.public) / src
    if dest.endswith("/") or not dest:
        dest += public_file.name
    if not public_file.exists():
        return ZipOperationResult(filename=dest, error=f"File public/{src} not found.")
    if not public_file.is_file():
        return ZipOperationResult(
            filename=dest, error=f"File public/{src} is not a file."
        )

    duped, reason = check_duped_file(zipf, dest)
    if duped:
        return ZipOperationResult(filename=dest, error=reason)

    with zipf.open(dest, "w") as zf:
        zf.write(public_file.read_bytes())

    return ZipOperationResult(filename=dest)


def format_public(
    context: TMTContext, zipf: ZipFile, src: str, dest: str
) -> ZipOperationResult:
    """
    Formats the file using the current TMTConfig and place it inside the zip archive.

    Args:
        context: The current TMTContext.
        zipf: The file handler to the target zip archive.
        src: The filename of the file to be fomatted, relative to the public directory.
        dest: The destination directory or filename in the target zip archive.
    """

    public_file = pathlib.Path(context.path.public) / src
    if dest.endswith("/") or not dest:
        dest += public_file.name
    if not public_file.exists():
        return ZipOperationResult(filename=dest, error=f"File public/{src} not found.")
    if not public_file.is_file():
        return ZipOperationResult(
            filename=dest, error=f"File public/{src} is not a file."
        )

    duped, reason = check_duped_file(zipf, dest)
    if duped:
        return ZipOperationResult(filename=dest, error=reason)

    try:
        with zipf.open(dest, "w") as zf:
            zf.write(
                SafeFormatter()
                .format(public_file.read_text(), config=context.config)
                .encode()
            )
    except ValueError as e:
        return ZipOperationResult(filename=dest, error=f"Format error: {e}")

    return ZipOperationResult(filename=dest)


def filter_secret(zf: BinaryIO, f: TextIO):
    hide = False
    improper = False
    for line in f.readlines():
        if re.match(r"BEGIN\s+SECRET", line):
            improper = improper or hide
            hide = True
        if not hide:
            zf.write(line.encode())
        if re.match(r"END\s+SECRET", line):
            improper = improper or not hide
            hide = False
    return improper or hide


def header_public(
    context: TMTContext, zipf: ZipFile, src: str, dest: str
) -> ZipOperationResult:

    public_file = pathlib.Path(context.path.graders) / src
    if dest.endswith("/") or not dest:
        dest += public_file.name
    if not public_file.exists():
        return ZipOperationResult(filename=dest, error=f"File graders/{src} not found.")
    if not public_file.is_file():
        return ZipOperationResult(
            filename=dest, error=f"File graders/{src} is not a file."
        )

    duped, reason = check_duped_file(zipf, dest)
    if duped:
        return ZipOperationResult(filename=dest, error=reason)

    # CMS logic
    with zipf.open(dest, "w") as zf, open(public_file, "r") as f:
        improper_filter = filter_secret(zf, f)

    if improper_filter:
        return ZipOperationResult(
            filename=dest, warning="BEGIN-END SECRET is not properly matched"
        )
    return ZipOperationResult(filename=dest)


def grader_public(
    context: TMTContext, zipf: ZipFile, lang_id: str, dest: str
) -> ZipOperationResult:
    lang = None
    for lang_type in languages.languages:
        if lang_type(context).id == lang_id:
            lang = lang_type(context)

    if lang is None:
        return ZipOperationResult(
            filename=None, error=f"'{lang_id}' is not a valid language ID."
        )

    grader = None
    for ext in lang.source_extensions:
        public_grader_path = pathlib.Path(context.path.graders) / (
            context.config.solution.grader_name + ext
        )
        if public_grader_path.exists() and public_grader_path.is_file():
            grader = public_grader_path
            break
    if grader is None:
        return ZipOperationResult(
            filename=None,
            error=f"Grader of language '{lang_id}' is not available in graders directory.",
        )

    grader_path = "grader" + lang.source_extensions[0]
    if dest.endswith("/") or not dest:
        dest += grader_path

    duped, reason = check_duped_file(zipf, dest)
    if duped:
        return ZipOperationResult(filename=dest, error=reason)

    with zipf.open(dest, "w") as zf, open(public_grader_path, "r") as f:
        improper_filter = filter_secret(zf, f)

    if improper_filter:
        return ZipOperationResult(
            filename=dest, warning="BEGIN-END SECRET is not properly matched"
        )
    return ZipOperationResult(filename=dest)


def sample_testcase_public(
    context: TMTContext, zipf: ZipFile, codename: str, dest: str
) -> ZipOperationResult:

    testcase_input = pathlib.Path(
        context.path.testcases
    ) / context.construct_input_filename(codename)
    testcase_output = pathlib.Path(
        context.path.testcases
    ) / context.construct_output_filename(codename)

    input_dest = output_dest = dest
    if dest.endswith("/") or not dest:
        input_dest += codename
        output_dest += codename

    input_dest += ".in"
    output_dest += ".out"
    filename = input_dest + ", " + output_dest

    for src, dest in [(testcase_input, input_dest), (testcase_output, output_dest)]:
        if not src.exists():
            return ZipOperationResult(
                filename=dest, error=f"File testcases/{src.name} not found."
            )
        if not src.is_file():
            return ZipOperationResult(
                filename=dest, error=f"File testcases/{src.name} is not a file."
            )
        duped, reason = check_duped_file(zipf, dest)
        if duped:
            return ZipOperationResult(filename=dest, error=reason)

    with zipf.open(input_dest, "w") as zf:
        zf.write(testcase_input.read_bytes())
    with zipf.open(output_dest, "w") as zf:
        zf.write(testcase_output.read_bytes())

    return ZipOperationResult(filename=filename)


def hidden_testcase_public(
    context: TMTContext, zipf: ZipFile, _: str, dest: str
) -> ZipOperationResult:

    files = []
    for codename in context.recipe.get_all_test_names():
        testcase_input = pathlib.Path(
            context.path.testcases
        ) / context.construct_input_filename(codename)

        input_dest = dest
        if dest.endswith("/") or not dest:
            input_dest += codename

        input_dest += ".in"
        files.append(input_dest)

        if not testcase_input.exists():
            return ZipOperationResult(
                filename=None, error=f"File testcases/{testcase_input.name} not found."
            )
        if not testcase_input.is_file():
            return ZipOperationResult(
                filename=None,
                error=f"File testcases/{testcase_input.name} is not a file.",
            )
        duped, reason = check_duped_file(zipf, input_dest)
        if duped:
            return ZipOperationResult(filename=input_dest, error=reason)

        with zipf.open(input_dest, "w") as zf:
            zf.write(testcase_input.read_bytes())

    return ZipOperationResult(filename=", ".join(files))


COMMAND_TABLE: dict[
    str, Callable[[TMTContext, ZipFile, *tuple[str, ...]], ZipOperationResult]
] = {
    "public": raw_public,
    "format": format_public,
    "grader": grader_public,
    "header": header_public,
    "sample": sample_testcase_public,
    "testcases": hidden_testcase_public,
}


def command_make_public(*, formatter: Formatter, context: TMTContext) -> bool:
    """Export problem package to a sepcific format."""
    context.log_directory = None

    if context.config.judge_convention != JudgeConvention.CMS:
        raise ValueError("make-public currently only supports CMS tasks")

    archive_name = context.config.short_name + ".zip"
    public_path = pathlib.Path(context.path.public)
    public_zip = pathlib.Path(context.path.public) / (
        context.config.short_name + ".zip"
    )

    formatter.println("Creating public attachment ", archive_name, "...")

    commands = []
    line_no = 0
    bad = False
    max_command_width = 0

    def report_error(error_str: str):
        nonlocal bad
        formatter.println(
            f"files:{line_no}: ",
            formatter.ANSI_RED,
            "error: ",
            formatter.ANSI_RESET,
            error_str,
        )
        bad = True

    with open(public_path / "files", "r") as filelist:
        # Filter commands and reject unrecognized ones
        for line in filelist.readlines():
            line_no += 1
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            cmd = line.split(maxsplit=2)
            if len(cmd) == 1 or cmd[0] not in COMMAND_TABLE:
                report_error(f'Unrecognized command "{cmd}"')
                continue

            cmd += [""] * (3 - len(cmd))

            method, src, dest = cmd
            max_command_width = max(max_command_width, len(method) + len(src) + 2)

            # Sanitize src
            if method != "grader":
                src = os.path.normpath(src)
                if src.startswith(".."):
                    report_error(
                        f'Source must not resolve to a path starting with double dots (found "{src}")'
                    )

            # Sanitize dest
            if dest:
                normpath = os.path.normpath(dest)
                if normpath.startswith("/"):
                    report_error(
                        f'Destination must not be an absolute path (found "{dest}")'
                    )
                    continue
                if normpath.startswith(".."):
                    report_error(
                        f'Destination must not resolve to a path starting with double dots (found "{dest}")'
                    )
                    continue

                if dest.endswith("/"):
                    normpath += "/"
                dest = normpath

            commands.append((method, src, dest))
            del cmd
    if bad:
        return False

    if context.config.problem_type is ProblemType.OUTPUT_ONLY:
        commands.append(("testcases", "", "tests/"))
        max_command_width = max(max_command_width, 11)

    with ZipFile(public_zip, "w") as z:
        for method, src, dest in commands:
            formatter.print(" " * 4)
            formatter.print_fixed_width(method, ": ", src, width=max_command_width)
            formatter.print(" " * 4)

            result = COMMAND_TABLE[method](context, z, src, dest)

            if result.error:
                formatter.print(
                    "[", formatter.ANSI_RED, "FAIL", formatter.ANSI_RESET, "]  "
                )
                if result.filename:
                    formatter.println(result.filename, ": ", result.error)
                else:
                    formatter.println(result.error)
                bad = True

            elif result.warning:
                formatter.println(
                    "[",
                    formatter.ANSI_YELLOW,
                    "WARN",
                    formatter.ANSI_RESET,
                    "]  ",
                    result.filename,
                    ": ",
                    result.warning,
                )
            else:
                formatter.println(
                    "[",
                    formatter.ANSI_GREEN,
                    "OK",
                    formatter.ANSI_RESET,
                    "]    ",
                    result.filename,
                )

    return not bad
