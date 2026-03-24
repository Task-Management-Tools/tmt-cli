import enum
import resource
import re
import dataclasses


@dataclasses.dataclass
class TMTConfigError:
    what: str

    @classmethod
    def invalid_field(cls, expected: str, found):
        return TMTConfigError(
            f"Invalid config field: {expected}, found {found} ({type(found).__name__})."
        )


@dataclasses.dataclass(frozen=True)
class JudgeSettings:
    name: str
    display_score: bool
    display_testsets: bool


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
    OUTPUT_ONLY = "outputonly"


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
        if isinstance(data, str):
            data = {"type": "custom", "filename": data}
        if not isinstance(data, dict):
            return [TMTConfigError.invalid_field("checker (object)", data)]
        errors = []

        type = data.pop("type", None)
        filename = data.pop("filename", None)
        arguments = data.pop("arguments", None)
        check_forced_output = data.pop("check_forced_output", True)
        check_generated_output = data.pop("check_generated_output", True)

        try:
            type = CheckerType(type)
        except ValueError:
            errors.append(
                TMTConfigError(
                    f"Config checker.type ({type}) is not a valid value (expected: one of [{', '.join(t.value for t in CheckerType)}])."
                )
            )

        if filename is not None and not isinstance(filename, str):
            errors.append(
                TMTConfigError.invalid_field("checker.filename (string)", filename)
            )

        if arguments is not None:
            if not isinstance(arguments, str):
                errors.append(
                    TMTConfigError.invalid_field(
                        "checker.arguments (string)", arguments
                    )
                )
            else:
                arguments = arguments.split()

        if (
            isinstance(type, CheckerType)
            and type is CheckerType.CUSTOM
            and filename is None
        ):
            errors.append(
                TMTConfigError(
                    "Config checker.filename must be present when checker.type is set to custom."
                )
            )

        if not isinstance(check_forced_output, bool):
            errors.append(
                TMTConfigError.invalid_field(
                    "checker.check_forced_output (bool)", check_forced_output
                )
            )

        if not isinstance(check_generated_output, bool):
            errors.append(
                TMTConfigError.invalid_field(
                    "checker.check_generated_output (bool)", check_generated_output
                )
            )

        for key in data.keys():
            errors.append(
                TMTConfigError(
                    f"Extra config remaining in checker: {key}. Please move them under config 'extra'."
                )
            )

        if errors:
            return errors
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
        errors = []

        type = data.pop("type", None)

        try:
            type = ValidatorType(type)
        except ValueError:
            errors.append(
                TMTConfigError(
                    f"Config validator.type is not a valid value (found: {type}, (expected: one of [{', '.join(t.value for t in ValidatorType)}])."
                )
            )
            return errors

        if type is not ValidatorType.DEFAULT:
            errors.append(
                TMTConfigError(f"Validator type {type} is not supported yet.")
            )

        for key in data.keys():
            errors.append(
                TMTConfigError(
                    f"Extra config remaining in validator: {key}. Please move them under config 'extra'."
                )
            )

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
        errors = []

        filename = data.pop("filename", None)
        arguments = data.pop("arguments", None)

        if not isinstance(filename, str):
            errors.append(
                TMTConfigError.invalid_field("interactor.filename (string)", filename)
            )

        if arguments is not None:
            if not isinstance(arguments, str):
                errors.append(
                    TMTConfigError.invalid_field(
                        "interactor.arguments (string)", arguments
                    )
                )
            else:
                arguments = arguments.split()
        else:
            arguments = []

        for key in data.keys():
            errors.append(
                TMTConfigError(
                    f"Extra config remaining in interactor: {key}. Please move them under config 'extra'."
                )
            )

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
        errors = []

        filename = data.pop("filename", None)

        if not isinstance(filename, str):
            errors.append(
                TMTConfigError.invalid_field("manager.filename (string)", filename)
            )

        for key in data.keys():
            errors.append(
                TMTConfigError(
                    f"Extra config remaining in manager: {key}. Please move them under config 'extra'."
                )
            )

        if errors:
            return errors
        return Manager(filename=filename)


