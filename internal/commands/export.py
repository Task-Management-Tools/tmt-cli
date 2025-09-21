from typing import Optional

from internal.formatting import Formatter
from internal.context import TMTContext
from internal.context import JudgeConvention
from internal.exporters.icpc import ICPCExporter


def command_export(*, formatter: Formatter, context: TMTContext, output_path: str, package_format: Optional[JudgeConvention] = None, create_zip: bool = True):
    """Export problem package to a sepcific format."""
    
    if package_format == None:
        package_format = context.config.judge_convention

    match package_format:
        case JudgeConvention.ICPC:
            exporter = ICPCExporter(formatter, context, output_path)
        case _:
            raise ValueError("Unsupported package export format: " + str(package_format) + ".")

    exporter.export(formatter, context, create_zip)
