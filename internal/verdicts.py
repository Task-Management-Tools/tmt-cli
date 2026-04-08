import dataclasses
import enum
import os
import yaml

from internal.context.context import TMTContext
from internal.exceptions import TMTMissingFileError, TMTInvalidConfigError
from internal.outcomes import EvaluationOutcome, EvaluationOutcomeGroup
from .context.paths import ProblemDirectoryHelper

class ExpectedVerdict(enum.Enum):
    ACCEPTED = ("Accepted", "AC", ["accepted", "AC", "correct"], EvaluationOutcomeGroup.ACCEPTED.outcome_list)
    WRONG_ANSWER = ("Wrong Answer", "WA", ["wrong_answer", "WA", "incorrect"], EvaluationOutcomeGroup.WRONG_ANSWER.outcome_list)
    TIME_LIMIT_EXCEEDED = ("Time Limit Exceeded", "TLE", ["time_limit_exceeded", "time_limit", "timeout", "TLE"], 
                           EvaluationOutcomeGroup.TIMEOUT.outcome_list)
    RUNTIME_ERROR = ("Runtime Error", "RTE", ["runtime_error", "RE", "RTE"], EvaluationOutcomeGroup.RUNTIME_ERROR.outcome_list)
    PARTIAL = ("Partially Correct", "PC", ["partial", "PC"], EvaluationOutcomeGroup.PARTIAL.outcome_list)
    OUTPUT_LIMIT = ("Output Limit Exceeded", "OLE", ["output_limit_exceeded", "output_limit", "OLE"], EvaluationOutcomeGroup.OUTPUT_LIMIT.outcome_list)

    # These verdicts should not be used in verdicts.yaml
    JUDGE_ERROR = ("Judge Error", "JE", [], EvaluationOutcomeGroup.JUDGE_ERROR.outcome_list)
    UNKNOWN = ("UNKNOWN", "??", [], [])

    def __init__(self, displayed_name: str, short_name: str, alias: list[str], outcome_list: list[EvaluationOutcome]) -> None:
        self.displayed_name = displayed_name
        self.short_name = short_name
        self.alias = alias
        self.outcome_list = outcome_list

    def __contains__(self, value: object) -> bool:
        return value in self.outcome_list

    def __str__(self) -> str:
        return self.displayed_name

    @classmethod
    def from_str(cls, value: str) -> "ExpectedVerdict":
        for verdict in list(ExpectedVerdict):
            if value in verdict.alias:
                return verdict
        raise ValueError(f"Unknown verdict {value}")

    @classmethod
    def from_evaluation_outcome(cls, outcome: EvaluationOutcome) -> "ExpectedVerdict":
        for verdict in list(ExpectedVerdict):
            if outcome in verdict.outcome_list:
                return verdict
        return ExpectedVerdict.UNKNOWN

    @classmethod
    def _missing_(cls, value: object) -> "ExpectedVerdict":
        if not isinstance(value, str):
            raise ValueError(f"Cannot convert {type(value)} to Verdict")
        return cls.from_str(value)

@dataclasses.dataclass
class VerdictRule:
    must: list[ExpectedVerdict] = dataclasses.field(default_factory=list)
    never: list[ExpectedVerdict] = dataclasses.field(default_factory=list)

    def __str__(self) -> str:
        result = []
        if self.must:
            result.append("must=[" + ", ".join([str(item) for item in self.must]) + "]")
        if self.never:
            result.append("never=[" + ", ".join([str(item) for item in self.never]) + "]")
        return "{" + ', '.join(result) + "}"

    def check_rule(self, verdicts: list[ExpectedVerdict] | set[ExpectedVerdict]) -> bool:
        must_ok = not self.must
        for verdict in verdicts:
            if verdict in self.never or \
                    (ExpectedVerdict.ACCEPTED in self.must and verdict != ExpectedVerdict.ACCEPTED) or \
                    (ExpectedVerdict.PARTIAL in self.must and verdict not in [ExpectedVerdict.ACCEPTED, ExpectedVerdict.PARTIAL]):
                return False
            if verdict in self.must:
                must_ok = True
        if not must_ok:
            return False
        return True

    @classmethod
    def from_raw(cls, data) -> "VerdictRule":
        """
        Covert a raw VerdictRule list.

        Raw data format:
        ```
        str | list[str] | VerdictRule
        ```
        - If the raw data is a str `s`, it is treated as `[s]`.
        - If the raw data is a list[str] `l`, it is treated as `{ must: l }`.
        """

        # verdict: "accepted"
        if isinstance(data, (ExpectedVerdict, str)):
            ret: VerdictRule = cls(must=[ExpectedVerdict(data)])
        elif isinstance(data, list):
            # verdict: ["accepted"]
            ret = cls(must=[ExpectedVerdict(item) for item in data])
        else:
            ret = cls(**data)
            ret.must = [ExpectedVerdict(ret.must)] if isinstance(ret.must, (ExpectedVerdict, str)) \
                        else list(map(ExpectedVerdict, ret.must)) if ret.must \
                        else []
            ret.never = [ExpectedVerdict(ret.never)] if isinstance(ret.never, (ExpectedVerdict, str)) \
                        else list(map(ExpectedVerdict, ret.never)) if ret.never \
                        else []

        found_must = bool(ret.must)
        found_accepted = any(verdict == ExpectedVerdict.ACCEPTED for verdict in ret.must)
        found_partial = any(verdict == ExpectedVerdict.PARTIAL for verdict in ret.must)
        found_others = any(verdict not in [ExpectedVerdict.ACCEPTED, ExpectedVerdict.PARTIAL]
                           for verdict in ret.must + ret.never)
        if not found_must:
            raise ValueError("Verdict rule should contain at least one \"must\" rule")
        if found_accepted and (found_partial or found_others):
            raise ValueError("\"accepted\" in \"must\" rule but the rule contains other verdicts (Hint: \"must: accepted\" also bans all other verdicts.)")
        if found_partial and found_others:
            raise ValueError("\"partial\" in \"must\" rule but the rule contains other verdicts (Hint: \"must: partial\" also bans all incorrect verdicts.)")

        return ret

