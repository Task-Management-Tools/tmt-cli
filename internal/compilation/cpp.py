import os
import platform

from .abc import Language, MakeInfo


class LanguageCpp(Language):
    @property
    def source_extensions(self):
        return [".cpp", ".cc"]

    @property
    def name(self):
        return "cpp"

    def _construct_make_env(self, executable_stack_mib: int) -> dict[str, str]:
        compile_flags = self.context.compile_flags(self.name)
        if platform.system() == "Darwin":
            compile_flags += [
                "-Wl,-stack_size",
                f"-Wl,{min(executable_stack_mib, 512) * 1024 * 1024:x}",
            ]
        return {
            "CXXFLAGS": " ".join(compile_flags),
            "INCLUDE_PATHS": self.context.path.include,
        }

    def get_make_wildcard_command(self, executable_stack_mib: int) -> MakeInfo:
        return MakeInfo(
            makefile=os.path.join(
                self.context.path.script_dir,
                "internal/compilation/makefiles/cpp.wildcard.Makefile",
            ),
            env=self._construct_make_env(executable_stack_mib),
        )

    def get_make_target_command(self, executable_stack_mib: int) -> MakeInfo:
        return MakeInfo(
            makefile=os.path.join(
                self.context.path.script_dir,
                "internal/compilation/makefiles/cpp.target.Makefile",
            ),
            env=self._construct_make_env(executable_stack_mib),
        )

    @property
    def get_compile_single_commands(self):
        raise NotImplementedError
