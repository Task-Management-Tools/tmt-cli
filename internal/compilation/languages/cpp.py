import os
import platform

from .abc import Language, MakeInfo


class LanguageCpp(Language):
    @property
    def name(self):
        return "cpp"

    @property
    def source_extensions(self):
        return [".cpp", ".cc"]

    @property
    def executable_extension(self):
        return None  # compiles to ELF

    def _get_stack_size_args(self, executable_stack_mib: int) -> list[str]:
        if platform.system() == "Darwin":
            executable_stack_mib = min(executable_stack_mib, 512)
            return [
                "-Wl,-stack_size",
                f"-Wl,{executable_stack_mib * 1024 * 1024:x}",
            ]
        return []

    def _construct_make_env(self, executable_stack_mib: int) -> dict[str, str]:
        compile_flags = self.context.compile_flags(self.name)
        compile_flags += self._get_stack_size_args(executable_stack_mib)
        return {
            "CXXFLAGS": " ".join(compile_flags),
            "INCLUDE_PATHS": self.context.path.include,
        }

    def get_make_wildcard_command(self, executable_stack_mib: int) -> MakeInfo:
        return MakeInfo(
            makefile=os.path.join(
                self.context.path.script_dir,
                "internal/compilation/languages/makefiles/cpp.wildcard.Makefile",
            ),
            env=self._construct_make_env(executable_stack_mib),
        )

    def get_make_target_command(self, executable_stack_mib: int) -> MakeInfo:
        return MakeInfo(
            makefile=os.path.join(
                self.context.path.script_dir,
                "internal/compilation/languages/makefiles/cpp.target.Makefile",
            ),
            env=self._construct_make_env(executable_stack_mib),
        )

    def get_compile_single_commands(
        self,
        source_filenames: list[str],
        executable_filename_base: str,
        executable_stack_mib: int,
    ) -> list[list[str]]:
        compiler = os.getenv("CXX", "g++")
        compile_flags = os.getenv("CXXFLAGS", self.context.compile_flags(self.name))
        compile_flags += self._get_stack_size_args(executable_stack_mib)
        command = [compiler]
        command += compile_flags
        command += source_filenames
        command += ["-o", executable_filename_base]

        return [command]

    def get_execution_command(
        self,
        executable_filename_base: str,
        executable_stack_mib: int,
    ):
        return [executable_filename_base]
