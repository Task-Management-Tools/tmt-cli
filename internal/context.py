from __future__ import annotations

from internal.utils import make_file_extension
from internal.paths import ProblemDirectoryHelper

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from internal.config import TMTConfig


class TMTContext:
    def __init__(self):
        self.path: ProblemDirectoryHelper = None
        """Constructs absolute paths for the problem package. See the class for more information."""
        self.config: TMTConfig = None
        """Stores configs parsed from the problem package. See the class for more information."""

        self.compiler = "g++"
        self.compile_flags = ["-std=gnu++20", "-Wall", "-Wextra", "-O2"]  # TODO read it from .yaml

    def construct_test_filename(self, code_name, extension):
        return code_name + make_file_extension(extension)

    def construct_input_filename(self, code_name):
        return self.construct_test_filename(code_name, self.config.input_extension)

    def construct_output_filename(self, code_name):
        return self.construct_test_filename(code_name, self.config.output_extension)
