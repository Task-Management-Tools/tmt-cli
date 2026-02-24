import enum
import resource
import re
import dataclasses


class JudgeConvention(enum.Enum):
    ICPC = "icpc"
    CMS = "cms"
    TIOJ_OLD = "old-tioj"
    TIOJ_NEW = "new-tioj"


class ProblemType(enum.Enum):
    BATCH = "batch"
    INTERACTIVE = "interactive"


class CheckerType(enum.Enum):
    DEFAULT = "default"
    CUSTOM = "custom"


@dataclasses.dataclass
class Checker:
    type: CheckerType
    filename: str | None = None
    arguments: list[str] | None = None
    check_forced_output: bool = True
    check_generated_output: bool = True

    def __post_init__(self):
        self.type = CheckerType(self.type)
        if self.arguments is None:
            self.arguments = []
        else:
            self.arguments = self.arguments.split()


class ValidatorType(enum.Enum):
    DEFAULT = "default"
    PROVER = "prover"


@dataclasses.dataclass
class Validator:
    type: ValidatorType

    def __post_init__(self):
        self.type = ValidatorType(self.type)
        if self.type is not ValidatorType.DEFAULT:
            raise ValueError(f"Validator type {self.type} is not supported yet.")


@dataclasses.dataclass
class Interactor:
    filename: str
    arguments: str | None = None


# TODO: document time limit format and memory limit format
def parse_time_to_second(field_name: str, input_str: str) -> float:
    match = re.fullmatch(r"(\d+|\d+\.\d+)\s*(ms|s)", input_str)
    if match is None:
        raise ValueError(f'{field_name} "{input_str}" is invalid.')
    if match.group(2) == "ms":
        return float(match.group(1)) / 1000.0
    else:
        return float(match.group(1))


def parse_bytes_to_mib(field_name: str, input_str: str) -> int:
    match = re.fullmatch(r"(\d+)\s*(G|GB|GiB|M|MB|MiB)", input_str)
    if match is None:
        raise ValueError(f'{field_name} "{input_str}" is invalid.')
    if match.group(2).startswith("G"):
        return int(match.group(1)) * 1024
    else:
        return int(match.group(1))


class SolutionType(enum.Enum):
    DEFAULT = "default"
    GRADER = "grader"  # means the solution should be compiled with grader


@dataclasses.dataclass
class Solution:
    type: SolutionType
    time_limit: str
    time_limit_sec: float = dataclasses.field(init=False)
    memory_limit: str
    memory_limit_mib: int = dataclasses.field(init=False)
    output_limit: str
    output_limit_mib: int = dataclasses.field(init=False)

    def parse_limits(self):
        self.time_limit_sec = parse_time_to_second(
            "solution.time_limit", self.time_limit
        )
        self.memory_limit_mib = parse_bytes_to_mib(
            "solution.time_limit", self.memory_limit
        )
        if self.output_limit == "unlimited":
            self.output_limit_mib = resource.RLIM_INFINITY
        else:
            self.output_limit_mib = parse_bytes_to_mib(
                "solution.time_limit", self.output_limit
            )

    def __post_init__(self):
        self.type = SolutionType(self.type)
        self.parse_limits()

        if self.type is not SolutionType.DEFAULT:
            raise ValueError(f"solution.type {self.type} is not supported yet.")


class AnswerGenerationType(enum.Enum):
    SOLUTION = "solution"
    GENERATOR = "generator"


@dataclasses.dataclass
class AnswerGeneration:
    type: AnswerGenerationType
    filename: str | None = None

    def __post_init__(self):
        self.type = AnswerGenerationType(self.type)
        if self.type is not AnswerGenerationType.SOLUTION:
            raise ValueError(
                f"answer_generation.type {self.type} is not supported yet."
            )

        if self.type is AnswerGenerationType.SOLUTION:
            if self.filename is None:
                raise ValueError(
                    "answer_generation.filename must be specified "
                    "when type is 'solution'."
                )


@dataclasses.dataclass
class TMTConfig:
    title: str | None
    short_name: str
    description: str | None

    input_extension: str
    output_extension: str

    judge_convention: JudgeConvention
    problem_type: ProblemType

    validator: Validator
    solution: Solution
    answer_generation: AnswerGeneration

    checker: Checker | None = None
    interactor: Interactor | None = None
    # TODO: manager

    compile_time_limit: str | None = None
    compile_memory_limit: str | None = None

    def __post_init__(self):
        if not self.input_extension.startswith("."):
            raise ValueError('input_extension should start with ".".')
        if not self.output_extension.startswith("."):
            raise ValueError('output_extension should start with ".".')

        self.judge_convention = JudgeConvention(self.judge_convention)
        self.problem_type = ProblemType(self.problem_type)

        self.validator = Validator(**self.validator)
        self.solution = Solution(**self.solution)
        self.answer_generation = AnswerGeneration(**self.answer_generation)

        if self.checker is not None:
            self.checker = Checker(**self.checker)
        if self.interactor is not None:
            self.interactor = Interactor(**self.interactor)

        # TODO: validate the fields,
        # e.g. batch problem should not have interactor
        if self.problem_type is ProblemType.BATCH:
            if self.interactor is not None:
                raise ValueError(
                    "Interactor should not be specified when the problem type is batch."
                )
        elif self.problem_type is ProblemType.INTERACTIVE:
            if self.interactor is None:
                raise ValueError(
                    "Interactor should be specified "
                    "when the problem type is interactive."
                )

        if self.problem_type is not ProblemType.BATCH:
            if self.checker is not None:
                raise ValueError(
                    "Checker should not be specified "
                    "when the problem type is not batch."
                )

        # TODO maybe these should be in compiler.yaml
        if self.compile_time_limit is None:
            self.compile_time_limit_sec = 60.0  # default one minute
        else:
            self.compile_time_limit_sec = parse_time_to_second(
                "compile_time_limit", self.compile_time_limit
            )
        if self.compile_memory_limit is None:
            self.compile_memory_limit_mib = resource.RLIM_INFINITY  # default unlimited
        elif self.compile_memory_limit == "unlimited":
            self.compile_memory_limit_mib = resource.RLIM_INFINITY
        else:
            self.compile_memory_limit_sec = parse_bytes_to_mib(
                "compile_memory_limit", self.compile_memory_limit
            )

        self.trusted_step_time_limit_sec = 10.0
        self.trusted_step_memory_limit_mib = 4 * 1024
        self.trusted_step_output_limit_mib = resource.RLIM_INFINITY
