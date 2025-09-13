from dataclasses import dataclass
from abc import ABC, abstractmethod

from internal.context import TMTContext


@dataclass
class MakeInfo:
    makefile: str
    env: dict[str, str]


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

    @abstractmethod
    def get_make_wildcard_command(self, executable_stack_mib: int) -> MakeInfo:
        return MakeInfo("", {})

    @abstractmethod
    def get_make_target_command(self, executable_stack_mib: int) -> MakeInfo:
        return MakeInfo("", {})

    @abstractmethod
    def get_compile_single_commands(self, executable_stack_mib: int) -> list[list[str]]:
        return []
