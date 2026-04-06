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
        self.issues.append(TMTVerifyIssue(self.name, code, related_file, message))

    def flush_issue_message(self, formatter: Formatter):
        while self.issue_print_pointer < len(self.issues):
            issue = self.issues[self.issue_print_pointer]
            self.issue_print_pointer += 1
            issue_type = self.registered_issue_code[issue.code]
            relative_path = os.path.relpath(issue.related_file, self.context.path.problem_dir)
            print_message = f"{relative_path}: {issue.message}"
            match issue_type:
                case TMTVerifyIssueType.IGNORE:
                    pass
                case TMTVerifyIssueType.WARNING:
                    formatter.println(formatter.ANSI_YELLOW, print_message, formatter.ANSI_RESET)
                case TMTVerifyIssueType.ERROR:
                    formatter.println(formatter.ANSI_RED, print_message, formatter.ANSI_RESET)
                case _:
                    raise NotImplementedError(f"Unknown issue type {issue_type}.")
