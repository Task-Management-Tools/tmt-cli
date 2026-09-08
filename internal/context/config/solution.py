from dataclasses import dataclass
from enum import Enum
from typing import Any, Generic, Literal, TypeAlias, TypeVar, final

from internal.utils import assert_never

from .parser import DictParser, TMTConfigError, TMTConfigErrorsList, unwrap


class SolutionType(Enum):
    DEFAULT = "default"
    GRADER = "grader"  # means the solution should be compiled with grader


@final
@dataclass
class SolutionCompilationStandalone:
    type: Literal[SolutionType.DEFAULT]
    grader_name: None


@final
@dataclass
class SolutionCompilationGradered:
    type: Literal[SolutionType.GRADER]
    grader_name: str


SolutionCompilation: TypeAlias = (
    SolutionCompilationStandalone | SolutionCompilationGradered
)


@final
@dataclass
class SolutionExecutionStandalone:
    pass


@final
@dataclass
class SolutionExecutionCommunication:
    num_procs: int
    use_fifo: bool


SolutionExecution: TypeAlias = (
    SolutionExecutionStandalone | SolutionExecutionCommunication
)

C = TypeVar(
    "C", SolutionCompilation, SolutionCompilationGradered, SolutionCompilationStandalone
)
E = TypeVar(
    "E", SolutionExecution, SolutionExecutionStandalone, SolutionExecutionCommunication
)


@dataclass(kw_only=True)
class Solution(Generic[C, E]):
    time_limit_sec: float
    memory_limit_mib: int
    output_limit_mib: int

    compilation: C
    execution: E

    @property
    def memory_limit_bytes(self) -> float:
        return self.memory_limit_mib * 1024 * 1024

    @property
    def memory_limit_kib(self) -> int:
        return self.memory_limit_mib * 1024

    @property
    def memory_limit_gib(self) -> float:
        return self.memory_limit_mib / 1024


def parse_solution(data: Any) -> Solution | TMTConfigErrorsList:
    if not isinstance(data, dict):
        return TMTConfigErrorsList.single_bad_complex_type("solution (config)", data)

    parser = DictParser(data, "solution")

    time_limit_sec = parser.pop_time_to_second("time_limit")
    memory_limit_mib = parser.pop_bytes_to_mib("memory_limit")
    output_limit_mib = parser.pop_bytes_to_mib("output_limit", allow_unlimited=True)

    type_ = parser.pop("type", SolutionType)
    grader_name = parser.pop_optional("grader_name", str)

    num_procs = parser.pop_optional("num_procs", int)
    use_fifo = parser.pop_optional("use_fifo", bool)

    parser.reject_remaining()

    compilation: TMTConfigError | SolutionCompilation
    match (type_, grader_name):
        case (TMTConfigError() as e, _) | (_, TMTConfigError() as e):
            compilation = e
        case (SolutionType.DEFAULT, None):
            compilation = SolutionCompilationStandalone(type_, grader_name)
        case (SolutionType.DEFAULT, str()):
            compilation = parser.add_err(
                "Invalid config solution.grader_name: "
                "Tasks without grader must not supply solution.grader_name."
            )
        case (SolutionType.GRADER, None):
            compilation = parser.add_err(
                "Invalid config solution.grader_name: "
                "Tasks with grader must supply solution.grader_name."
            )
        case (SolutionType.GRADER, str()):
            compilation = SolutionCompilationGradered(type_, grader_name)

    execution: TMTConfigError | SolutionExecution
    bad: TMTConfigError | None = None
    if isinstance(num_procs, int):
        if num_procs <= 0:
            bad = parser.add_err("Config option solution.num_procs must be positive.")
        elif num_procs > 10:
            bad = parser.add_err(
                "Config option solution.num_procs must be at most 10. "
                "CMS does not support Communication task with more than 10 solution processes. "
                "See https://github.com/cms-dev/cms/issues/1207."
            )

    match (num_procs, use_fifo):
        case (TMTConfigError() as e, _) | (_, TMTConfigError() as e):
            execution = e
        case (None, None):
            execution = SolutionExecutionStandalone()
        case (int(), bool()):
            execution = bad or SolutionExecutionCommunication(num_procs, use_fifo)
        case (int(), None) | (None, bool()):
            execution = parser.add_err(
                "Invalid config solution.{num_procs,use_fifo}: "
                "One of the config exists but not the other. "
                "Communication task must have both and other tasks must have none of them."
            )
        case _:
            # ??? mypy cannot reason this
            assert_never((num_procs, use_fifo))  # type: ignore[arg-type]

    return parser.errors or Solution(
        time_limit_sec=unwrap(time_limit_sec),
        memory_limit_mib=unwrap(memory_limit_mib),
        output_limit_mib=unwrap(output_limit_mib),
        compilation=unwrap(compilation),
        execution=unwrap(execution),
    )
