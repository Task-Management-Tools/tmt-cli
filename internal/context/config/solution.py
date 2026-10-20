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


@final
@dataclass
class SolutionExecutionMultipass:
    max_passes: int


SolutionExecution: TypeAlias = (
    SolutionExecutionStandalone
    | SolutionExecutionCommunication
    | SolutionExecutionMultipass
)

C = TypeVar(
    "C", SolutionCompilation, SolutionCompilationGradered, SolutionCompilationStandalone
)
E = TypeVar(
    "E",
    SolutionExecution,
    SolutionExecutionStandalone,
    SolutionExecutionCommunication,
    SolutionExecutionMultipass,
)


@dataclass(kw_only=True)
class Solution(Generic[C, E]):
    time_limit_sec: float
    memory_limit_mib: int
    output_limit_mib: int

    compilation: C
    execution: E

    # Helper properties, also for internal use
    @property
    def memory_limit_bytes(self) -> float:
        return self.memory_limit_mib * 1024 * 1024

    @property
    def memory_limit_kib(self) -> int:
        return self.memory_limit_mib * 1024

    @property
    def memory_limit_gib(self) -> float:
        return self.memory_limit_mib / 1024

    # Helper properties, only for config formatter use
    # Use getattr here to supress mypy warning; formatter will handle AttributeError
    @property
    def grader_name(self) -> Any:
        return getattr(self.compilation, "grader_name")

    @property
    def num_procs(self) -> Any:
        return getattr(self.execution, "num_procs")

    @property
    def use_fifo(self) -> Any:
        return getattr(self.execution, "use_fifo")

    @property
    def max_passes(self) -> Any:
        return getattr(self.execution, "max_passes")


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
    max_passes = parser.pop_optional("max_passes", int)

    parser.reject_remaining()

    compilation: TMTConfigError | SolutionCompilation
    match (type_, grader_name):
        case (TMTConfigError() as e, _) | (_, TMTConfigError() as e):
            compilation = e
        case (SolutionType.DEFAULT, None):
            compilation = SolutionCompilationStandalone(type_)
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

    # Parse execution configs
    if isinstance(num_procs, int):
        if num_procs <= 0:
            num_procs = parser.add_err(
                "Config option solution.num_procs must be positive."
            )
        elif num_procs > 10:
            num_procs = parser.add_err(
                "Config option solution.num_procs must be at most 10. "
                "CMS does not support Communication task with more than 10 solution processes. "
                "See https://github.com/cms-dev/cms/issues/1207."
            )
    if isinstance(max_passes, int):
        if max_passes <= 1:
            max_passes = parser.add_err(
                "Config option solution.max_passes must be at least 2."
            )

    exe_communication: TMTConfigError | SolutionExecutionCommunication | None
    match (num_procs, use_fifo):
        case (TMTConfigError() as e, _) | (_, TMTConfigError() as e):
            exe_communication = e
        case (None, None):
            exe_communication = None
        case (int(), bool()):
            exe_communication = SolutionExecutionCommunication(num_procs, use_fifo)
        case (int(), None) | (None, bool()):
            exe_communication = parser.add_err(
                "Invalid config solution.{num_procs,use_fifo}: "
                "One of the config exists but not the other. "
                "Communication task must have both and other tasks must have none of them."
            )
        case _:
            # ??? mypy cannot reason this
            assert_never((num_procs, use_fifo))  # type: ignore[arg-type]

    exe_multi_pass: TMTConfigError | SolutionExecutionMultipass | None
    match max_passes:
        case TMTConfigError() as e:
            exe_multi_pass = e
        case None:
            exe_multi_pass = None
        case int():
            exe_multi_pass = SolutionExecutionMultipass(max_passes)
        case _:
            assert_never(max_passes)

    execution: TMTConfigError | SolutionExecution
    match (exe_communication, exe_multi_pass):
        case (None, None):
            execution = SolutionExecutionStandalone()
        case (SolutionExecutionCommunication(), None):
            execution = exe_communication
        case (None, SolutionExecutionMultipass()):
            execution = exe_multi_pass
        case (None, TMTConfigError() as e) | (TMTConfigError() as e, None):
            execution = e
        case _:
            execution = parser.add_err(
                "Mixed configs supplied for task-type specific fields: "
                "Communication task must have both 'num_procs' and 'use_fifo'; "
                "multi-pass task must have 'max_passes'; "
                "other tasks must have none of them."
            )

    return parser.errors or Solution(
        time_limit_sec=unwrap(time_limit_sec),
        memory_limit_mib=unwrap(memory_limit_mib),
        output_limit_mib=unwrap(output_limit_mib),
        compilation=unwrap(compilation),
        execution=unwrap(execution),
    )
