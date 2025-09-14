import pathlib
import re
import resource
import yaml

from enum import Enum

from internal.recipe_parser import parse_recipe_data
from internal.errors import TMTMissingFileError, TMTInvalidConfigError

from .paths import ProblemDirectoryHelper


class JudgeConvention(Enum):
    ICPC = "icpc"
    CMS = "cms"
    TIOJ_OLD = "old-tioj"
    TIOJ_NEW = "new-tioj"


class ProblemType(Enum):
    BATCH = "batch"
    INTERACTIVE = "interactive"


class CheckerType(Enum):
    DEFAULT = "default"
    CUSTOM = "custom"


class TMTConfig:
    # TODO: document time limit format and memory limit format
    @classmethod
    def parse_time_to_second(cls, field_name: str, input: str) -> float:
        match = re.fullmatch(r"(\d+|\d+\.\d+)\s*(ms|s)", input)
        if match is None:
            raise TMTInvalidConfigError(f'{field_name} "{input}" is invalid.')
        if match.group(2) == "ms":
            return float(match.group(1)) / 1000.0
        else:
            return float(match.group(1))

    @classmethod
    def parse_bytes_to_mib(cls, field_name: str, input: str) -> int:
        match = re.fullmatch(r"(\d+)\s*(G|GB|GiB|M|MB|MiB)", input)
        if match is None:
            raise TMTInvalidConfigError(f'{field_name} "{input}" is invalid.')
        if match.group(2).startswith("G"):
            return int(match.group(1)) * 1024
        else:
            return int(match.group(1))

    def __init__(self, yaml: dict):
        # title: display title (str)
        # short_name: problem short name (str)
        self.short_name = str(yaml["short_name"])
        # description: (str)

        # time_limit: (number) ms/s
        self.time_limit_sec = self.parse_time_to_second(
            "Time limit", yaml["time_limit"]
        )
        # memory_limit: (number) MB/GB
        self.memory_limit_mib = self.parse_bytes_to_mib(
            "Memory limit", yaml["memory_limit"]
        )

        # output_limit: (number) MB/GB or "unlimited"
        if yaml["output_limit"] == "unlimited":
            self.output_limit_mib = resource.RLIM_INFINITY
        else:
            self.output_limit_mib = self.parse_bytes_to_mib(
                "Output limit", yaml["output_limit"]
            )

        # input_extension: (str)
        self.input_extension = str(yaml["input_extension"])
        # output_extension: (str)
        self.output_extension = str(yaml["output_extension"])
        # judge_convention: (str)
        self.judge = JudgeConvention(yaml["judge_convention"])

        # problem_type: (str)
        self.problem_type = ProblemType(yaml["problem_type"])

        # solution_compilation: (str)
        # TODO: parse this option

        # solution_execution:
        # TODO: parse this option

        # input_validation: (str)
        if yaml["input_validation"] != "default":
            raise TMTInvalidConfigError(
                "Unsupported input validation mode " + yaml["input_validation"]
            )

        # checker:
        if self.problem_type is ProblemType.BATCH:
            self.checker_type = CheckerType(yaml["checker"]["type"])
            if self.checker_type is CheckerType.CUSTOM:
                self.checker_filename = yaml["checker"]["filename"]
            self.checker_arguments = yaml["checker"].get("arguments", "").split()
            self.check_forced_output = bool(
                yaml["checker"].get("check_forced_output", True)
            )
            self.check_generated_output = bool(
                yaml["checker"].get("check_generated_output", True)
            )
        else:
            if "checker" in yaml:
                raise TMTInvalidConfigError(
                    "Checker should not be specified when the problem type is not batch."
                )

        if self.problem_type is ProblemType.INTERACTIVE:
            self.interactor_filename = yaml["interactor"]["filename"]
        else:
            if "interactor" in yaml:
                raise TMTInvalidConfigError(
                    "Interactor should not be specified when the problem type is not interactive."
                )

        if yaml["answer_generation"]["type"] == "solution":
            self.model_solution_path = yaml["answer_generation"]["filename"]
        else:  # TODO: support "generator" mode
            raise TMTInvalidConfigError(
                yaml["answer_generation"]["type"]
                + " is not a valid answer generation mode"
            )

        self.trusted_compile_time_limit_sec = 60.0  # 1 minute
        self.trusted_compile_memory_limit_mib = resource.RLIM_INFINITY

        self.trusted_step_time_limit_sec = 10.0
        self.trusted_step_memory_limit_mib = 4 * 1024
        self.trusted_step_output_limit_mib = resource.RLIM_INFINITY


class TMTContext:
    def __init__(self, problem_dir: str, script_root: str):
        # context.path constructs absolute paths.
        self.path = ProblemDirectoryHelper(problem_dir, script_root)

        try:
            with open(self.path.problem_yaml, "r") as file:
                problem_yaml = yaml.safe_load(file)
            # self.config stores the parsed config from problem.yaml
            self.config = TMTConfig(problem_yaml)
        except (FileNotFoundError, IsADirectoryError, PermissionError) as e:
            raise TMTMissingFileError("config", self.path.problem_yaml) from e
        except yaml.YAMLError as e:
            raise TMTInvalidConfigError(self.path.problem_yaml) from e

        try:
            with open(self.path.compiler_yaml, "r") as file:
                self.compiler_yaml = yaml.safe_load(file)
        except (FileNotFoundError, IsADirectoryError, PermissionError) as e:
            raise TMTMissingFileError("config", self.path.compiler_yaml) from e
        except yaml.YAMLError as e:
            raise TMTInvalidConfigError(self.path.compiler_yaml) from e

        try:
            with open(self.path.tmt_recipe) as file:
                self.recipe = parse_recipe_data(file.readlines())
        except OSError as e:
            raise TMTMissingFileError("config", self.path.tmt_recipe) from e
        except ValueError as e:
            raise TMTInvalidConfigError(self.path.tmt_recipe) from e

        self.should_run_checker: bool = (
            self.config.problem_type is ProblemType.BATCH
            and self.config.checker_type is not CheckerType.DEFAULT
            and (self.config.check_forced_output or self.config.check_generated_output)
        )

    # TODO This should instead support user override of languages compilers;
    # For example, on some machine g++-version should be used over the default ones.
    # def compiler(self, language: str) -> str:
    #     if language == "cpp":
    #         return "g++"
    #     raise ValueError("Not yet supported now")

    def compile_flags(self, language: str) -> list[str]:
        return self.compiler_yaml[language]["flags"]

    def construct_test_filename(self, code_name: str, extension: str):
        if not extension.startswith("."):
            extension = "." + extension
        return code_name + extension

    def construct_input_filename(self, code_name: str):
        return self.construct_test_filename(code_name, self.config.input_extension)

    def construct_output_filename(self, code_name: str):
        return self.construct_test_filename(code_name, self.config.output_extension)


def find_problem_dir(script_root: str) -> str:
    cwd = pathlib.Path.cwd()
    for directory in [cwd] + list(cwd.parents):
        if (directory / ProblemDirectoryHelper.PROBLEM_YAML).exists():
            return str(directory.resolve())
    raise TMTMissingFileError(
        "config",
        ProblemDirectoryHelper.PROBLEM_YAML,
        "the current directory or any of its parent directories",
    )
