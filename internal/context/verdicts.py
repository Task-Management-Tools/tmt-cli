import dataclasses
import enum
from typing import Any
import yaml
from pathlib import Path

from internal.context.context import TMTContext
from internal.exceptions import TMTMissingFileError, TMTInvalidConfigError
from .paths import ProblemDirectoryHelper

class Verdict(enum.Enum):
    ACCEPTED = "accepted"
    WRONG_ANSWER = "wrong_answer"
    TIME_LIMIT_EXCEEDED = "time_limit_exceeded"
    RUNTIME_ERROR = "runtime_error"
    PARTIAL = "partial" # TODO: partial score range

    @classmethod
    def from_str(cls, value: str) -> "Verdict":
        match value:
            case "accepted" | "AC":
                return Verdict.ACCEPTED
            case "wrong_answer" | "WA":
                return Verdict.WRONG_ANSWER
            case "time_limit_exceeded" | "time_limit" | "TLE":
                return Verdict.TIME_LIMIT_EXCEEDED
            case "runtime_error" | "RE":
                return Verdict.RUNTIME_ERROR
            case "partial":
                return Verdict.PARTIAL
        raise ValueError(f"Unknown verdict {value}")

    @classmethod
    def _missing_(cls, value: object) -> "Verdict":
        if not isinstance(value, str):
            raise ValueError(f"Cannot convert {type(value)} to Verdict")
        return cls.from_str(value)

@dataclasses.dataclass
class VerdictRule:
    must: list[Verdict] = dataclasses.field(default_factory=list)
    never: list[Verdict] = dataclasses.field(default_factory=list)

    @classmethod
    def from_raw_list(cls, data) -> list["VerdictRule"]:
        """
        Covert a raw VerdictRule list.

        Raw data format:
        ```
        str | list[str] | list[VerdictRule]
        ```
        - If the raw data is a str `s`, it is treated as `[s]`.
        - If the raw data is a list[str] `l`, it is treated as `[{ must: l }]`.
        """

        # verdict: "accepted"
        if isinstance(data, (Verdict, str)):
            return [cls(must=[Verdict(data)])]
        if isinstance(data, list):
            if not data:
                raise ValueError("Verdict rule list should contain at least one \"must\" rule")
            
            first = data[0]

            # verdict: ["accepted"]
            if isinstance(first, (Verdict, str)):
                return [cls(must=[Verdict(item) for item in data])]

            if isinstance(first, dict):
                found_must = False
                rule_list: list[VerdictRule] = []
                for rule in data:
                    rule = cls(**rule)
                    rule.must = list(map(Verdict, rule.must))
                    rule.never = list(map(Verdict, rule.never))
                    if rule.must:
                        found_must = True
                    rule_list.append(rule)
                
                if not found_must:
                    raise ValueError("Verdict rule list should contain at least one \"must\" rule")

                return rule_list

        raise ValueError(f"Invalid verdict rule format: {data}")

@dataclasses.dataclass
class SubtaskVerdict:
    subtask: list[str]
    verdict: list[VerdictRule]

    @classmethod
    def from_raw(cls, data, subtask_list: list[str]) -> "SubtaskVerdict":
        """
        Parse subtask from raw data.

        Raw data format:
        ```
        subtask: str | list[str]
        verdict: Raw VerdictRule list
        ```
        If only a single str is provided in `subtask`,
        it is treated as a list containing the subtask only.
        """

        subtask = cls(**data)

        if isinstance(subtask.subtask, str):
            subtask.subtask = [subtask.subtask]
        if not isinstance(subtask.subtask, list):
            raise ValueError(f"Invalid subtask: {subtask.subtask}")
        
        for item in subtask.subtask:
            if item not in subtask_list:
                raise ValueError(f"Subtask {item} does not exist")

        subtask.verdict = VerdictRule.from_raw_list(subtask.verdict)
        
        return subtask
        

@dataclasses.dataclass
class SolutionVerdict:
    filename: str
    verdict: list[VerdictRule]
    judge_verdict: Verdict | None = None
    subtask: list[SubtaskVerdict] = dataclasses.field(default_factory=list)

    @classmethod
    def from_raw(cls, data, subtask_list: list[str], helper: ProblemDirectoryHelper) -> "SolutionVerdict":
        solution = cls(**data)

        # check solution file existence
        helper.replace_with_solution(solution.filename)

        if solution.judge_verdict:
            solution.judge_verdict = Verdict(solution.judge_verdict)

        solution.verdict = VerdictRule.from_raw_list(solution.verdict)
        subtasks: list[SubtaskVerdict] = []
        overwrite_subtasks: list[str] = []
        for item in solution.subtask:
            subtask = SubtaskVerdict.from_raw(item, subtask_list)
            subtasks.append(subtask)
            overwrite_subtasks += [item for item in subtask.subtask]
        solution.subtask = subtasks

        # check duplicates
        seen = set()
        for subtask in overwrite_subtasks:
            if subtask in seen:
                raise ValueError(f"Subtask {subtask} duplicates in verdict rules of {solution.filename}")
            seen.add(subtask)

        return solution

def parse_verdicts(context: TMTContext):
    helper = context.path
    yaml_path = helper.verdicts_yaml
    try:
        with open(yaml_path, "r") as file:
            verdicts_yaml = yaml.safe_load(file)
    except (FileNotFoundError, IsADirectoryError, PermissionError) as e: 
        raise TMTMissingFileError("config", yaml_path) from e
    except yaml.YAMLError as e:
        raise TMTInvalidConfigError(yaml_path) from e
    
    if not isinstance(verdicts_yaml, list):
        raise ValueError("verdicts.yaml should contain a list.")
    
    solution_list: list[SolutionVerdict] = []
    subtask_list: list[str] = list(context.recipe.subtasks.keys())
    for item in verdicts_yaml:
        solution_list.append(SolutionVerdict.from_raw(item, subtask_list, helper))

    return solution_list
    