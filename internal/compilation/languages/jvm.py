import os

from .base import Language


class JVMLanguage(Language):
    """
    Specifies compilation details of a language targeting JVM.
    """

    @property
    def executable_extension(self) -> str:
        return ".jar"

    def get_execution_command(
        self,
        executable_filename_base: str,
        executable_stack_mib: int,
    ) -> list[str]:
        java = os.getenv("JAVA", "java")
        return [
            java,
            f"-Xss{executable_stack_mib}m",
            "-jar",
            executable_filename_base + self.executable_extension,
        ]
