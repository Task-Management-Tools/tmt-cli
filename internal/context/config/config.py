import resource
from dataclasses import dataclass, fields
from enum import Enum
from typing import Any, Literal, TypeAlias, cast

from internal.utils import assert_never

from .answer import AnswerGeneration, parse_answer_generation
from .checker import Checker, parse_checker
from .interactor import Interactor, parse_interactor
from .manager import Manager, parse_manager
from .parser import (
    DictParser,
    TMTConfigError,
    TMTConfigErrorsList,
    check_error,
)
from .solution import (
    Solution,
    SolutionCompilation,
    SolutionExecutionCommunication,
    SolutionExecutionStandalone,
    parse_solution,
)
from .validator import Validator, parse_validator


@dataclass(frozen=True)
class JudgeSettings:
    name: str
    display_score: bool
    display_testsets: bool

    def __str__(self):
        return self.name


class JudgeConvention(Enum):
    ICPC = JudgeSettings(name="icpc", display_score=False, display_testsets=True)
    CMS = JudgeSettings(name="cms", display_score=True, display_testsets=False)
    TIOJ_OLD = JudgeSettings(
        name="old-tioj", display_score=True, display_testsets=False
    )
    TIOJ_NEW = JudgeSettings(
        name="new-tioj", display_score=True, display_testsets=False
    )

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            for member in cls:
                if member.value.name == value:
                    return member
        return None

    def __getattr__(self, item):
        # Guard against infinite recursion during pickling/copying
        if item.startswith("_"):
            raise AttributeError(item)
        return getattr(self._value_, item)


class ProblemType(Enum):
    BATCH = "batch"
    INTERACTIVE = "interactive"
    COMMUNICATION = "communication"
    OUTPUT_ONLY = "output-only"


@dataclass
class ProblemConfigBase:
    title: str
    short_name: str
    description: str | None
    tmt_version: str
    input_extension: str
    output_extension: str
    judge_convention: JudgeConvention
    validator: Validator
    answer_generation: AnswerGeneration
    compile_time_limit_sec: float
    compile_memory_limit_mib: int
    trusted_step_time_limit_sec = 10.0
    trusted_step_memory_limit_mib = 4 * 1024
    trusted_step_output_limit_mib = resource.RLIM_INFINITY


@dataclass
class ProblemConfigBatch(ProblemConfigBase):
    problem_type: Literal[ProblemType.BATCH]
    solution: Solution[SolutionCompilation, SolutionExecutionStandalone]
    checker: Checker | None
    interactor: None
    manager: None


@dataclass
class ProblemConfigInteractive(ProblemConfigBase):
    problem_type: Literal[ProblemType.INTERACTIVE]
    solution: Solution[SolutionCompilation, SolutionExecutionStandalone]
    checker: None
    interactor: Interactor
    manager: None


@dataclass
class ProblemConfigCommunication(ProblemConfigBase):
    problem_type: Literal[ProblemType.COMMUNICATION]
    solution: Solution[SolutionCompilation, SolutionExecutionCommunication]
    checker: None
    interactor: None
    manager: Manager


@dataclass
class ProblemConfigOutputOnly(ProblemConfigBase):
    problem_type: Literal[ProblemType.OUTPUT_ONLY]
    solution: Solution[SolutionCompilation, SolutionExecutionStandalone]
    checker: Checker | None
    interactor: None
    manager: None


ProblemConfig: TypeAlias = (
    ProblemConfigBatch
    | ProblemConfigInteractive
    | ProblemConfigCommunication
    | ProblemConfigOutputOnly
)


