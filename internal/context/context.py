import os
import pathlib
import yaml


from internal.recipe_parser import parse_recipe_data
from internal.exceptions import TMTMissingFileError, TMTInvalidConfigError

from .paths import ProblemDirectoryHelper
from .config import ProblemType, TMTConfig


class TMTContext:
    def __init__(self, problem_dir: str, script_root: str):
        # context.path constructs absolute paths.
        self.path = ProblemDirectoryHelper(problem_dir, script_root)
        self._log_directory: str | None = None

        try:
            with open(self.path.problem_yaml, "r") as file:
                problem_yaml = yaml.safe_load(file)
            # self.config stores the parsed config from problem.yaml
        except (FileNotFoundError, IsADirectoryError, PermissionError) as e:
            raise TMTMissingFileError("config", self.path.problem_yaml) from e
        except yaml.YAMLError as e:
            raise TMTInvalidConfigError(self.path.problem_yaml) from e

        try:
            self.config = TMTConfig.from_raw(problem_yaml)
            if not isinstance(self.config, TMTConfig):
                raise ValueError("\n".join([e.what for e in self.config]))
        except (TypeError, ValueError) as e:
            raise TMTInvalidConfigError(self.path.problem_yaml) from e
        self.config: TMTConfig

        try:
            with open(self.path.compiler_yaml, "r") as file:
                self.compiler_yaml = yaml.safe_load(file)
        except (FileNotFoundError, IsADirectoryError, PermissionError) as e:
            raise TMTMissingFileError("config", self.path.compiler_yaml) from e
        except yaml.YAMLError as e:
            raise TMTInvalidConfigError(self.path.compiler_yaml) from e

        try:
            with open(self.path.tmt_recipe) as file:
                # TODO: the last one feels hacky, but unless this is deferred there is no way to do this
                self.recipe = parse_recipe_data(
                    file.readlines(),
                    self.config.problem_type == ProblemType.OUTPUT_ONLY,
                )
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

    @property
    def log_directory(self) -> str:
        if self._log_directory is None:
            raise ValueError("Log file required while context holds none")
        return self._log_directory

    @log_directory.setter
    def log_directory(self, value: str | None) -> None:
        self._log_directory = value
        if self._log_directory is not None:
            os.makedirs(self._log_directory, exist_ok=True)

    def log_file(self, filename: str):
        return os.path.join(self.log_directory, filename)


def find_problem_dir(cwd: pathlib.Path) -> str:
    for directory in [cwd] + list(cwd.parents):
        if (directory / ProblemDirectoryHelper.PROBLEM_YAML).exists():
            return str(directory.resolve())
    raise TMTMissingFileError(
        "config",
        ProblemDirectoryHelper.PROBLEM_YAML,
        "the current directory or any of its parent directories",
    )
