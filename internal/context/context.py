import pathlib
import yaml


from internal.recipe_parser import parse_recipe_data
from internal.exceptions import TMTMissingFileError, TMTInvalidConfigError

from .paths import ProblemDirectoryHelper
from .config import TMTConfig


class TMTContext:
    def __init__(self, problem_dir: str, script_root: str):
        # context.path constructs absolute paths.
        self.path = ProblemDirectoryHelper(problem_dir, script_root)

        try:
            with open(self.path.problem_yaml, "r") as file:
                problem_yaml = yaml.safe_load(file)
            # self.config stores the parsed config from problem.yaml
        except (FileNotFoundError, IsADirectoryError, PermissionError) as e:
            raise TMTMissingFileError("config", self.path.problem_yaml) from e
        except yaml.YAMLError as e:
            raise TMTInvalidConfigError(self.path.problem_yaml) from e

        try:
            self.config = TMTConfig(**problem_yaml)
        except (TypeError, ValueError) as e:
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


def find_problem_dir(cwd: pathlib.Path) -> str:
    for directory in [cwd] + list(cwd.parents):
        if (directory / ProblemDirectoryHelper.PROBLEM_YAML).exists():
            return str(directory.resolve())
    raise TMTMissingFileError(
        "config",
        ProblemDirectoryHelper.PROBLEM_YAML,
        "the current directory or any of its parent directories",
    )
