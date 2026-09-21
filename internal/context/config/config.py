import resource
from dataclasses import dataclass, fields
from enum import Enum
from typing import Any, Literal, TypeAlias, TypeVar, cast

from internal.utils import assert_never

from .answer import AnswerGeneration, parse_answer_generation
from .checker import Checker, parse_checker
from .interactor import Interactor, parse_interactor
from .manager import Manager, parse_manager
from .parser import (
    DictParser,
    TMTConfigError,
    TMTConfigErrorsList,
    unwrap,
)
from .solution import (
    Solution,
    SolutionCompilation,
    SolutionExecutionCommunication,
    SolutionExecutionMultipass,
    SolutionExecutionStandalone,
    parse_solution,
)
from .validator import Validator, parse_validator


T = TypeVar("T")


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
    MULTI_PASS = "multi-pass"


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


@dataclass
class ProblemConfigMultipass(ProblemConfigBase):
    problem_type: Literal[ProblemType.MULTI_PASS]
    solution: Solution[SolutionCompilation, SolutionExecutionMultipass]
    checker: None
    interactor: Interactor
    manager: None


ProblemConfig: TypeAlias = (
    ProblemConfigBatch
    | ProblemConfigInteractive
    | ProblemConfigCommunication
    | ProblemConfigOutputOnly
    | ProblemConfigMultipass
)

T = TypeVar("T")


class _ConfigDictParser(DictParser):
    def check_config_none(
        self, key: str, problem_type: ProblemType, val: T | None | TMTConfigErrorsList
    ) -> None | TMTConfigErrorsList:
        if val is not None and not isinstance(val, TMTConfigErrorsList):
            err = self.add_err(
                f"Config {key} must not be present when 'problem_type' is '{problem_type.value}'."
            )
            return TMTConfigErrorsList([err])
        return val

    def check_config_exists(
        self, key: str, problem_type: ProblemType, val: T | None | TMTConfigErrorsList
    ) -> T | TMTConfigErrorsList:
        if val is None:
            err = self.add_err(
                f"Config {key} must be present when 'problem_type' is '{problem_type.value}'."
            )
            return TMTConfigErrorsList([err])
        return val

    def check_checker_args(
        self,
        judge_convention: JudgeConvention | TMTConfigError,
        checker: Checker | None | TMTConfigErrorsList,
    ):
        if (
            judge_convention is JudgeConvention.CMS
            and isinstance(checker, Checker)
            and checker.arguments
        ):
            return self.add_err(
                f"Config 'checker.arguments' must be empty when 'judge_convention' is '{judge_convention.value}'."
            )
        return checker


