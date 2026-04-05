import dataclasses
import enum
import os
from typing import Any
import yaml
from pathlib import Path

from internal.context.context import TMTContext
from internal.exceptions import TMTMissingFileError, TMTInvalidConfigError
from internal.outcomes import EvaluationOutcome
from .paths import ProblemDirectoryHelper

class Verdict(enum.Enum):
    ACCEPTED = "accepted"
    WRONG_ANSWER = "wrong_answer"
    TIME_LIMIT_EXCEEDED = "time_limit_exceeded"
    RUNTIME_ERROR = "runtime_error"
    PARTIAL = "partial" # TODO: partial score range

    # These verdicts should not be used in verdicts.yaml
    TIME_LIMIT_EXCEEDED_WALL = "internal_time_limit_exceeded_wall"
    JUDGE_ERROR = "internal_judge_error"
    UNKNOWN = "internal_unknown"

    @classmethod
    def from_str(cls, value: str) -> "Verdict":
        match value:
            case "accepted" | "AC":
                return Verdict.ACCEPTED
            case "wrong_answer" | "WA":
                return Verdict.WRONG_ANSWER
            case "time_limit_exceeded" | "time_limit" | "TLE":
                return Verdict.TIME_LIMIT_EXCEEDED
            case "runtime_error" | "RTE" | "RE":
                return Verdict.RUNTIME_ERROR
            case "partial" | "PA" | "PC":
                return Verdict.PARTIAL
        raise ValueError(f"Unknown verdict {value}")

    @classmethod
    def from_evaluation_outcome(cls, outcome: EvaluationOutcome) -> "Verdict":
        # TODO: copied from TerminalFormatter, may refactor
        group_accepted = [EvaluationOutcome.ACCEPTED]
        group_partial = [EvaluationOutcome.PARTIAL]
        group_wrong_answer = [
            EvaluationOutcome.WRONG,
            EvaluationOutcome.NO_FILE,
            EvaluationOutcome.NO_OUTPUT,
        ]
        group_timeout = [EvaluationOutcome.TIMEOUT, EvaluationOutcome.TIMEOUT_WALL]
        group_runtime_error = [
            EvaluationOutcome.RUNERROR_OUTPUT,
            EvaluationOutcome.RUNERROR_SIGNAL,
            EvaluationOutcome.RUNERROR_EXITCODE,
            EvaluationOutcome.RUNERROR_MEMORY,
        ]
        group_judge_error = [
            EvaluationOutcome.MANAGER_CRASHED,
            EvaluationOutcome.MANAGER_TIMEOUT,
            EvaluationOutcome.CHECKER_CRASHED,
            EvaluationOutcome.CHECKER_FAILED,
            EvaluationOutcome.CHECKER_TIMEDOUT,
            EvaluationOutcome.INTERNAL_ERROR,
        ]

        if outcome in group_accepted:
            return Verdict.ACCEPTED
        elif outcome in group_partial:
            return Verdict.PARTIAL
        elif outcome in group_wrong_answer:
            return Verdict.WRONG_ANSWER
        elif outcome in group_timeout:
            if outcome == EvaluationOutcome.TIMEOUT_WALL:
                return Verdict.TIME_LIMIT_EXCEEDED_WALL
            return Verdict.TIME_LIMIT_EXCEEDED
        elif outcome in group_runtime_error:
            return Verdict.RUNTIME_ERROR
        elif outcome in group_judge_error:
            return Verdict.JUDGE_ERROR
        else:
            return Verdict.UNKNOWN

    @classmethod
    def _missing_(cls, value: object) -> "Verdict":
        if not isinstance(value, str):
            raise ValueError(f"Cannot convert {type(value)} to Verdict")
        return cls.from_str(value)

@dataclasses.dataclass
class VerdictRule:
    must: list[Verdict] = dataclasses.field(default_factory=list)
    never: list[Verdict] = dataclasses.field(default_factory=list)

    def check_rule(self, verdicts: list[Verdict] | set[Verdict]) -> bool:
        must_ok = not self.must
        for verdict in verdicts:
            if verdict in self.never or \
                    (Verdict.ACCEPTED in self.must and verdict != Verdict.ACCEPTED) or \
                    (Verdict.PARTIAL in self.must and verdict not in [Verdict.ACCEPTED, Verdict.PARTIAL]):
                return False
            if verdict in self.must:
                must_ok = True
        if not must_ok:
            return False
        return True

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
        # TODO: If `must` contains ACCEPTED or PARTIAL, it should be the only item in `must` and `never` should be empty.

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
                    if isinstance(rule.must, (Verdict, str)):
                        rule.must = [Verdict(rule.must)]
                    else:
                        rule.must = list(map(Verdict, rule.must))
                    if isinstance(rule.never, (Verdict, str)):
                        rule.never = [Verdict(rule.never)]
                    else:
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
        solution_file = os.path.join(helper.solutions, solution.filename)
        if not os.path.isfile(solution_file):
            raise FileNotFoundError(f"Solution file {solution} not found.")

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
    