import os

from internal.compilation.languages.base import MakeInfo, Language
from internal.context.context import TMTContext


class LanguageDummy(Language):
    def __init__(self, context: TMTContext):
        super().__init__(context)
        self.base_path = os.path.join(
            self.context.path.script_dir,
            "tests/languages/",
        )

    @property
    def id(self):
        return "dummy"

    @property
    def name(self):
        return "Dummy (Always Compliation Error)"

    @property
    def source_extensions(self):
        return [".dummy"]

    @property
    def executable_extension(self):
        return ".dummy"

    def get_make_wildcard_command(self, executable_stack_mib: int) -> MakeInfo:
        return MakeInfo(
            makefile=os.path.join(self.base_path, "dummy.wildcard.Makefile"),
            extra_env={"COMPILER": os.path.join(self.base_path, "dummy-compiler.sh")},
        )

    def get_make_target_command(self, executable_stack_mib: int) -> MakeInfo:
        return MakeInfo(
            makefile=os.path.join(self.base_path, "dummy.target.Makefile"),
            extra_env={"COMPILER": os.path.join(self.base_path, "dummy-compiler.sh")},
        )

    def get_execution_command(
        self,
        executable_filename_base: str,
        executable_stack_mib: int,
    ):
        # It is fine to do this since the compilation always fails
        assert False, "The dummy language should never be executed"
