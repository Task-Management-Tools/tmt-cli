from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal, TypeAlias

from internal.utils import assert_never

from .parser import DictParser, TMTConfigError, TMTConfigErrorsList, unwrap


class CheckerType(Enum):
    DEFAULT = "default"
    CUSTOM = "custom"


@dataclass
class CheckerBase:
    type: CheckerType
    filename: str | None
    arguments: list[str]
    check_forced_output: bool
    check_generated_output: bool


@dataclass
class CheckerDefault(CheckerBase):
    type: Literal[CheckerType.DEFAULT]
    filename: None


@dataclass
class CheckerCustom(CheckerBase):
    type: Literal[CheckerType.CUSTOM]
    filename: str


Checker: TypeAlias = CheckerDefault | CheckerCustom


def parse_checker(data: Any) -> Checker | TMTConfigErrorsList:
    if isinstance(data, str):
        # Fall through for default args
        data = {"type": "custom", "filename": data}

    if not isinstance(data, dict):
        return TMTConfigErrorsList.single_bad_complex_type("checker (object)", data)

    parser = DictParser(data, "checker")
    type_ = parser.pop("type", CheckerType)
    filename = parser.pop_optional("filename", str)
    arguments = parser.pop_default("arguments", str, "")
    check_forced_output = parser.pop_default("check_forced_output", bool, True)
    check_generated_output = parser.pop_default("check_generated_output", bool, True)
    parser.reject_remaining()

    match type_:
        case TMTConfigError():
            return parser.errors
        case CheckerType.DEFAULT:
            # Also match error, since filename should not exist in the first place
            if filename is not None:
                parser.add_err(
                    "Config checker.filename must not be present when checker.type is set to default."
                )
                return parser.errors

            return parser.errors or CheckerDefault(
                type=type_,
                filename=filename,
                arguments=unwrap(arguments).split(),
                check_forced_output=unwrap(check_forced_output),
                check_generated_output=unwrap(check_generated_output),
            )

        case CheckerType.CUSTOM:
            if filename is None:
                parser.add_err(
                    "Config checker.filename must be present when checker.type is set to custom."
                )
                return parser.errors

            return parser.errors or CheckerCustom(
                type=type_,
                filename=unwrap(filename),
                arguments=unwrap(arguments).split(),
                check_forced_output=unwrap(check_forced_output),
                check_generated_output=unwrap(check_generated_output),
            )
        case _:
            assert_never()
