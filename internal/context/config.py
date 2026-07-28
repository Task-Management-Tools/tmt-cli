import dataclasses
import enum
import resource
import re
from typing import Any, TypeVar, Protocol, runtime_checkable


T = TypeVar("T")


@runtime_checkable
class DictParserSupported(Protocol):
    @classmethod
    def from_raw(cls: type[T], data: dict) -> "T | list[TMTConfigError]": ...


@dataclasses.dataclass
class TMTConfigError:
    what: str

    @classmethod
    def _typename(cls, t: type):
        if t is int:
            return "integer"
        if t is str:
            return "string"
        if t is float:
            return "number"
        if t is bool:
            return "boolean"
        if t is type(None):
            return "none"
        if issubclass(t, DictParserSupported):
            return "(config)"
        return t.__name__

    @classmethod
    def invalid_field(cls, name: str, expected_type: type, found: Any):
        return TMTConfigError(
            f"Invalid config field: {name} ({cls._typename(expected_type)}), "
            f"found {found} ({cls._typename(type(found))})."
        )


@dataclasses.dataclass
class DictParser:
    raw: dict[str, Any]
    parent: str
    errors: list[TMTConfigError] = dataclasses.field(default_factory=list)

    def add_err(self, what: str):
        self.errors.append(TMTConfigError(what))

    def _invalid_field(self, name: str, expected_type: type, found: Any):
        self.errors.append(TMTConfigError.invalid_field(name, expected_type, found))

    def full_config_name(self, key: str):
        return f"{self.parent}.{key}" if self.parent else key

    def pop(self, key: str, type: type[T], optional: bool = False) -> T | None:
        val = self.raw.pop(key, None)
        if val is None and optional:
            return None

        # Primitives
        if type in (int, str, bool, float):
            if not isinstance(val, type):
                self._invalid_field(self.full_config_name(key), type, val)
                return None
            return val

        if issubclass(type, enum.Enum):
            try:
                return type(val)
            except ValueError:
                self.errors.append(
                    TMTConfigError(
                        f"Config {self.full_config_name(key)} is not a valid value "
                        f"(found: {val}, expected: one of [{', '.join(str(j.value) for j in type)}])"
                    )
                )
                return None

        if issubclass(type, DictParserSupported):
            if val is None:
                self._invalid_field(self.full_config_name(key), type, val)
                return None
            res = type.from_raw(val)
            if isinstance(res, list):
                self.errors.extend(res)
                return None
            return res

        raise ValueError(f"Type {type} does not support config data parser interface")

    def pop_default(self, key: str, type: type[T], default: T) -> T | None:
        res = self.pop(key, type, optional=True)
        return default if res is None else res

    def reject_remaining(self) -> None:
        for key in self.raw.keys():
            self.add_err(
                f"Extra config remaining in {self.parent}: {key}. Please move them under config 'extra'."
            )

    # TODO: document time limit format and memory limit format
    def parse_time_to_second(self, input: str | None, key: str) -> float | None:
        if input is None:
            return None
        match = re.fullmatch(r"(\d+|\d+\.\d+)\s*(ms|s)", input)
        if match is None:
            self.add_err(
                f"Invalid config {self.full_config_name(key)} (found {input}, expected number s/ms)"
            )
            return None
        match match.group(2):
            case "ms":
                return float(match.group(1)) / 1000.0
            case "s":
                return float(match.group(1))
            case _:
                assert False, "Unreachable code"

    def parse_bytes_to_mib(
        self, input: str | None, key: str, *, allow_unlimited: bool = False
    ) -> int | None:
        if input is None:
            return None
        if allow_unlimited and input == "unlimited":
            return resource.RLIM_INFINITY
        match = re.fullmatch(r"(\d+)\s*(G|GiB|M|MiB)", input)
        if match is None:
            expected = (
                "number M/MiB/G/GiB or unlimited"
                if allow_unlimited
                else "number M/MiB/G/GiB"
            )
            self.add_err(
                f"Invalid config {self.full_config_name(key)} (found {input}, expected {expected})"
            )
            return None

        match match.group(2):
            case "G" | "GiB":
                return int(match.group(1)) * 1024
            case "M" | "MiB":
                return int(match.group(1))
            case _:
                assert False, "Unreachable code"


