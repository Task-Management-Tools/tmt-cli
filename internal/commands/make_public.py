from dataclasses import dataclass, asdict
from operator import itemgetter
import os
import re
import pathlib
import string
from typing import TextIO, BinaryIO, Protocol
from zipfile import ZipFile

from internal.compilation import languages
from internal.context import JudgeConvention, ProblemType, TMTContext
from internal.formatting import Formatter


class SafeFormatter(string.Formatter):
    def get_value(self, key, args, kwargs):
        try:
            return super().get_value(key, args, kwargs)
        except (KeyError, AttributeError):
            return "{" + str(key) + "}"

    def get_field(self, field_name, args, kwargs):
        if field_name.startswith("__"):
            raise ValueError(f"'{field_name}' contains double underscore")
        try:
            return super().get_field(field_name, args, kwargs)
        except (KeyError, AttributeError, IndexError, TypeError):
            raise ValueError(f"'{field_name}' is not a valid config attribute")


@dataclass
class ZipOperationResult:
    filename: str | None
    error: str | None = None
    warning: str | None = None


class ZipOperation(Protocol):
    # For type hinting
    def __call__(
        self, ctx: TMTContext, zf: ZipFile, *args: str
    ) -> ZipOperationResult: ...


def check_duped_file(zipf: ZipFile, filename: str) -> tuple[bool, str | None]:
    """
    Returns a pair.
    The first component is True if the filename coincides with another file or directory in the zip archive, or any parent is already a file.
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


@dataclass
class GraderFilterIssue:
    # TODO: this dataclass is only used for the following function for convenience.
    # when refactor makes sense, eliminate the usage of this one (maybe in favor of tmt-verify)
    warning: str | None = None
    error: str | None = None


def filter_secret(zf: BinaryIO, f: TextIO, srcname: str) -> list[GraderFilterIssue]:
    """
    Filters secret from a text stream to a binary stream.
    The filename is requried for diagnostics.

    Returns a list of issues.
    If a line is too similar to BEGIN/END SECRET, reports warning; if BEGIN-END pair is not properly matched, reports error.
    The results are ordered such that error precedes warning.
    """

    def fuzzy_match(text: str, target: str, threshold: int):
        """
        If matches, returns a tuple representing the first index and the respective substring.
        """

        def edit_distance(a: str, b: str):
            dp = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
            for i in range(len(a) + 1):
                dp[i][0] = i
            for i in range(len(b) + 1):
                dp[0][i] = i
            for i in range(len(a)):
                for j in range(len(b)):
                    dp[i + 1][j + 1] = min(
                        dp[i][j] + (a[i] != b[j]), dp[i][j + 1] + 1, dp[i + 1][j] + 1
                    )
            return dp[-1][-1]

        processed = text.translate(
            str.maketrans(
                string.ascii_lowercase, string.ascii_uppercase, string.whitespace
            )
        )
        target = target.translate(
            str.maketrans(
                string.ascii_lowercase, string.ascii_uppercase, string.whitespace
            )
        )

        for i in range(len(processed)):
            subtext = processed[i : i + len(target)]
            if edit_distance(subtext, target) <= threshold:
                index_mapping = list(
                    map(
                        itemgetter(0),
                        filter(
                            lambda x: x[1] not in string.whitespace, enumerate(text, 0)
                        ),
                    )
                )
                start = index_mapping[i]
                end = index_mapping[i + len(subtext) - 1] + 1
                return start + 1, text[start:end]
        return None

    hide = False
    issues: list[GraderFilterIssue] = []
    for i, line in enumerate(f.readlines(), 1):
        # match begin secret
        begin_secret = end_secret = False
        if re.search(r"\bBEGIN\s+SECRET\b", line):
            begin_secret = True
        if re.search(r"\bEND\s+SECRET\b", line):
            end_secret = True
        if begin_secret and end_secret:
            issues.append(
                GraderFilterIssue(
                    error=f"{srcname}:{i}: BEGIN and END SECRET found on the same line."
                )
            )
        # typo detect
        if begin_secret or end_secret:
            pass
        elif (fmatch := fuzzy_match(line, "BEGIN SECRET", 3)) is not None:
            issues.append(
                GraderFilterIssue(
                    warning=f"{srcname}:{i}:{fmatch[0]}: '{fmatch[1]}' too similar to 'BEGIN SECRET'.",
                )
            )
        elif (fmatch := fuzzy_match(line, "END SECRET", 2)) is not None:
            issues.append(
                GraderFilterIssue(
                    warning=f"{srcname}:{i}:{fmatch[0]}: '{fmatch[1]}' too similar to 'END SECRET'.",
                )
            )
        # write lines
        if begin_secret:
            if hide:
                issues.append(
                    GraderFilterIssue(
                        error=f"{srcname}:{i}: Found BEGIN SECRET while the secret section is already opened.",
                    )
                )
            hide = True
        if not hide:
            zf.write(line.encode())
        if end_secret:
            if not hide:
                issues.append(
                    GraderFilterIssue(
                        error=f"{srcname}: {i}: Found END SECRET while the secret section is already closed."
                    )
                )
            hide = False

    if hide:
        issues.append(
            GraderFilterIssue(
                error=f"{srcname}:{i}: The last SECRET section is not properly closed.",
            )
        )
    # Python sort is stable, so line number is not messed up.
    issues.sort(key=lambda i: i.error is None)
    return issues


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
        issues = filter_secret(zf, f, str(public_file.relative_to(os.getcwd())))
        if issues:
            # TODO: the current framework does not allow all error reporting
            return ZipOperationResult(filename=dest, **asdict(issues[0]))

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
        issues = filter_secret(zf, f, str(public_grader_path.relative_to(os.getcwd())))
        if issues:
            # TODO: the current framework does not allow all error reporting
            return ZipOperationResult(filename=dest, **asdict(issues[0]))

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


COMMAND_TABLE: dict[str, ZipOperation] = {
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

    if not pathlib.Path(context.path.public_filelist).is_file():
        formatter.println(
            formatter.ANSI_RED,
            "Error: ",
            formatter.ANSI_RESET,
            f"Public filelist ({os.path.relpath(context.path.public_filelist)}) is not a file or does not exist.",
        )
        return False

    archive_name = context.config.short_name + ".zip"
    public_zip = pathlib.Path(context.path.public) / archive_name
    formatter.println("Creating public attachment ", archive_name, "...")

    with open(context.path.public_filelist, "r") as filelist:
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
                if src.startswith("/"):
                    report_error(f'Source must not be an absolute path (found "{src}")')

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
        if public_zip.exists():
            public_zip.unlink()
        return False

    if context.config.problem_type is ProblemType.OUTPUT_ONLY:
        commands.append(("testcases", "", "tests/"))
        max_command_width = max(max_command_width, 11)

    # Build the zipfile
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
    if bad and public_zip.exists():
        public_zip.unlink()

    return not bad
