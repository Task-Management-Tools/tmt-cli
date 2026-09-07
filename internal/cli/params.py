"""Metadata records produced by the `option`/`argument` decorators."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class OptionSpec:
    flags: tuple[str, ...]
    kwargs: dict[str, Any] = field(default_factory=dict)


@dataclass
class ArgumentSpec:
    name: str
    kwargs: dict[str, Any] = field(default_factory=dict)
