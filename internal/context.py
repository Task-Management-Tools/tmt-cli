import pathlib
import yaml
import resource
import re

from enum import Enum

from internal.utils import make_file_extension
from internal.paths import ProblemDirectoryHelper
from internal.step_solution_batch import BatchSolutionStep
from internal.step_solution_interactive_icpc import InteractiveICPCSolutionStep


class JudgeConvention(Enum):
    ICPC = "icpc"
    CMS = "cms"
    TIOJ = "tioj"


class TMTConfig:
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
        self.problem_name = yaml["id"]

        # TODO: document this
        time_limit_match = re.fullmatch(r"(\d+|\d+\.\d+)\s*(ms|s)", yaml["time_limit"])
        if time_limit_match is None:
            raise ValueError(f"Time limit \"{yaml["time_limit"]}\" is invalid.")
        if time_limit_match.group(2) == "ms":
            self.time_limit_sec = float(time_limit_match.group(1)) / 1000.0
        else:
            self.time_limit_sec = float(time_limit_match.group(1))

        self.memory_limit_mib = self.parse_bytes_to_mib("Memory limit", yaml["memory_limit"])
        if yaml["output_limit"] == "unlimited":
            self.output_limit_mib = resource.RLIM_INFINITY
        else:
            self.output_limit_mib = self.parse_bytes_to_mib("Output limit", yaml["output_limit"])
        self.input_extension = yaml["input_extension"]
        self.output_extension = yaml["output_extension"]

        self.judge = JudgeConvention(yaml["judge_convention"])

        if yaml["output_validation"]["type"] == "default":
            self.solution_step = BatchSolutionStep
        elif yaml["output_validation"]["type"] == "interactive":
            self.solution_step = InteractiveICPCSolutionStep
        else:
            raise ValueError(yaml["output_validation"]["type"] + " is not a valid output validation mode")
        
        if yaml["answer_generation"]["type"] == "solution":
            self.model_solution_path = yaml["answer_generation"]["file"]
        else: # TODO: support "generator" mode
            raise ValueError(yaml["answer_generation"]["type"] + " is not a valid answer generation mode")


        self.trusted_compile_time_limit_sec = 60.0  # 1 minute
        self.trusted_compile_memory_limit_mib = resource.RLIM_INFINITY

        self.trusted_step_time_limit_sec = 10.0
        self.trusted_step_memory_limit_mib = 4 * 1024
        self.trusted_step_output_limit_mib = resource.RLIM_INFINITY


class TMTContext:
    def __init__(self):
        self.path: ProblemDirectoryHelper = None
        """Constructs absolute paths for the problem package. See the class for more information."""
        self.config: TMTConfig = None
        """Stores configs parsed from the problem package. See the class for more information."""
        
        self.compiler = "g++"
        self.compile_flags = ["-std=gnu++20", "-Wall", "-Wextra", "-O2"] # TODO read it from .yaml

    def construct_test_filename(self, code_name, extension):
        return code_name + make_file_extension(extension)

    def construct_input_filename(self, code_name):
        return self.construct_test_filename(code_name, self.config.input_extension)

    def construct_output_filename(self, code_name):
        return self.construct_test_filename(code_name, self.config.output_extension)


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