@dataclasses.dataclass
class ScoreRange:
    min: float | None = None
    max: float | None = None
    exact: float | None = None

    def check_score(self, score: float):
        result = True
        EPS = 1e-9
        if self.exact is not None:
            result = result and abs(score - self.exact) <= EPS
        if self.min is not None:
            result = result and score >= self.min - EPS
        if self.max is not None:
            result = result and score <= self.max + EPS
        return result

    def __str__(self) -> str:
        if self.exact is not None:
            return f"{self.exact}"
        if self.min is None and self.max is None:
            return ""
        min_str = str(self.min) if self.min is not None else ""
        max_str = str(self.max) if self.max is not None else ""
        return f"[{min_str},{max_str}]"

    @classmethod
    def from_raw(cls, data) -> "ScoreRange":
        if isinstance(data, ScoreRange):
            return data
        if data is None:
            return cls()
        if isinstance(data, (str, float, int)):
            return cls(None, None, float(data))
        obj = cls(**data)
        if obj.min is not None:
            obj.min = float(obj.min)
        if obj.max is not None:
            obj.max = float(obj.max)
        if obj.exact is not None:
            obj.exact = float(obj.exact)
        if obj.exact is not None and (obj.min is not None or obj.max is not None):
            raise ValueError("The exact score is set in a score range but min or max score is also set")
        return obj

@dataclasses.dataclass
class SubtaskVerdict:
    subtask: list[str]
    verdict: VerdictRule
    score: ScoreRange = dataclasses.field(default_factory=ScoreRange)

    @classmethod
    def from_raw(cls, data, subtask_list: list[str]) -> "SubtaskVerdict":
        """
        Parse subtask from raw data.

        Raw data format:
        ```
        subtask: str | list[str]
        verdict: Raw VerdictRule
        score:
          - min: 0.0
          - max: 1.0
          - exact: 0.5 # all are optional, exact and min/max should not appear at the same time
        # score: 0.5 # this is treated as exact: 0.5
        ```
        If only a single str is provided in `subtask`,
        it is treated as a list containing the subtask only.
        """

        subtask = cls(**data)

        if not isinstance(subtask.subtask, list):
            subtask.subtask = [subtask.subtask]
        if not isinstance(subtask.subtask, list):
            raise ValueError(f"Invalid subtask: {subtask.subtask}")
        
        subtask.subtask = list(map(str, subtask.subtask))
        for item in subtask.subtask:
            if item not in subtask_list:
                raise ValueError(f"Subtask {item} does not exist")

        subtask.verdict = VerdictRule.from_raw(subtask.verdict)
        subtask.score = ScoreRange.from_raw(subtask.score)
        
        return subtask
        

@dataclasses.dataclass
class SolutionVerdict:
    filename: str
    verdict: VerdictRule
    judge_verdict: ExpectedVerdict | None = None
    subtask: list[SubtaskVerdict] = dataclasses.field(default_factory=list)
    score: ScoreRange = dataclasses.field(default_factory=ScoreRange)

    @classmethod
    def from_raw(cls, data, subtask_list: list[str], helper: ProblemDirectoryHelper) -> "SolutionVerdict":
        solution = cls(**data)

        # check solution file existence
        solution_file = os.path.join(helper.solutions, solution.filename)
        if not os.path.isfile(solution_file):
            raise FileNotFoundError(f"Solution file {solution.filename} not found.")

        if solution.judge_verdict:
            solution.judge_verdict = ExpectedVerdict(solution.judge_verdict)

        solution.verdict = VerdictRule.from_raw(solution.verdict)
        subtasks: list[SubtaskVerdict] = []
        overwrite_subtasks: list[str] = []
        for item in solution.subtask:
            subtask = SubtaskVerdict.from_raw(item, subtask_list)
            subtasks.append(subtask)
            overwrite_subtasks += [item for item in subtask.subtask]
        solution.subtask = subtasks

        solution.score = ScoreRange.from_raw(solution.score)

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
    