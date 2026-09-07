import os

from internal.formatting import Formatter
from internal.context import TMTContext, JudgeConvention
from internal.exporters import (
    BaseExporter,
    DOMJudgeLegacyExporter,
    CMSTPSExporter,
    CommandExportSummary,
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
