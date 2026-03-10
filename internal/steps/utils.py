from dataclasses import dataclass
from enum import Enum
import functools
from typing import Callable

from internal.outcomes import CompilationResult


def requires_sandbox(func):
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        if getattr(self, "sandbox") is None:
            class_name = self.__class__.__name__
            method_name = func.__name__
            raise RuntimeError(
                f"{class_name}.{method_name} should not be called when sandbox is None"
            )
        return func(self, *args, **kwargs)

    return wrapper


@dataclass(frozen=True)
class CompilationSlotInfo:
    display_name: str
    internal_name: str


class CompilationSlot(Enum):
    # fmt: off
    GENERATOR  = CompilationSlotInfo("Generator", "generator")
    VALIDATOR  = CompilationSlotInfo("Validator", "validator")
    SOLUTION   = CompilationSlotInfo("Solution", "solution")
    INTERACTOR = CompilationSlotInfo("Interactor", "interactor")
    MANAGER    = CompilationSlotInfo("Manager", "manager")
    CHECKER    = CompilationSlotInfo("Checker", "checker")
    # fmt: on

    # Convenience accessors
    @property
    def display_name(self) -> str:
        return self.value.display_name

    @property
    def internal_name(self) -> str:
        return self.value.internal_name


@dataclass
class CompilationJob:
    slot: CompilationSlot
    compile_fn: Callable[[], CompilationResult]
    display_file: str