@dataclasses.dataclass(frozen=True)
class JudgeSettings:
    name: str
    display_score: bool
    display_testsets: bool

    def __str__(self):
        return self.name


class JudgeConvention(enum.Enum):
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


class ProblemType(enum.Enum):
    BATCH = "batch"
    INTERACTIVE = "interactive"
    MULTI_PASS = "multi-pass"
    COMMUNICATION = "communication"
    OUTPUT_ONLY = "output-only"


class CheckerType(enum.Enum):
    DEFAULT = "default"
    CUSTOM = "custom"


@dataclasses.dataclass
class Checker:
    type: CheckerType
    filename: str | None
    arguments: list[str] | None
    check_forced_output: bool = True
    check_generated_output: bool = True

    @classmethod
    def from_raw(cls, data: dict | str) -> "Checker | list[TMTConfigError]":
        # TODO: document this
        if isinstance(data, str):
            # Fall through for default args
            data = {"type": "custom", "filename": data}

        if not isinstance(data, dict):
            return [TMTConfigError.invalid_field("checker (config)", data)]

        parser = DictParser(data, "checker")
        type = parser.pop("type", CheckerType)
        filename = parser.pop("filename", str, optional=True)
        arguments = parser.pop_default("arguments", str, "")
        check_forced_output = parser.pop_default("check_forced_output", bool, True)
        check_generated_output = parser.pop_default(
            "check_generated_output", bool, True
        )

        if type is CheckerType.CUSTOM and filename is None:
            parser.add_err(
                "Config checker.filename must be present when checker.type is set to custom."
            )

        parser.reject_remaining()
        if parser.errors:
            return parser.errors

        assert type is not None
        assert arguments is not None
        assert check_forced_output is not None
        assert check_generated_output is not None
        return Checker(
            type=type,
            filename=filename,
            arguments=arguments.split(),
            check_forced_output=check_forced_output,
            check_generated_output=check_generated_output,
        )


class ValidatorType(enum.Enum):
    DEFAULT = "default"
    # PROVER = "prover"


@dataclasses.dataclass
class Validator:
    type: ValidatorType

    @classmethod
    def from_raw(cls, data: dict | str) -> "Validator | list[TMTConfigError]":
        if isinstance(data, str):
            # Fall through for enum check
            data = {"type": data}

        if not isinstance(data, dict):
            return [TMTConfigError.invalid_field("validator (config)", data)]

        parser = DictParser(data, "validator")

        type = parser.pop("type", ValidatorType)
        if type is not ValidatorType.DEFAULT:
            parser.add_err(f"Validator type {type} is not supported yet.")

        parser.reject_remaining()
        assert type is not None
        return parser.errors or Validator(type=type)


@dataclasses.dataclass
class Interactor:
    filename: str
    arguments: list[str]

    @classmethod
    def from_raw(cls, data: dict | str) -> "Interactor | list[TMTConfigError]":
        if isinstance(data, str):
            return Interactor(filename=data, arguments=[])

        if not isinstance(data, dict):
            return [TMTConfigError.invalid_field("interactor (config)", data)]

        parser = DictParser(data, "interactor")

        filename = parser.pop("filename", str)
        arguments = parser.pop("arguments", str, optional=True)

        arg_list = [] if not arguments else arguments.split()
        parser.reject_remaining()

        if parser.errors:
            return parser.errors
        assert filename is not None
        return Interactor(filename=filename, arguments=arg_list)


@dataclasses.dataclass
class Manager:
    filename: str

    @classmethod
    def from_raw(cls, data: dict) -> "Manager | list[TMTConfigError]":
        if isinstance(data, str):
            return Manager(filename=data)

        if not isinstance(data, dict):
            return [TMTConfigError.invalid_field("manager (config)", data)]

        parser = DictParser(data, "manager")
        filename = parser.pop("filename", str)
        parser.reject_remaining()

        if parser.errors:
            return parser.errors
        assert filename is not None
        return Manager(filename=filename)


class SolutionType(enum.Enum):
    DEFAULT = "default"
    GRADER = "grader"  # means the solution should be compiled with grader


