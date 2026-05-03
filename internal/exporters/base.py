import os
from pathlib import Path
from abc import ABC, abstractmethod
from typing import Generator

from internal.formatting import Formatter
from internal.context import TMTContext
from internal.zip_handler import ZipFileHander

from .operations import ExportOperation, ExportResult, ExportResultEnum


class BaseExporter(ABC):
    """Base class for exporters"""

    @abstractmethod
    def setup_operations(
        self, context: TMTContext
    ) -> Generator[ExportOperation, None, None]:
        pass

    def export(
        self, formatter: Formatter, context: TMTContext, output_path: str
    ) -> bool:
        assert os.path.isabs(output_path)

        # TODO: maybe if the path is a directory, we export a zip into that directory?
        if output_path.endswith("/"):
            formatter.println(
                formatter.ANSI_RED,
                "Error: why are you trying to make this problem package your entire file system?",
                formatter.ANSI_RESET,
            )
            return False

        # TODO: it should generally return the result list, but it currently returns bool for convenicence

        formatter.println(f"Exporting to {output_path}...")

        if Path(output_path).exists():
            formatter.println(
                formatter.ANSI_RED,
                f"Error: path {output_path} already exists.",
                formatter.ANSI_RESET,
            )
            return False
        if Path(output_path + ".part").exists():
            formatter.println(
                formatter.ANSI_RED,
                f"Error: path {output_path}.part already exists.",
                formatter.ANSI_RESET,
            )
            return False

        zipfile = ZipFileHander(output_path + ".part")

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
        if any(res.result == ExportResultEnum.FAILURE for res in res_list):
            os.remove(output_path + ".part")
            return False

        os.rename(output_path + ".part", output_path)
        return True
