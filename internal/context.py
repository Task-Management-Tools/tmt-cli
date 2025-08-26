import pathlib
import yaml
import resource
import re

from enum import Enum
from typing import Type

from internal.utils import make_file_extension
from internal.paths import ProblemDirectoryHelper
from internal.step_solution import MetaSolutionStep
from internal.step_solution_batch import BatchSolutionStep
from internal.step_solution_interactive_icpc import InteractiveICPCSolutionStep

class TMTContext:
    def __init__(self):
        self.path: ProblemDirectoryHelper = None
        """Constructs absolute paths for the problem package. See the class for more information."""
        self.config: 'TMTConfig' = None
        """Stores configs parsed from the problem package. See the class for more information."""

        self.compiler = "g++"
        self.compile_flags = ["-std=gnu++20", "-Wall", "-Wextra", "-O2"]  # TODO read it from .yaml

    def construct_test_filename(self, code_name, extension):
        return code_name + make_file_extension(extension)

    def construct_input_filename(self, code_name):
        return self.construct_test_filename(code_name, self.config.input_extension)

    def construct_output_filename(self, code_name):
        return self.construct_test_filename(code_name, self.config.output_extension)

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
            raise ValueError(f"{field_name} \"{match}\" is invalid.")
        if match.group(2) == "ms":
            return float(match.group(1)) / 1000.0
        else:
            return float(match.group(1))

    @classmethod
    def parse_bytes_to_mib(cls, field_name: str, input: str) -> int:
        match = re.fullmatch(r"(\d+)\s*(G|GB|GiB|M|MB|MiB)", input)
        if match is None:
            raise ValueError(f"{field_name} \"{match}\" is invalid.")
        if match.group(2).startswith('G'):
            return int(match.group(1)) * 1024
        else:
            return int(match.group(1))

    def __init__(self, yaml: dict):
        # title: display title (str)
        # short_name: problem short name (str)
        self.short_name = str(yaml["short_name"])
        # description: (str)

        # time_limit: (number) ms/s
        self.time_limit_sec = self.parse_time_to_second("Time limit", yaml["time_limit"])
        # memory_limit: (number) MB/GB
        self.memory_limit_mib = self.parse_bytes_to_mib("Memory limit", yaml["memory_limit"])

        # output_limit: (number) MB/GB or "unlimited"
        if yaml["output_limit"] == "unlimited":
            self.output_limit_mib = resource.RLIM_INFINITY
        else:
            self.output_limit_mib = self.parse_bytes_to_mib("Output limit", yaml["output_limit"])

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
            raise ValueError("Unsupported input validation mode " + yaml["input_validation"])

        # output_validation:
        if self.problem_type is ProblemType.BATCH:
            self.checker_type = CheckerType(yaml["output_validation"]["type"])
            if self.checker_type is CheckerType.CUSTOM:
                self.checker_filename = yaml["output_validation"]["filename"]
            self.checker_arguments = yaml["output_validation"].get("arguments", "").split()
            self.check_forced_output = bool(yaml["output_validation"].get("arguments", True))
        else:
            if "output_validation" in yaml:
                raise ValueError("Output validation should not be specified when the problem type is not batch.")

        if yaml["answer_generation"]["type"] == "solution":
            self.model_solution_path = yaml["answer_generation"]["filename"]
        else:  # TODO: support "generator" mode
            raise ValueError(yaml["answer_generation"]["type"] + " is not a valid answer generation mode")

        self.trusted_compile_time_limit_sec = 60.0  # 1 minute
        self.trusted_compile_memory_limit_mib = resource.RLIM_INFINITY

        self.trusted_step_time_limit_sec = 10.0
        self.trusted_step_memory_limit_mib = 4 * 1024
        self.trusted_step_output_limit_mib = resource.RLIM_INFINITY

    def get_solution_step(self) -> Type[MetaSolutionStep]:
        if self.problem_type is ProblemType.BATCH:
            return BatchSolutionStep
        elif self.problem_type is ProblemType.INTERACTIVE:
            return InteractiveICPCSolutionStep
        else:
            raise ValueError(str(self.problem_type) + " is not a valid problem type.")



def _load_config(context: TMTContext):
    # use PyYAML to parse the problem.yaml file
    with open(context.path.tmt_config, 'r') as file:
        problem_yaml = yaml.safe_load(file)
        context.config = TMTConfig(problem_yaml)


def init_tmt_root(script_root: str) -> TMTContext:
    """Initialize the root directory of tmt tasks."""

    context = TMTContext()

    tmt_root = pathlib.Path.cwd()
    while tmt_root != tmt_root.parent:
        if (tmt_root / ProblemDirectoryHelper.PROBLEM_YAML).exists():
            context.path = ProblemDirectoryHelper(str(tmt_root), script_root)
            _load_config(context)
            return context
        tmt_root = tmt_root.parent

    raise FileNotFoundError(2,
                            f"No tmt root found in the directory hierarchy"
                            f"The directory must contain a {ProblemDirectoryHelper.PROBLEM_YAML} file.",
                            ProblemDirectoryHelper.PROBLEM_YAML)
