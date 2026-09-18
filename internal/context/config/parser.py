import re
import resource
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class TMTConfigError:
    what: str

    @classmethod
    def _typename(cls, t: type):
        if t is int:
            return "integer"
        if t is str:
            return "string"
        if t is bool:
            return "boolean"
        if t is type(None):
            return "none"
        if issubclass(t, Enum):
            all_vals = ", ".join(str(val.value) for val in t)
            return f"enum (one of {all_vals})"
        return "config"

    @classmethod
    def bad_basic_type(cls, name: str, expected_type: type[T], found: Any):
        return TMTConfigError(
            f"Invalid type for config field: {name} ({cls._typename(expected_type)}), "
            f"found {found} ({cls._typename(type(found))})."
        )

    @classmethod
    def bad_complex_type(cls, name: str, found: Any):
        return TMTConfigError(
            f"Invalid type for config field: {name} (object), "
            f"found {found} ({cls._typename(type(found))})."
        )


class TMTConfigErrorsList(list[TMTConfigError]):
    @classmethod
    def single_bad_basic_type(cls, name: str, expected_type: type[T], found: Any):
        return cls([TMTConfigError.bad_basic_type(name, expected_type, found)])

    @classmethod
    def single_bad_complex_type(cls, name: str, found: Any):
        return cls([TMTConfigError.bad_complex_type(name, found)])


@dataclass
class DictParser:
    """
    DictParser: parsing dict loaded from YAML and accumulates errors

    Each pop* function pops a field, validates, and returns the result or the error.
    Every error produced through pop* is also recorded in `errors` for error reporting.
    """

    data: dict[str, Any]
    parent: str
    errors: TMTConfigErrorsList = field(default_factory=TMTConfigErrorsList)

    def _full_key_name(self, key: str):
        return f"{self.parent}.{key}" if self.parent else key

    def add_err(self, what: str | TMTConfigError) -> TMTConfigError:
        """Add a TMTConfigError and return it"""
        match what:
            case TMTConfigError():
                self.errors.append(what)
                return what
            case str():
                err = TMTConfigError(what)
                self.errors.append(err)
                return err

    def pop(self, key: str, type: type[T]) -> T | TMTConfigError:
        """Pop and validate field with primitive types (int, str, bool, or any Enum)"""

        val = self.data.pop(key, None)
        if type in (int, str, bool):
            if not isinstance(val, type):
                return self.add_err(
                    TMTConfigError.bad_basic_type(self._full_key_name(key), type, val)
                )
            return val

        if issubclass(type, Enum):
            try:
                if not isinstance(val, str):
                    raise TypeError()  # immedately caught below
                return type(val)
            except (ValueError, TypeError):
                return self.add_err(
                    TMTConfigError.bad_basic_type(self._full_key_name(key), type, val)
                )

        raise ValueError(f"Type {type} is not a basic type")

    def pop_optional(self, key: str, type: type[T]) -> T | None | TMTConfigError:
        """Pop and validate optional field with primitive types (int, str, bool, or any Enum)"""

        val = None if self.data.get(key, None) is None else self.pop(key, type)
        self.discard(key)
        return val

    def pop_default(self, key: str, type: type[T], default: T) -> T | TMTConfigError:
        """Pop and validate optional field with default values (int, str, bool, or any Enum)"""
        res = self.pop_optional(key, type)
        return default if res is None else res

    def pop_then(self, key: str, func: Callable[[Any], T]) -> T | TMTConfigErrorsList:
        """
        Pop a field and pass it into a parsing function.
        The function should return T | TMTConfigErrorsList, so the Result | Error union has error type TMTConfigErrorsList.
        """

        val = self.data.pop(key, None)
        if val is None:
            err = TMTConfigError.bad_complex_type(self._full_key_name(key), val)
            self.add_err(err)
            return TMTConfigErrorsList([err])
        ret = func(val)
        if isinstance(ret, TMTConfigErrorsList):
            self.errors.extend(ret)
        return ret

    def pop_optional_then(
        self, key: str, func: Callable[[Any], T]
    ) -> T | TMTConfigErrorsList | None:
        """
        Pop an optional field and pass it into a parsing function.
        """

        val = None if self.data.get(key, None) is None else self.pop_then(key, func)
        self.discard(key)
        return val

    def reject_remaining(self) -> None:
        """Produce an error for each remaining field in the dict."""

        for key in self.data:
            self.add_err(
                f"Extra config remaining in {self.parent}: {key}. Please move them under config 'extra'."
            )

    def discard(self, key: str) -> None:
        """Discard (ignore) a key in the dict."""
        self.data.pop(key, None)

    def pop_time_to_second(
        self, key: str, *, default: float | None = None
    ) -> float | TMTConfigError:
        """Pop and validate a time limit field (number + ms/s)."""

        if default is not None:
            val = self.pop_optional(key, str)
            if val is None:
                return default
        else:
            val = self.pop(key, str)
        if isinstance(val, TMTConfigError):
            return val

        match = re.fullmatch(r"(\d+|\d+\.\d+)\s*(ms|s)", val)
        if match is None:
            return self.add_err(
                f"Invalid config {self._full_key_name(key)} (found {val}, expected number s/ms)"
            )
        match match.group(2):
            case "ms":
                return float(match.group(1)) / 1000.0
            case "s":
                return float(match.group(1))
            case _:
                assert False, "Unreachable code"

    def pop_bytes_to_mib(
        self, key: str, *, default: int | None = None, allow_unlimited: bool = False
    ) -> int | TMTConfigError:
        """Pop and validate a memory limit field (number + G/GiB/M/MiB, or unlimited, depending on argument)."""

        if default is not None:
            val = self.pop_optional(key, str)
            if val is None:
                return default
        else:
            val = self.pop(key, str)
        if isinstance(val, TMTConfigError):
            return val

        if allow_unlimited and val == "unlimited":
            return resource.RLIM_INFINITY
        match = re.fullmatch(r"(\d+)\s*(G|GiB|M|MiB)", val)
        if match is None:
            expected = (
                "number M/MiB/G/GiB or unlimited"
                if allow_unlimited
                else "number M/MiB/G/GiB"
            )
            return self.add_err(
                f"Invalid config {self._full_key_name(key)} (found {val}, expected {expected})"
            )
        match match.group(2):
            case "G" | "GiB":
                return int(match.group(1)) * 1024
            case "M" | "MiB":
                return int(match.group(1))
            case _:
                assert False, "Unreachable code"


class TMTConfigParsingError(AssertionError):
    """
    Raised by check_error when arguments are error-typed value.
    Mostly, uncaught if it should never be an error.
    Rarely, can be caught for checking that arguments are not errors.

    Component outside of config parsing should not catch this.
    """

    def __init__(self, err: TMTConfigError | TMTConfigErrorsList):
        match err:
            case TMTConfigError():
                super().__init__(f"check_error: value is error-typed: {err.what}")
            case TMTConfigErrorsList():
                errs = "; ".join(e.what for e in err)
                super().__init__(f"check_error: value is error-typed: {errs}")


def check_error(t: T | TMTConfigError | TMTConfigErrorsList) -> T:
    if isinstance(t, (TMTConfigError, TMTConfigErrorsList)):
        raise TMTConfigParsingError(t)
    return t
