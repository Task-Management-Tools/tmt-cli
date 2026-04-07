from abc import ABC
from dataclasses import dataclass
from enum import Enum
import os

from internal.context.context import TMTContext
from internal.formatting.base import Formatter

@dataclass
class TMTVerifyIssue:
    verifier_name: str
    code: str
    type: TMTVerifyIssueType
    related_file: str
    message: str

class TMTVerifyIssueType(Enum):
    IGNORE = 0
    WARNING = 1
    ERROR = 2

class Verifier(ABC):
    name: str
    registered_issue_code: dict[str, TMTVerifyIssueType]

    def __init__(self, context: TMTContext) -> None:
        self.issues: list[TMTVerifyIssue] = []
        self.issue_print_pointer = 0
        self.context = context

    def add_issue(self, code: str, related_file: str, message: str) -> None:
        if code not in self.registered_issue_code:
            raise KeyError(f"Issue code {self.name}.{code} is not registered.")
        type = self.registered_issue_code[code]
        self.issues.append(TMTVerifyIssue(self.name, code, type, related_file, message))