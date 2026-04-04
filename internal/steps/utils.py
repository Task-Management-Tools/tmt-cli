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


class CompilationSlot(Enum):
    GENERATOR = "generator"
    VALIDATOR = "validator"
    SOLUTION = "solution"
    INTERACTOR = "interactor"
    MANAGER = "manager"
    CHECKER = "checker"


@dataclass
class CompilationJob:
    slot: CompilationSlot
    compile_fn: Callable[[], CompilationResult]
    display_file: str
