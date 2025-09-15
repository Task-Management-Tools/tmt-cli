from dataclasses import dataclass
from abc import ABC, abstractmethod

from internal.context import TMTContext


@dataclass
class MakeInfo:
    makefile: str
    """Absolue path to the Makefile."""
    extra_env: dict[str, str]
    """Extra environment supplied to the Makefile."""


class Language(ABC):
    """
    Specifies compilation details of a language.
    """

    def __init__(self, context: TMTContext):
        self.context = context

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Returns the name of this langauge. It will be used in configuration files.
        """
        return "unknown"

    @property
    @abstractmethod
    def source_extensions(self) -> list[str]:
        """
        Returns a list of supported extensions.
        Each extension must start with a dot.
        """
        return []

    @property
    @abstractmethod
    def executable_extension(self) -> str:
        """
        Return an unique extension (possibly empty: indicating no extension) to identify the execution method.
        """
        return ""

    @abstractmethod
    def get_make_wildcard_command(self, executable_stack_mib: int) -> MakeInfo:
        """
        Returns a MakeInfo indicating the location of the Makefile compiling every single target,
        and the related environment.
        """
        return MakeInfo("", {})

    @abstractmethod
    def get_make_target_command(self, executable_stack_mib: int) -> MakeInfo:
        """
        Returns a MakeInfo indicating the location of the Makefile compiling a single target,
        and the related environment.

        Apart from the compiler specific environment variables, SRCS and TARGET_NAME should 
        still be supplied to form the compilation environment.
        """
        return MakeInfo("", {})

    @abstractmethod
    def get_execution_command(
        self,
        executable_filename_base: str,
        executable_stack_mib: int,
    ) -> list[str]:
        return []
