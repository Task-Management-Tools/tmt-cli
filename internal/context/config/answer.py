from dataclasses import dataclass
from enum import Enum
from typing import Any

from .parser import DictParser, TMTConfigErrorsList, check_error


class AnswerGenerationType(Enum):
    SOLUTION = "solution"
    # GENERATOR = "generator"


@dataclass
class AnswerGeneration:
    type: AnswerGenerationType
    filename: str


def parse_answer_generation(data: Any) -> AnswerGeneration | TMTConfigErrorsList:
    if isinstance(data, str):
        return AnswerGeneration(type=AnswerGenerationType.SOLUTION, filename=data)

    if not isinstance(data, dict):
        return TMTConfigErrorsList.single_bad_complex_type(
            "answer_generation (config)", data
        )

    parser = DictParser(data, "answer_generation")
    type_ = parser.pop("type", AnswerGenerationType)
    filename = parser.pop("filename", str)
    parser.reject_remaining()

    return parser.errors or AnswerGeneration(
        type=check_error(type_), filename=check_error(filename)
    )
