import os

from internal.formatting import Formatter
from internal.context import TMTContext
from internal.context import JudgeConvention
from internal.exporters.domjudge_legacy import DOMJudgeLegacyExporter
from internal.exporters.cms_tps import CMSTPSExporter


def command_export(
    *,
    formatter: Formatter,
    context: TMTContext,
    output_path: str,
    package_format: JudgeConvention | None = None,
):
    """Export problem package to a sepcific format."""
    context.log_directory = None

    if package_format is None:
        package_format = context.config.judge_convention

    match package_format:
        case JudgeConvention.ICPC:
            exporter = DOMJudgeLegacyExporter()
        case JudgeConvention.CMS:
            exporter = CMSTPSExporter()
        case _:
            raise ValueError(
                "Unsupported package export format: " + str(package_format) + "."
            )
    output_path = os.path.normpath(os.path.join(os.getcwd(), output_path))
    return exporter.export(formatter, context, output_path)