@dataclasses.dataclass(kw_only=True)
class Solution:
    type: SolutionType
    grader_name: str | None
    time_limit_sec: float
    memory_limit_mib: int
    output_limit_mib: int

    # Communication only attributes
    num_procs: int | None
    use_fifo: bool

    # Multipass only attributes
    max_passes: int | None

    @property
    def memory_limit_bytes(self) -> float:
        return self.memory_limit_mib * 1024 * 1024

    @property
    def memory_limit_kib(self) -> int:
        return self.memory_limit_mib * 1024

    @property
    def memory_limit_gib(self) -> float:
        return self.memory_limit_mib / 1024

    @classmethod
    def from_raw(cls, data: dict) -> "Solution | list[TMTConfigError]":
        if not isinstance(data, dict):
            return [TMTConfigError.invalid_field("solution (config)", data)]

        parser = DictParser(data, "solution")

        type = parser.pop("type", SolutionType)
        grader_name = parser.pop("grader_name", str, optional=True)
        time_limit = parser.pop("time_limit", str)
        memory_limit = parser.pop("memory_limit", str)
        output_limit = parser.pop("output_limit", str)
        num_procs = parser.pop("num_procs", int, optional=True)
        use_fifo = parser.pop("use_fifo", bool, optional=True)
        max_passes = parser.pop("max_passes", int, optional=True)

        # Fine because valid time/memory is nevery empty
        time_limit_sec = parser.parse_time_to_second(time_limit, "time_limit")
        memory_limit_mib = parser.parse_bytes_to_mib(memory_limit, "memory_limit")
        output_limit_mib = parser.parse_bytes_to_mib(
            output_limit, "output_limit", allow_unlimited=True
        )

        if num_procs is not None:
            if num_procs <= 0:
                parser.add_err("Config option solution.num_procs must be positive.")
            elif num_procs > 10:
                parser.add_err(
                    "Config option solution.num_procs must be at most 10. "
                    "CMS does not support Communication task with more than 10 solution processes. "
                    "See https://github.com/cms-dev/cms/issues/1207."
                )

        if max_passes is not None:
            if max_passes <= 1:
                parser.add_err("Config option solution.num_passes must be at least 2.")

        if use_fifo is None:
            use_fifo = False

        if type is SolutionType.GRADER and grader_name is None:
            parser.add_err(
                "Invalid config solution.grader_name: Tasks with grader must supply solution.grader_name."
            )

        parser.reject_remaining()
        if parser.errors:
            return parser.errors

        assert type is not None
        assert time_limit_sec is not None
        assert memory_limit_mib is not None
        assert output_limit_mib is not None

        return Solution(
            type=type,
            grader_name=grader_name,
            time_limit_sec=time_limit_sec,
            memory_limit_mib=memory_limit_mib,
            output_limit_mib=output_limit_mib,
            num_procs=num_procs,
            use_fifo=use_fifo,
            max_passes=max_passes,
        )


class AnswerGenerationType(enum.Enum):
    SOLUTION = "solution"
    GENERATOR = "generator"


@dataclasses.dataclass
class AnswerGeneration:
    type: AnswerGenerationType
    filename: str | None

    @classmethod
    def from_raw(cls, data: dict) -> "AnswerGeneration | list[TMTConfigError]":
        if isinstance(data, str):
            return AnswerGeneration(type=AnswerGenerationType.SOLUTION, filename=data)

        if not isinstance(data, dict):
            return [TMTConfigError.invalid_field("answer_generation (config)", data)]

        parser = DictParser(data, "answer_generation")

        type = parser.pop("type", AnswerGenerationType)
        filename = parser.pop("filename", str, optional=True)

        if type == AnswerGenerationType.SOLUTION and filename is None:
            parser.add_err(
                "Config answer_generation.filename must be specified when type is 'solution'."
            )

        parser.reject_remaining()
        if parser.errors:
            return parser.errors
        assert type is not None
        return AnswerGeneration(type=type, filename=filename)


