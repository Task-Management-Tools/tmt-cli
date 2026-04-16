import dataclasses
import enum
import functools
import resource
import re
import typing


@dataclasses.dataclass
class TMTConfigError:
    what: str

    @classmethod
    def typename(cls, t: type):
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

        return t.__name__

    @classmethod
    def invalid_field(cls, expected: str, found):
        return TMTConfigError(
            f"Invalid config field: {expected}, found {found} ({cls.typename(type(found))})."
        )


T = typing.TypeVar("T")


@typing.overload
def pop_from_raw(
    data: dict,
    key: str,
    type: typing.Type[T],
    errors: list[TMTConfigError],
    config_root: str = ...,
    *,
    optional: typing.Literal[True],
) -> T | None: ...


@typing.overload
def pop_from_raw(
    data: dict,
    key: str,
    type: typing.Type[T],
    errors: list[TMTConfigError],
    config_root: str = ...,
    *,
    optional: typing.Literal[False],
) -> T: ...


def pop_from_raw(
    data: dict,
    key: str,
    type: type,
    errors: list[TMTConfigError],
    config_root: str = "",
    optional: bool = False,
):
    if config_root:
        config_root += "."

    val = data.pop(key, None)
    if val is None and optional:
        return None

    # Primitives
    if type in [int, str, bool, float]:
        if not isinstance(val, type):
            errors.append(
                TMTConfigError.invalid_field(
                    f"{config_root}{key} ({type.__name__})", val
                )
            )
            return None
        return val

    if issubclass(type, enum.Enum):
        try:
            return type(val)
        except ValueError:
            errors.append(
                TMTConfigError(
                    f"Config {config_root}{key} is not a valid value "
                    f"(found: {val}, expected: one of [{', '.join(str(j.value) for j in type)}])"
                )
            )
            return None

    if hasattr(type, "from_raw"):
        if val is None:
            errors.append(
                TMTConfigError.invalid_field(f"{config_root}{key} (object)", val)
            )
            return None
        res = type.from_raw(val)
        if not isinstance(res, type):
            errors.extend(res)
            return None
        return res

    raise ValueError("Invalid class:", type)