# TODO: document time limit format and memory limit format
def parse_time_to_second(input_str: str) -> float:
    match = re.fullmatch(r"(\d+|\d+\.\d+)\s*(ms|s)", input_str)
    if match is None:
        raise ValueError(f'"{input_str}" is an invalid time string.')
    if match.group(2) == "ms":
        return float(match.group(1)) / 1000.0
    else:
        return float(match.group(1))


def parse_bytes_to_mib(input_str: str) -> int:
    if input_str == "unlimited":
        return resource.RLIM_INFINITY
    match = re.fullmatch(r"(\d+)\s*(G|GiB|M|MiB)", input_str)
    if match is None:
        raise ValueError(f'"{input_str}" is an invalid memory string.')
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
        errors = []

        type = data.pop("type", None)
        grader_name = data.pop("grader_name", None)
        time_limit = data.pop("time_limit", None)
        memory_limit = data.pop("memory_limit", None)
        output_limit = data.pop("output_limit", None)
        num_procs = data.pop("num_procs", None)
        use_fifo = data.pop("use_fifo", None)

        try:
            type = SolutionType(type)
        except ValueError:
            errors.append(
                TMTConfigError(
                    f"Config solution.type is not a valid value (found: {type}, expected: one of [{', '.join(t.value for t in SolutionType)}])"
                )
            )
        if grader_name is not None and not isinstance(grader_name, str):
            errors.append(
                TMTConfigError.invalid_field(
                    "solution.grader_name (string)", grader_name
                )
            )

        try:
            time_limit_sec = parse_time_to_second(time_limit)
        except (ValueError, TypeError):
            errors.append(
                TMTConfigError(
                    f"Invalid config solution.time_limit (found {time_limit}, expected numbers s/ms)"
                )
            )

        try:
            memory_limit_mib = parse_bytes_to_mib(memory_limit)
            if memory_limit_mib == resource.RLIM_INFINITY:
                errors.append(
                    TMTConfigError("Config solution.memory_limit must not be unlimited")
                )
        except (ValueError, TypeError):
            errors.append(
                TMTConfigError(
                    f"Invalid config solution.memory_limit (found {memory_limit}, expected numbers M/MiB/G/GiB)"
                )
            )

        try:
            output_limit_mib = parse_bytes_to_mib(output_limit)
        except (ValueError, TypeError):
            errors.append(
                TMTConfigError(
                    f"Invalid config solution.output_limit (found {output_limit}, expected numbers M/MiB/G/GiB or unlimited)"
                )
            )

        if num_procs is not None:
            if not isinstance(num_procs, int):
                errors.append(
                    TMTConfigError.invalid_field("solution.num_procs (int)", num_procs)
                )
            elif num_procs <= 0:
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

        if use_fifo is not None:
            if not isinstance(use_fifo, bool):
                errors.append(
                    TMTConfigError.invalid_field("solution.use_fifo (bool)", use_fifo)
                )
        else:
            use_fifo = False

        if type == SolutionType.GRADER and grader_name is None:
            errors.append(
                TMTConfigError(
                    "Invalid config solution.grader_name: Tasks with grader must supply solution.grader_name."
                )
            )

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
        errors = []

        type = data.pop("type", None)
        filename = data.pop("filename", None)

        try:
            type = AnswerGenerationType(type)
        except ValueError:
            errors.append(
                TMTConfigError(
                    f"Config answer_generation.type ({type}) is not a valid value"
                )
            )
        if filename is not None and not isinstance(filename, str):
            errors.append(
                TMTConfigError.invalid_field(
                    "answer_generation.filename (string)", filename
                )
            )

        if type == AnswerGenerationType.SOLUTION and filename is None:
            errors.append(
                TMTConfigError(
                    "Config answer_generation.filename must be specified when type is 'solution'."
                )
            )

        for key in data.keys():
            errors.append(
                TMTConfigError(
                    f"Extra config remaining in answer_generation: {key}. Please move them under config 'extra'."
                )
            )

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
        errors = []

        title = data.pop("title", None)
        short_name = data.pop("short_name", None)
        description = data.pop("description", None)
        tmt_version = data.pop("tmt_version", None)
        input_extension = data.pop("input_extension", None)
        output_extension = data.pop("output_extension", None)
        judge_convention = data.pop("judge_convention", None)
        problem_type = data.pop("problem_type", None)

        if not isinstance(title, str):
            errors.append(TMTConfigError.invalid_field("title (string)", title))
        if not isinstance(short_name, str):
            errors.append(
                TMTConfigError.invalid_field("short_name (string)", short_name)
            )
        if description and not isinstance(description, str):
            errors.append(
                TMTConfigError.invalid_field("description (string)", description)
            )
        # TODO warn for tmt_version

        if not isinstance(input_extension, str):
            errors.append(
                TMTConfigError.invalid_field(
                    "input_extension (string)", input_extension
                )
            )
        if not isinstance(output_extension, str):
            errors.append(
                TMTConfigError.invalid_field(
                    "output_extension (string)", output_extension
                )
            )

        if not input_extension.startswith("."):
            errors.append(
                TMTConfigError("Config input_extension should start with a dot.")
            )
        if not output_extension.startswith("."):
            errors.append(
                TMTConfigError("Config output_extension should start with a dot.")
            )
        if (
            isinstance(input_extension, str)
            and isinstance(output_extension, str)
            and input_extension == output_extension
        ):
            errors.append(
                TMTConfigError(
                    "Config input_extension and output_extension must not be the same."
                )
            )
        try:
            judge_convention = JudgeConvention(judge_convention)
        except ValueError:
            errors.append(
                TMTConfigError(
                    f"Config judge_convention is not a valid value (found: {judge_convention}, expected: one of [{', '.join(j.value.name for j in JudgeConvention)}])"
                )
            )
        try:
            problem_type = ProblemType(problem_type)
        except ValueError:
            errors.append(
                TMTConfigError(
                    f"Config problem_type is not a valid value (found: {problem_type}, expected: one of [{', '.join(p.value for p in ProblemType)}]) "
                )
            )

        validator = Validator.from_raw(data.pop("validator", None))
        if not isinstance(validator, Validator):
            errors.extend(validator)

        solution = Solution.from_raw(data.pop("solution", None))
        if not isinstance(solution, Solution):
            errors.extend(solution)

        answer_generation = AnswerGeneration.from_raw(
            data.pop("answer_generation", None)
        )
        if not isinstance(answer_generation, AnswerGeneration):
            errors.extend(answer_generation)

        if (checker := data.pop("checker", None)) is not None:
            checker = Checker.from_raw(checker)
            if not isinstance(checker, Checker):
                errors.extend(checker)

        if (interactor := data.pop("interactor", None)) is not None:
            interactor = Interactor.from_raw(interactor)
            if not isinstance(interactor, Interactor):
                errors.extend(interactor)

        if (manager := data.pop("manager", None)) is not None:
            manager = Manager.from_raw(manager)
            if not isinstance(manager, Manager):
                errors.extend(manager)

        compile_time_limit_sec = None
        if (compile_time_limit := data.pop("compile_time_limit", None)) is not None:
            try:
                compile_time_limit_sec = parse_time_to_second(compile_time_limit)
            except (ValueError, TypeError):
                errors.append(
                    TMTConfigError(
                        f"Invalid config compile_time_limit (found {compile_time_limit}, expected numbers s/ms)"
                    )
                )

        compile_memory_limit_mib = None
        if (compile_memory_limit := data.pop("compile_memory_limit", None)) is not None:
            try:
                compile_memory_limit_mib = parse_bytes_to_mib(compile_memory_limit)
            except (ValueError, TypeError):
                errors.append(
                    TMTConfigError(
                        f"Invalid config compile_memory_limit (found {compile_memory_limit}, expected numbers M/MiB/G/GiB or unlimited)"
                    )
                )

        if isinstance(problem_type, ProblemType):
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
                if checker is not None:
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
        for key in data.keys():
            errors.append(
                TMTConfigError(
                    f"Extra config remaining in . (root): {key}. Please move them under config 'extra'."
                )
            )

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
