import os
import secrets
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
    invalid_format: bool = False
    invalid_path: bool = False
    invalid_path_part: bool = False
    exported_path: Path | None = None
    export_results: list[ExportResult] = dataclasses.field(default_factory=list)

    def __bool__(self):
        return (
            not self.invalid_format
            and not self.invalid_path
            and not self.invalid_path_part
            and not any(
                r.result is ExportResultEnum.FAILURE for r in self.export_results
            )
        )


class BaseExporter(ABC):
    description = "base exporter class"

    @abstractmethod
    def setup_operations(
        self, context: TMTContext
    ) -> Generator[ExportOperation, None, None]:
        """
        A generator which gives all export operations required.
        """
        pass

    def export(
        self,
        formatter: Formatter,
        context: TMTContext,
        output_path: str,
        force_output: bool,
    ) -> CommandExportSummary:

        export_path = Path(output_path)
        assert export_path.is_absolute()

        display_path = str(
            export_path.relative_to(Path.cwd())
            if export_path.is_relative_to(Path.cwd())
            else export_path
        ) + (os.sep if output_path.endswith(os.sep) else "")
        formatter.println(f"Exporting to {display_path}...")

        def print_err(err: str):
            formatter.println(formatter.ANSI_RED, err, formatter.ANSI_RESET)

        if output_path.endswith(os.sep):
            print_err(f"Error: path '{output_path}' refers to a directory.")
            return CommandExportSummary(invalid_path=True)
        if not export_path.parent.exists():
            print_err(
                f"Error: parent of the specified path '{output_path}' is not a directory."
            )
            return CommandExportSummary(invalid_path=True)
        if export_path.exists():
            if not force_output:
                print_err(f"Error: path '{output_path}' already exists.")
                return CommandExportSummary(invalid_path=True)
            if not export_path.is_file():
                print_err(f"Error: '{output_path}' is not a file; cannot overwrite.")
                return CommandExportSummary(invalid_path=True)

        # We export to [archive_name].[8-digit base64].part first, so if it fails we won't override the original one
        # Does not clean up for unexpected failure
        for _ in range(3):
            export_path_tmp: Path = export_path.with_name(
                f"{export_path.name}.{secrets.token_urlsafe(6)}.part"
            )
            if not export_path_tmp.exists():
                break
        else:  # how is this possible?
            print_err("Error: cannot write to partial file.")
            return CommandExportSummary(invalid_path_part=True)

        try:
            zipfile = ZipFileHander(export_path_tmp)
        except OSError as e:
            reason = os.strerror(e.errno) if e.errno is not None else "Unknown error"
            print_err(
                f"Error: cannot create temporary archive {export_path_tmp}: {reason}."
            )
            return CommandExportSummary(invalid_path=True)

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
        summary.exported_path = export_path
        return summary