def reject_remaining_keys(data: dict, errors: list, config_root: str = "") -> None:
    for key in data.keys():
        errors.append(
            TMTConfigError(
                f"Extra config remaining in {config_root}: {key}. Please move them under config 'extra'."
            )
        )


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
    def from_raw(cls, data: dict) -> "Checker | list[TMTConfigError]":
        # TODO: document this
        if isinstance(data, str):
            data = {"type": "custom", "filename": data}

        if not isinstance(data, dict):
            return [TMTConfigError.invalid_field("checker (object)", data)]

        errors: list[TMTConfigError] = []
        pop = functools.partial(
            pop_from_raw, data, errors=errors, config_root="checker"
        )

        type = pop("type", CheckerType)
        filename = pop("filename", str, optional=True)
        arguments = pop("arguments", str, optional=True)
        check_forced_output = pop("check_forced_output", bool, optional=True)
        check_generated_output = pop("check_generated_output", bool, optional=True)

        if arguments is not None:
            arguments = arguments.split()

        if type is CheckerType.CUSTOM and filename is None:
            errors.append(
                TMTConfigError(
                    "Config checker.filename must be present when checker.type is set to custom."
                )
            )

        reject_remaining_keys(data, errors, "checker")
        if errors:
            return errors

        if check_forced_output is None:
            check_forced_output = True
        if check_generated_output is None:
            check_generated_output = True

        return Checker(
            type=type,
            filename=filename,
            arguments=arguments,
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
    def from_raw(cls, data: dict) -> "Validator | list[TMTConfigError]":
        if isinstance(data, str):
            data = {"type": data}

        if not isinstance(data, dict):
            return [TMTConfigError.invalid_field("validator (object)", data)]

        errors: list[TMTConfigError] = []
        pop = functools.partial(
            pop_from_raw, data, errors=errors, config_root="validator"
        )

        type = pop("type", ValidatorType)

        if type is not ValidatorType.DEFAULT:
            errors.append(
                TMTConfigError(f"Validator type {type} is not supported yet.")
            )

        reject_remaining_keys(data, errors, "validator")
        if errors:
            return errors
        return Validator(type=type)


@dataclasses.dataclass
class Interactor:
    filename: str
    arguments: list[str]

    @classmethod
    def from_raw(cls, data: dict) -> "Interactor | list[TMTConfigError]":
        if isinstance(data, str):
            data = {"filename": data}

        if not isinstance(data, dict):
            return [TMTConfigError.invalid_field("interactor (object)", data)]

        errors: list[TMTConfigError] = []
        pop = functools.partial(
            pop_from_raw, data, errors=errors, config_root="interactor"
        )

        filename = pop("filename", str)
        arguments = pop("arguments", str, optional=True)

        arguments = [] if not arguments else arguments.split()

        reject_remaining_keys(data, errors, "interactor")
        if errors:
            return errors
        return Interactor(filename=filename, arguments=arguments)


@dataclasses.dataclass
class Manager:
    filename: str

    @classmethod
    def from_raw(cls, data: dict) -> "Manager | list[TMTConfigError]":
        if isinstance(data, str):
            data = {"filename": data}
        if not isinstance(data, dict):
            return [TMTConfigError.invalid_field("manager (object)", data)]

        errors: list[TMTConfigError] = []
        pop = functools.partial(
            pop_from_raw, data, errors=errors, config_root="manager"
        )

        filename = pop("filename", str)

        reject_remaining_keys(data, errors, "manager")
        if errors:
            return errors
        return Manager(filename=filename)


# TODO: document time limit format and memory limit format
def parse_time_to_second(
    input_str: str, errors: list, config_name: str
) -> float | None:
    match = re.fullmatch(r"(\d+|\d+\.\d+)\s*(ms|s)", input_str)
    if match is None:
        errors.append(
            TMTConfigError(
                f"Invalid config {config_name} (found {input_str}, expected numbers s/ms)"
            )
        )
        return None
    if match.group(2) == "ms":
        return float(match.group(1)) / 1000.0
    else:
        return float(match.group(1))


def parse_bytes_to_mib(
    input_str: str, errors: list, config_name: str, *, allow_unlimited: bool = False
) -> int | None:
    if input_str == "unlimited" and allow_unlimited:
        return resource.RLIM_INFINITY
    match = re.fullmatch(r"(\d+)\s*(G|GiB|M|MiB)", input_str)
    if match is None:
        if allow_unlimited:
            errors.append(
                TMTConfigError(
                    f"Invalid config {config_name} (found {input_str}, expected numbers M/MiB/G/GiB or unlimited)"
                )
            )
        else:
            errors.append(
                TMTConfigError(
                    f"Invalid config {config_name} (found {input_str}, expected numbers M/MiB/G/GiB)"
                )
            )
        return None
    if match.group(2).startswith("G"):
        return int(match.group(1)) * 1024
    else:
        return int(match.group(1))


class SolutionType(enum.Enum):
    DEFAULT = "default"
    GRADER = "grader"  # means the solution should be compiled with grader


@dataclasses.dataclass(kw_only=True)
class Solution:
    type: SolutionType
    grader_name: str
    time_limit_sec: float
    memory_limit_mib: int
    output_limit_mib: int

    # Communication only attributes
    num_procs: int | None
    use_fifo: bool

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
            return [TMTConfigError.invalid_field("solution (object)", data)]

        errors: list[TMTConfigError] = []
        pop = functools.partial(
            pop_from_raw, data, errors=errors, config_root="solution"
        )

        type = pop("type", SolutionType)
        grader_name = pop("grader_name", str, optional=True)
        time_limit = pop("time_limit", str)
        memory_limit = pop("memory_limit", str)
        output_limit = pop("output_limit", str)
        num_procs = pop("num_procs", int, optional=True)
        use_fifo = pop("use_fifo", bool, optional=True)

        if isinstance(time_limit, str):
            time_limit_sec = parse_time_to_second(
                time_limit, errors, "solution.time_limit"
            )
        if isinstance(memory_limit, str):
            memory_limit_mib = parse_bytes_to_mib(
                memory_limit, errors, "solution.memory_limit"
            )
        if isinstance(output_limit, str):
            output_limit_mib = parse_bytes_to_mib(
                output_limit, errors, "solution.output_limit", allow_unlimited=True
            )

        if isinstance(num_procs, int):
            if num_procs <= 0:
                errors.append(
                    TMTConfigError("Config option solution.num_procs must be positive.")
                )
            elif num_procs > 10:
                errors.append(
                    TMTConfigError(
                        "Config option solution.num_procs must be at most 10. "
                        "CMS does not support Communication task with more than 10 solution processes. "
                        "See https://github.com/cms-dev/cms/issues/1207."
                    )
                )

        if use_fifo is None:
            use_fifo = False

        if type == SolutionType.GRADER and grader_name is None:
            errors.append(
                TMTConfigError(
                    "Invalid config solution.grader_name: Tasks with grader must supply solution.grader_name."
                )
            )

        reject_remaining_keys(data, errors, "solution")
        if len(errors):
            return errors
        return Solution(
            type=type,
            grader_name=grader_name,
            time_limit_sec=time_limit_sec,
            memory_limit_mib=memory_limit_mib,
            output_limit_mib=output_limit_mib,
            num_procs=num_procs,
            use_fifo=use_fifo,
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
            data = {"type": "solution", "filename": data}
        if not isinstance(data, dict):
            return [TMTConfigError.invalid_field("answer_generation (object)", data)]

        errors: list[TMTConfigError] = []
        pop = functools.partial(
            pop_from_raw, data, errors=errors, config_root="answer_generation"
        )

        type = pop("type", AnswerGenerationType)
        filename = pop("filename", str, optional=True)

        if type == AnswerGenerationType.SOLUTION and filename is None:
            errors.append(
                TMTConfigError(
                    "Config answer_generation.filename must be specified when type is 'solution'."
                )
            )

        reject_remaining_keys(data, errors, "answer_generation")
        if len(errors):
            return errors
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
        errors: list[TMTConfigError] = []
        pop = functools.partial(pop_from_raw, data, errors=errors)

        # fmt: off
        title                = pop("title",                str)
        short_name           = pop("short_name",           str)
        description          = pop("description",          str, optional=True)
        tmt_version          = pop("tmt_version",          str)
        input_extension      = pop("input_extension",      str)
        output_extension     = pop("output_extension",     str)
        judge_convention     = pop("judge_convention",     JudgeConvention)
        problem_type         = pop("problem_type",         ProblemType)
        validator            = pop("validator",            Validator)
        solution             = pop("solution",             Solution)
        answer_generation    = pop("answer_generation",    AnswerGeneration)
        checker              = pop("checker",              Checker, optional=True)
        interactor           = pop("interactor",           Interactor, optional=True)
        manager              = pop("manager",              Manager, optional=True)
        compile_time_limit   = pop("compile_time_limit",   str, optional=True)
        compile_memory_limit = pop("compile_memory_limit", str, optional=True)
        # fmt: on

        # TODO warn for tmt_version
        if isinstance(input_extension, str) and not input_extension.startswith("."):
            errors.append(
                TMTConfigError("Config input_extension should start with a dot.")
            )
        if isinstance(output_extension, str) and not output_extension.startswith("."):
            errors.append(
                TMTConfigError("Config output_extension should start with a dot.")
            )
        if input_extension is not None and input_extension == output_extension:
            errors.append(
                TMTConfigError(
                    "Config input_extension and output_extension must not be the same."
                )
            )

        compile_time_limit_sec = None
        if compile_time_limit is not None:
            compile_time_limit_sec = parse_time_to_second(
                compile_time_limit, errors, "compile_time_limit"
            )

        compile_memory_limit_mib = None
        if compile_memory_limit is not None:
            compile_memory_limit_mib = parse_bytes_to_mib(
                compile_memory_limit,
                errors,
                "compile_memory_limit",
                allow_unlimited=True,
            )

        if problem_type is ProblemType.BATCH:
            pass
            # TODO warn about extra interactor/manager
        if problem_type is ProblemType.INTERACTIVE:
            if not isinstance(interactor, Interactor):
                errors.append(
                    TMTConfigError(
                        "Config interactor must be present when problem_type is interactive."
                    )
                )
        if problem_type is ProblemType.COMMUNICATION:
            if not isinstance(manager, Manager):
                errors.append(
                    TMTConfigError(
                        "Config manager must be present when problem_type is communication."
                    )
                )
            if isinstance(checker, Checker):
                errors.append(
                    TMTConfigError(
                        "Config checker must not be present when problem_type is communication."
                    )
                )
            if isinstance(solution, Solution) and solution.num_procs is None:
                errors.append(
                    TMTConfigError(
                        "Config solution.num_procs must be present when problem_type is communication."
                    )
                )

        data.pop("extra", None)
        reject_remaining_keys(data, errors)
        if len(errors):
            return errors

        if compile_time_limit_sec is None:
            compile_time_limit_sec = 60.0  # default one minute
        if compile_memory_limit_mib is None:
            compile_memory_limit_mib = resource.RLIM_INFINITY  # default unlimited

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
