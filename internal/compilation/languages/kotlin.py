import os

from .base import MakeInfo
from .jvm import JVMLanguage


class LanguageKotlin(JVMLanguage):
    @property
    def id(self) -> str:
        return "kotlin"

    @property
    def name(self) -> str:
        return "Kotlin"

    @property
    def source_extensions(self) -> list[str]:
        return [".kt"]

    def _construct_make_env(self) -> dict[str, str]:
        compile_flags = self.context.compile_flags(self.id)
        return {"KOTLINCFLAGS": " ".join(compile_flags)}

    def get_make_wildcard_command(self, executable_stack_mib: int) -> MakeInfo:
        return MakeInfo(
            makefile=os.path.join(
                self.context.path.script_dir,
                "internal/compilation/languages/makefiles/kotlin.wildcard.Makefile",
            ),
            extra_env=self._construct_make_env(),
        )

    def get_make_target_command(self, executable_stack_mib: int) -> MakeInfo:
        return MakeInfo(
            makefile=os.path.join(
                self.context.path.script_dir,
                "internal/compilation/languages/makefiles/kotlin.target.Makefile",
            ),
            extra_env=self._construct_make_env(),
        )