def parse_problem_yaml(data: dict) -> ProblemConfig | TMTConfigErrorsList:
    parser = DictParser(data, "")

    # fmt: off
    title                = parser.pop("title",                    str)
    short_name           = parser.pop("short_name",               str)
    description          = parser.pop_optional("description",     str)
    tmt_version          = parser.pop("tmt_version",              str)
    input_extension      = parser.pop("input_extension",          str)
    output_extension     = parser.pop("output_extension",         str)
    judge_convention     = parser.pop("judge_convention",         JudgeConvention)
    prob_type            = parser.pop("problem_type",             ProblemType)
    validator            = parser.pop_then("validator",           parse_validator)
    solution             = parser.pop_then("solution",            parse_solution)
    answer_generation    = parser.pop_then("answer_generation",   parse_answer_generation)
    checker              = parser.pop_optional_then("checker",    parse_checker)
    interactor           = parser.pop_optional_then("interactor", parse_interactor)
    manager              = parser.pop_optional_then("manager",    parse_manager)
    comp_time_lim_sec    = parser.pop_time_to_second("compile_time_limit",
                                                     default=60.0)
    comp_memory_lim_mib  = parser.pop_bytes_to_mib("compile_memory_limit",
                                                   allow_unlimited=True,
                                                   default=resource.RLIM_INFINITY)
    # fmt: on

    parser.discard("extra")
    parser.reject_remaining()

    # TODO warn for tmt_version
    if isinstance(input_extension, str) and not input_extension.startswith("."):
        parser.add_err("Config 'input_extension' should start with a dot.")
    if isinstance(output_extension, str) and not output_extension.startswith("."):
        parser.add_err("Config 'output_extension' should start with a dot.")
    if isinstance(input_extension, str) and input_extension == output_extension:
        parser.add_err(
            "Config 'input_extension' and 'output_extension' must not be the same."
        )

    # Deferred common construction
    def get_common() -> dict[str, Any]:
        base = ProblemConfigBase(
            title=check_error(title),
            short_name=check_error(short_name),
            description=check_error(description),
            tmt_version=check_error(tmt_version),
            input_extension=check_error(input_extension),
            output_extension=check_error(output_extension),
            judge_convention=check_error(judge_convention),
            validator=check_error(validator),
            answer_generation=check_error(answer_generation),
            compile_time_limit_sec=check_error(comp_time_lim_sec),
            compile_memory_limit_mib=check_error(comp_memory_lim_mib),
        )
        return {f.name: getattr(base, f.name) for f in fields(base)}

    def missing_config_prob_type(name: str, prob_type: ProblemType):
        return f"{name} must be present when 'prob_type' is '{prob_type.value}'."

    def extra_config_prob_type(name: str, prob_type: ProblemType):
        return f"{name} must not be present when '{prob_type}' is '{prob_type.value}'."

    def check_no_checker(prob_type: ProblemType):
        if isinstance(checker, Checker):
            parser.add_err(extra_config_prob_type("Config 'checker'", prob_type))

    def check_no_interactor(prob_type: ProblemType):
        if isinstance(interactor, Interactor):
            parser.add_err(extra_config_prob_type("Config 'interactor'", prob_type))

    def check_no_manager(prob_type: ProblemType):
        if isinstance(manager, Manager):
            parser.add_err(extra_config_prob_type("Config 'manager'", prob_type))

    def check_checker_args():
        if (
            not isinstance(checker, Checker)
            or judge_convention is not JudgeConvention.CMS
        ):
            return
        if len(checker.arguments):
            parser.add_err(
                f"Config 'checker.arguments' must be empty or an empty list when 'judge_convention' is '{judge_convention.value}'"
            )

    def check_solution_param(prob_type: ProblemType, is_communication: bool):
        if not isinstance(solution, Solution):
            return
        has_param = isinstance(solution.execution, SolutionExecutionCommunication)
        name = "Config for communication problem in solution (num_procs, use_fifo)"
        if is_communication and not has_param:
            parser.add_err(missing_config_prob_type(name, prob_type))
        if not is_communication and has_param:
            parser.add_err(extra_config_prob_type(name, prob_type))

    match prob_type:
        case ProblemType.BATCH:
            check_no_interactor(prob_type)
            check_no_manager(prob_type)
            check_solution_param(prob_type, is_communication=False)
            check_checker_args()

            if parser.errors:
                return parser.errors

            assert interactor is None and manager is None
            solution = cast(
                Solution[SolutionCompilation, SolutionExecutionStandalone],
                check_error(solution),
            )
            assert isinstance(solution.execution, SolutionExecutionStandalone)
            return ProblemConfigBatch(
                **get_common(),
                problem_type=prob_type,
                solution=solution,
                checker=check_error(checker),
                interactor=check_error(interactor),
                manager=check_error(manager),
            )

        case ProblemType.INTERACTIVE:
            check_no_checker(prob_type)
            check_no_manager(prob_type)
            check_solution_param(prob_type, is_communication=False)
            if interactor is None:
                parser.add_err(
                    missing_config_prob_type("Config 'interactor'", prob_type)
                )

            if parser.errors:
                return parser.errors

            assert checker is None and manager is None
            assert interactor is not None
            solution = cast(
                Solution[SolutionCompilation, SolutionExecutionStandalone],
                check_error(solution),
            )
            assert isinstance(solution.execution, SolutionExecutionStandalone)
            return ProblemConfigInteractive(
                **get_common(),
                problem_type=prob_type,
                solution=solution,
                checker=check_error(checker),
                interactor=check_error(interactor),
                manager=check_error(manager),
            )

        case ProblemType.COMMUNICATION:
            check_no_checker(prob_type)
            check_no_interactor(prob_type)
            check_solution_param(prob_type, is_communication=True)
            if manager is None:
                parser.add_err(missing_config_prob_type("Config 'manager'", prob_type))

            if parser.errors:
                return parser.errors

            assert checker is None and interactor is None
            assert manager is not None
            solution = cast(
                Solution[SolutionCompilation, SolutionExecutionCommunication],
                check_error(solution),
            )
            assert isinstance(solution.execution, SolutionExecutionCommunication)
            return ProblemConfigCommunication(
                **get_common(),
                problem_type=prob_type,
                solution=solution,
                checker=check_error(checker),
                interactor=check_error(interactor),
                manager=check_error(manager),
            )

        case ProblemType.OUTPUT_ONLY:
            check_no_interactor(prob_type)
            check_no_manager(prob_type)
            check_solution_param(prob_type, is_communication=False)
            check_checker_args()

            if parser.errors:
                return parser.errors

            assert interactor is None and manager is None
            solution = cast(
                Solution[SolutionCompilation, SolutionExecutionStandalone],
                check_error(solution),
            )
            assert isinstance(solution.execution, SolutionExecutionStandalone)
            return ProblemConfigOutputOnly(
                **get_common(),
                problem_type=prob_type,
                solution=solution,
                checker=check_error(checker),
                interactor=check_error(interactor),
                manager=check_error(manager),
            )

        case TMTConfigError():
            return parser.errors

        case _:
            assert_never(prob_type)
