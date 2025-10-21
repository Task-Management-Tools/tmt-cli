import os

from .base import Language, MakeInfo


class LanguagePython3(Language):
    @property
    def name(self):
        return "python3"

    @property
    def source_extensions(self):
        return [".py"]

    @property
    def executable_extension(self):
        return ".pyz"

    def get_make_wildcard_command(self, executable_stack_mib: int) -> MakeInfo:
        return MakeInfo(
            makefile=os.path.join(
                self.context.path.script_dir,
                "internal/compilation/languages/makefiles/python.wildcard.Makefile",
            ),
            extra_env={},
        )

    def get_make_target_command(self, executable_stack_mib: int) -> MakeInfo:
        return MakeInfo(
            makefile=os.path.join(
                self.context.path.script_dir,
                "internal/compilation/languages/makefiles/python.target.Makefile",
            ),
            extra_env={},
        )

    def get_execution_command(
        self,
        executable_filename_base: str,
        executable_stack_mib: int,
    ):
        interperter = os.getenv("PYTHON", "python3")
        return [interperter, executable_filename_base + self.executable_extension]