@dataclasses.dataclass(kw_only=True)
class TMTConfig:
    title: str
    short_name: str
    description: str | None

    tmt_version: str

    input_extension: str
    output_extension: str

    judge_convention: JudgeConvention
    problem_type: ProblemType

    validator: Validator
    solution: Solution
    answer_generation: AnswerGeneration
    checker: Checker | None
    interactor: Interactor | None
    manager: Manager | None

    compile_time_limit_sec: float
    compile_memory_limit_mib: int

    trusted_step_time_limit_sec = 10.0
    trusted_step_memory_limit_mib = 4 * 1024
    trusted_step_output_limit_mib = resource.RLIM_INFINITY

    @classmethod
    def from_raw(cls, data: dict) -> "TMTConfig | list[TMTConfigError]":
        parser = DictParser(data, "")

        # fmt: off
        title                = parser.pop("title",                str)
        short_name           = parser.pop("short_name",           str)
        description          = parser.pop("description",          str, optional=True)
        tmt_version          = parser.pop("tmt_version",          str)
        input_extension      = parser.pop("input_extension",      str)
        output_extension     = parser.pop("output_extension",     str)
        judge_convention     = parser.pop("judge_convention",     JudgeConvention)
        problem_type         = parser.pop("problem_type",         ProblemType)
        validator            = parser.pop("validator",            Validator)
        solution             = parser.pop("solution",             Solution)
        answer_generation    = parser.pop("answer_generation",    AnswerGeneration)
        checker              = parser.pop("checker",              Checker, optional=True)
        interactor           = parser.pop("interactor",           Interactor, optional=True)
        manager              = parser.pop("manager",              Manager, optional=True)
        compile_time_limit   = parser.pop_default("compile_time_limit",   str, "60 s")
        compile_memory_limit = parser.pop_default("compile_memory_limit", str, "unlimited")
        # fmt: on

        # TODO warn for tmt_version
        if isinstance(input_extension, str) and not input_extension.startswith("."):
            parser.add_err("Config input_extension should start with a dot.")
        if isinstance(output_extension, str) and not output_extension.startswith("."):
            parser.add_err("Config output_extension should start with a dot.")
        if input_extension is not None and input_extension == output_extension:
            parser.add_err(
                "Config input_extension and output_extension must not be the same."
            )

        compile_time_limit_sec = parser.parse_time_to_second(
            compile_time_limit, "compile_time_limit"
        )
        compile_memory_limit_mib = parser.parse_bytes_to_mib(
            compile_memory_limit, "compile_memory_limit", allow_unlimited=True
        )

        if problem_type is ProblemType.BATCH:
            pass
            # TODO warn about extra interactor/manager
        if problem_type is ProblemType.INTERACTIVE:
            if not isinstance(interactor, Interactor):
                parser.add_err(
                    "Config interactor must be present when problem_type is interactive."
                )

        if problem_type is ProblemType.COMMUNICATION:
            if not isinstance(manager, Manager):
                parser.add_err(
                    "Config manager must be present when problem_type is communication."
                )
            if isinstance(checker, Checker):
                parser.add_err(
                    "Config checker must not be present when problem_type is communication."
                )
            if isinstance(solution, Solution) and solution.num_procs is None:
                parser.add_err(
                    "Config solution.num_procs must be present when problem_type is communication."
                )

        if problem_type is ProblemType.MULTI_PASS:
            if not isinstance(interactor, Interactor):
                parser.add_err(
                    "Config interactor must be present when problem_type is multi-pass."
                )
            if not isinstance(solution, Solution) or solution.max_passes is None:
                parser.add_err(
                    "Config solution.num_passes must be present when problem_type is multi-pass."
                )

        parser.raw.pop("extra", None)
        parser.reject_remaining()
        if parser.errors:
            return parser.errors

        assert title is not None
        assert short_name is not None
        assert tmt_version is not None
        assert input_extension is not None
        assert output_extension is not None
        assert judge_convention is not None
        assert problem_type is not None
        assert validator is not None
        assert solution is not None
        assert answer_generation is not None
        assert compile_time_limit_sec is not None
        assert compile_memory_limit_mib is not None
        return TMTConfig(
            title=title,
            short_name=short_name,
            description=description,
            tmt_version=tmt_version,
            input_extension=input_extension,
            output_extension=output_extension,
            judge_convention=judge_convention,
            problem_type=problem_type,
            validator=validator,
            solution=solution,
            answer_generation=answer_generation,
            checker=checker,
            interactor=interactor,
            manager=manager,
            compile_time_limit_sec=compile_time_limit_sec,
            compile_memory_limit_mib=compile_memory_limit_mib,
        )