def parse_problem_yaml(data: dict) -> ProblemConfig | TMTConfigErrorsList:
    parser = _ConfigDictParser(data, "")

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
            title=unwrap(title),
            short_name=unwrap(short_name),
            description=unwrap(description),
            tmt_version=unwrap(tmt_version),
            input_extension=unwrap(input_extension),
            output_extension=unwrap(output_extension),
            judge_convention=unwrap(judge_convention),
            validator=unwrap(validator),
            answer_generation=unwrap(answer_generation),
            compile_time_limit_sec=unwrap(comp_time_lim_sec),
            compile_memory_limit_mib=unwrap(comp_memory_lim_mib),
        )
        return {f.name: getattr(base, f.name) for f in fields(base)}

    def check_solution_param(prob_type: ProblemType, exe_type: type):
        if not isinstance(solution, Solution):
            return
        entry_name = {
            SolutionExecutionStandalone: None,
            SolutionExecutionCommunication: "Config for communication problem in solution (num_procs, use_fifo)",
            SolutionExecutionMultipass: "Config for multi-pass problem in solution (max_passes)",
        }
        if not isinstance(solution.execution, exe_type):
            missing_name = entry_name[exe_type]
            if missing_name is not None:
                parser.add_err(
                    f"{missing_name} must be present when 'problem_type' is '{prob_type.value}'."
                )
            extra_name = entry_name[type(solution.execution)]
            if extra_name is not None:
                parser.add_err(
                    f"{missing_name} must not be present when 'problem_type' is '{prob_type.value}'."
                )

    # It is fine that we use check_subconfig_none/exists early, because we don't use
    # the value later.
    match prob_type:
        case ProblemType.BATCH:
            checker = parser.check_checker_args(judge_convention, checker)
            interactor = parser.check_config_none("interactor", prob_type, interactor)
            manager = parser.check_config_none("manager", prob_type, manager)
            check_solution_param(prob_type, SolutionExecutionStandalone)

            if parser.errors:
                return parser.errors

            solution = cast(
                Solution[SolutionCompilation, SolutionExecutionStandalone],
                unwrap(solution),
            )
            assert isinstance(solution.execution, SolutionExecutionStandalone)
            return ProblemConfigBatch(
                **get_common(),
                problem_type=prob_type,
                solution=solution,
                checker=unwrap(checker),
                interactor=unwrap(interactor),
                manager=unwrap(manager),
            )

        case ProblemType.INTERACTIVE:
            checker = parser.check_config_none("checker", prob_type, checker)
            interactor = parser.check_config_exists("interactor", prob_type, interactor)
            manager = parser.check_config_none("manager", prob_type, manager)
            check_solution_param(prob_type, SolutionExecutionStandalone)

            if parser.errors:
                return parser.errors

            solution = cast(
                Solution[SolutionCompilation, SolutionExecutionStandalone],
                unwrap(solution),
            )
            assert isinstance(solution.execution, SolutionExecutionStandalone)
            return ProblemConfigInteractive(
                **get_common(),
                problem_type=prob_type,
                solution=solution,
                checker=unwrap(checker),
                interactor=unwrap(interactor),
                manager=unwrap(manager),
            )

        case ProblemType.COMMUNICATION:
            checker = parser.check_config_none("checker", prob_type, checker)
            interactor = parser.check_config_none("interactor", prob_type, interactor)
            manager = parser.check_config_exists("manager", prob_type, manager)
            check_solution_param(prob_type, SolutionExecutionCommunication)

            if parser.errors:
                return parser.errors

            solution = cast(
                Solution[SolutionCompilation, SolutionExecutionCommunication],
                unwrap(solution),
            )
            assert isinstance(solution.execution, SolutionExecutionCommunication)
            return ProblemConfigCommunication(
                **get_common(),
                problem_type=prob_type,
                solution=solution,
                checker=unwrap(checker),
                interactor=unwrap(interactor),
                manager=unwrap(manager),
            )

        case ProblemType.OUTPUT_ONLY:
            checker = parser.check_checker_args(judge_convention, checker)
            interactor = parser.check_config_none("interactor", prob_type, interactor)
            manager = parser.check_config_none("manager", prob_type, manager)
            check_solution_param(prob_type, SolutionExecutionStandalone)

            if parser.errors:
                return parser.errors

            solution = cast(
                Solution[SolutionCompilation, SolutionExecutionStandalone],
                unwrap(solution),
            )
            assert isinstance(solution.execution, SolutionExecutionStandalone)
            return ProblemConfigOutputOnly(
                **get_common(),
                problem_type=prob_type,
                solution=solution,
                checker=unwrap(checker),
                interactor=unwrap(interactor),
                manager=unwrap(manager),
            )

        case ProblemType.MULTI_PASS:
            checker = parser.check_config_none("checker", prob_type, checker)
            interactor = parser.check_config_exists("interactor", prob_type, interactor)
            manager = parser.check_config_none("manager", prob_type, manager)
            check_solution_param(prob_type, SolutionExecutionMultipass)

            if parser.errors:
                return parser.errors

            solution = cast(
                Solution[SolutionCompilation, SolutionExecutionMultipass],
                unwrap(solution),
            )
            assert isinstance(solution.execution, SolutionExecutionMultipass)
            return ProblemConfigMultipass(
                **get_common(),
                problem_type=prob_type,
                solution=solution,
                checker=unwrap(checker),
                interactor=unwrap(interactor),
                manager=unwrap(manager),
            )

        case TMTConfigError():
            return parser.errors

        case _:
            assert_never(prob_type)
