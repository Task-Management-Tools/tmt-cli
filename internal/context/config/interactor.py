from dataclasses import dataclass
from typing import Any

from .parser import DictParser, TMTConfigErrorsList, check_error


@dataclass
class Interactor:
    filename: str
    arguments: list[str]


def parse_interactor(data: Any) -> Interactor | TMTConfigErrorsList:
    if isinstance(data, str):
        return Interactor(filename=data, arguments=[])

    if not isinstance(data, dict):
        return TMTConfigErrorsList.single_bad_complex_type("interactor (config)", data)

    parser = DictParser(data, "interactor")
    filename = parser.pop("filename", str)
    arguments = parser.pop_default("arguments", str, "")
    parser.reject_remaining()

    return parser.errors or Interactor(
        filename=check_error(filename), arguments=check_error(arguments).split()
    )
