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
            env={},
        )

    def get_make_target_command(self, executable_stack_mib: int) -> MakeInfo:
        return MakeInfo(
            makefile=os.path.join(
                self.context.path.script_dir,
                "internal/compilation/languages/makefiles/cpp.target.Makefile",
            ),
            env={},
        )

    def get_compile_single_commands(
        self,
        source_filenames: list[str],
        executable_filename_base: str,
        executable_stack_mib: int,
    ) -> list[list[str]]:
        ENTRY_POINT = "__main__.pyc"

        compiler = os.getenv("PYTHON", "python3")
        commands = []

        commands.append(["cp"] + source_filenames + ["."])
        commands.append([compiler, "-m", "compileall", "-b", "."])
        commands.append(
            [
                "mv",
                os.path.splitext(os.path.basename(source_filenames[0]))[0] + ".pyc",
                "__main__.pyc",
            ]
        )
        commands.append(
            ["zip", executable_filename_base + self.executable_extension]
            + [ENTRY_POINT]
            + [os.path.basename(src) + ".pyc" for src in source_filenames[1:]]
        )
        return commands

    def get_execution_command(
        self,
        executable_filename_base: str,
        executable_stack_mib: int,
    ):
        interperter = os.getenv("PYTHON", "python3")
        return [interperter, executable_filename_base + self.executable_extension]
