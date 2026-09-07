import os
import pathlib
from argparse import RawTextHelpFormatter

from internal.cli import argument, command, option
from internal.formatting import Formatter
from internal.context import TMTContext, JudgeConvention
from internal.exporters import (
    BaseExporter,
    DOMJudgeLegacyExporter,
    CMSTPSExporter,
    CommandExportSummary,
    exporters,
)


def command_export(
    *,
    formatter: Formatter,
    context: TMTContext,
    output_path: str,
    package_format: type[BaseExporter] | None = None,
    force_output: bool,
):
    """Export problem package to a sepcific format."""
    context.log_directory = None

    if package_format is None:
        match context.config.judge_convention:
            case JudgeConvention.ICPC:
                package_format = DOMJudgeLegacyExporter
            case JudgeConvention.CMS:
                package_format = CMSTPSExporter
            case _:
                formatter.println(
                    formatter.ANSI_RED,
                    f"Error: judge convention {context.config.judge_convention} has no default exporter.",
                    formatter.ANSI_RESET,
                )
                return CommandExportSummary(invalid_format=True)

    end_with_slash = output_path.endswith(os.sep)
    output_path = os.path.normpath(os.path.join(os.getcwd(), output_path))
    if end_with_slash and not output_path.endswith(os.sep):
        output_path += os.sep
    return package_format().export(formatter, context, output_path, force_output)


@command("export", help="Export packages", formatter_class=RawTextHelpFormatter)
@argument(
    "output_path",
    help="Output path of the archive. "
    "If the path is considered a directory, it will be exported to <short_name>.zip inside the directory. "
    "By default, a path ending with a trailing slash and a path that is a directory are considered a directory. "
    "Specifying --explicit-directory disables the second case and the path will always be treated as a file if it has no trailing slash.",
)
@option(
    "-p",
    "--package",
    help="Specifies package format. "
    "If not set, use default exporter of the judge convention. "
    "Otherwise, must be one of: \n"
    + "".join(f" - {k}: {v.description}\n" for k, v in exporters.items()),
    choices=list(exporters.keys()),
    default=None,
)
@option(
    "-f",
    "--force",
    is_flag=True,
    dest="force_output",
    help="Force overwriting the output file even if it exists.",
)
@option(
    "-e",
    "--explicit-directory",
    is_flag=True,
    help="Prevent outputing into the directory if the path specified is a directory but not specified with trailing slash.",
)
def command_export_cli(
    *,
    formatter: Formatter,
    context: TMTContext,
    output_path: str,
    package: str | None,
    force_output: bool,
    explicit_directory: bool,
) -> CommandExportSummary:
    """CLI entry point for `tmt export`.

    Resolves `--package` into an exporter class and interprets `output_path` as a
    directory (exporting `<short_name>.zip` into it) when appropriate. The plain
    `command_export` treats `output_path` verbatim.
    """
    package_format = exporters[package] if package is not None else None

    # UNIX directory
    if output_path.endswith(os.sep):
        output_path += context.config.short_name + ".zip"
    if not explicit_directory and (pathlib.Path.cwd() / output_path).is_dir():
        output_path += os.sep + context.config.short_name + ".zip"

    return command_export(
        formatter=formatter,
        context=context,
        output_path=output_path,
        package_format=package_format,
        force_output=force_output,
    )
