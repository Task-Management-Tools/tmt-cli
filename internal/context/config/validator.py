from dataclasses import dataclass
from enum import Enum
from typing import Any

from .parser import DictParser, TMTConfigErrorsList, unwrap


class ValidatorType(Enum):
    DEFAULT = "default"
    # PROVER = "prover"


@dataclass
class Validator:
    type: ValidatorType


def parse_validator(data: Any) -> Validator | TMTConfigErrorsList:
    if isinstance(data, str):
        # Fall through for enum check
        data = {"type": data}

    if not isinstance(data, dict):
        return TMTConfigErrorsList.single_bad_complex_type("validator (config)", data)

    parser = DictParser(data, "validator")
    type_ = parser.pop("type", ValidatorType)
    parser.reject_remaining()

    return parser.errors or Validator(type=unwrap(type_))
