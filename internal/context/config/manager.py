from dataclasses import dataclass
from typing import Any

from .parser import DictParser, TMTConfigErrorsList, check_error


@dataclass
class Manager:
    filename: str


def parse_manager(data: Any) -> Manager | TMTConfigErrorsList:
    if isinstance(data, str):
        return Manager(filename=data)

    if not isinstance(data, dict):
        return TMTConfigErrorsList.single_bad_complex_type("manager (config)", data)

    parser = DictParser(data, "manager")
    filename = parser.pop("filename", str)
    parser.reject_remaining()

    return parser.errors or Manager(filename=check_error(filename))
