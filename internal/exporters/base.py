import os
import dataclasses
from pathlib import Path
from typing import Generator
from abc import ABC, abstractmethod

from internal.formatting import Formatter
from internal.context import TMTContext
from internal.zip_handler import ZipFileHander

from .operations import ExportOperation, ExportResult, ExportResultEnum


@dataclasses.dataclass
class CommandExportSummary:
    invalid_path: bool = False
    invalid_path_part: bool = False
    export_results: list[ExportResult] = dataclasses.field(default_factory=list)

    def __bool__(self):
        return (
            not self.invalid_path
            and not self.invalid_path_part
            and not any(
                r.result is ExportResultEnum.FAILURE for r in self.export_results
            )
        )


class BaseExporter(ABC):
    """Base class for exporters"""

    @abstractmethod
    def setup_operations(
        self, context: TMTContext
    ) -> Generator[ExportOperation, None, None]:
        pass

    def export(
        self, formatter: Formatter, context: TMTContext, output_path: str
    ) -> CommandExportSummary:

        # We export to [archive_name].part first, so if it fails we don't override the original one;
        # also this prevents multiple export running at the same time
        export_path = Path(output_path)
        export_path_tmp = export_path.with_name(export_path.name + ".part")
        assert export_path.is_absolute()

        # TODO: maybe if the path is a directory, we export a zip into that directory?
        if export_path == export_path.anchor:
            formatter.println(
                formatter.ANSI_RED,
                "Error: why are you trying to make this problem package your entire file system?",
                formatter.ANSI_RESET,
            )
            return CommandExportSummary(invalid_path=True)

        formatter.println(f"Exporting to {export_path.relative_to(Path.cwd())}...")

        if export_path.exists():
            formatter.println(
                formatter.ANSI_RED,
                f"Error: {export_path.relative_to(Path.cwd())} already exists.",
                formatter.ANSI_RESET,
            )
            return CommandExportSummary(invalid_path=True)
        if export_path_tmp.exists():
            formatter.println(
                formatter.ANSI_RED,
                f"Error: {export_path_tmp.relative_to(Path.cwd())} already exists.",
                formatter.ANSI_RESET,
            )
            return CommandExportSummary(invalid_path_part=True)

        zipfile = ZipFileHander(export_path_tmp)

        # Execute all operations
        ops = list(self.setup_operations(context))
        name_length = max(len(operation.target_name) for operation in ops) + 2

        res_list: list[ExportResult] = []
        for operation in ops:
            formatter.print(" " * 4)
            formatter.print_fixed_width(operation.target_name, width=name_length)
            res = operation.execute(context, zipfile)

            match res.result:
                case ExportResultEnum.SUCCESS:
                    color, text = formatter.ANSI_GREEN, "OK"
                case ExportResultEnum.WARNING:
                    color, text = formatter.ANSI_YELLOW, "WARN"
                case ExportResultEnum.SKIPPED:
                    color, text = formatter.ANSI_GREY, "SKIP"
                case ExportResultEnum.FAILURE:
                    color, text = formatter.ANSI_RED, "FAIL"
                case _:
                    raise ValueError(f"export: Unknown ExportResultEnum {res.result}")

            formatter.print_fixed_width(
                "[", color, text, formatter.ANSI_RESET, "]", width=8
            )

            msgs = res.target_compressed or ", ".join(res.target_list)
            if len(res.target_list) >= 8:
                msgs += f" (total {len(res.target_list)})"
            msgs += res.msg

            formatter.print_preserve_offset(msgs)
            formatter.println()
            res_list.append(res)

        zipfile.close()
        summary = CommandExportSummary(export_results=res_list)
        if not summary:
            os.remove(export_path_tmp)
            formatter.println(
                formatter.ANSI_RED, "Export failed.", formatter.ANSI_RESET
            )
        else:
            os.rename(export_path_tmp, export_path)
            if any(
                r.result is ExportResultEnum.WARNING for r in summary.export_results
            ):
                formatter.println(
                    formatter.ANSI_YELLOW,
                    "Export completed with warnings.",
                    formatter.ANSI_RESET,
                )
            else:
                formatter.println("Export completed.")
        return summary
