from .base import Language


class ExecutableLanguage(Language):
    """
    Specifies compilation details of a language compiling to ELF.
    """

    @property
    def executable_extension(self) -> str:
        return ""

    def get_execution_command(
        self,
        executable_filename_base: str,
        executable_stack_mib: int,
    ) -> list[str]:
        return [executable_filename_base]
