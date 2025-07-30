import os
import pathlib
import stat
import errno
import shutil
import yaml
import resource

from pathlib import Path

from internal.utils import make_file_extension
class ProblemDirectoryHelper:
    """
    Helps everything with files and directories.
    """

    MAKEFILE_NORMAL = "internal/Makefile"
    MAKEFILE_CHECKER = "internal/CheckerMakefile"

    PROBLEM_YAML = "problem.yaml"
    RECIPE = "recipe"

    VALIDATOR_PATH = "validator"
    GENERATOR_PATH = "generator"
    GENERATOR_MANUAL_PATH = "generator/manual"
    SOLUTIONS_PATH = "solutions"
    CHECKER_PATH = "checker"
    TESTCASES_PATH = "testcases"
    TESTCASES_SUMMARY_PATH = "testcases/summary"
    GRADERS_PATH = "graders"
    SANDBOX_PATH = "sandbox"
    SANDBOX_SOLUTION_PATH = "sandbox/solution"
    SANDBOX_CHECKER_PATH = "sandbox/checker"
    LOGS_PATH = "logs"

    def __init__(self, problem_dir: str, script_dir: str):
        self.problem_dir = problem_dir
        self.script_dir = script_dir

    # Subdirectories

    @property
    def validator(self): return os.path.join(self.problem_dir, self.VALIDATOR_PATH)

    @property
    def generator(self): return os.path.join(self.problem_dir, self.GENERATOR_PATH)

    @property
    def generator_manuals(self): return os.path.join(self.problem_dir, self.GENERATOR_MANUAL_PATH)

    @property
    def solutions(self): return os.path.join(self.problem_dir, self.SOLUTIONS_PATH)

    @property
    def checker(self): return os.path.join(self.problem_dir, self.CHECKER_PATH)

    @property
    def testcases(self): return os.path.join(self.problem_dir, self.TESTCASES_PATH)

    @property
    def sandbox(self): return os.path.join(self.problem_dir, self.SANDBOX_PATH)

    @property
    def sandbox_solution(self): return os.path.join(self.problem_dir, self.SANDBOX_SOLUTION_PATH)

    @property
    def sandbox_checker(self): return os.path.join(self.problem_dir, self.SANDBOX_CHECKER_PATH)

    @property
    def logs(self): return os.path.join(self.problem_dir, self.LOGS_PATH)

    # Important files

    @property
    def tmt_config(self): return os.path.join(self.problem_dir, self.PROBLEM_YAML)

    @property
    def makefile_normal(self): return os.path.join(self.script_dir, self.MAKEFILE_NORMAL)

    @property
    def makefile_checker(self): return os.path.join(self.script_dir, self.MAKEFILE_CHECKER)

    @property
    def testcases_summary(self): return os.path.join(self.problem_dir, self.TESTCASES_SUMMARY_PATH)

    @property
    def recipe(self): return os.path.join(self.problem_dir, self.RECIPE)

    def mkdir_testcases(self):
        if not os.path.isdir(self.testcases):
            os.mkdir(self.testcases)

    def mkdir_sandbox(self):
        if not os.path.isdir(self.sandbox):
            os.mkdir(self.sandbox)

    def mkdir_sandbox_solution(self):
        self.mkdir_sandbox()
        if not os.path.isdir(self.sandbox_solution):
            os.mkdir(self.sandbox_solution)

    def mkdir_sandbox_checker(self):
        self.mkdir_sandbox()
        if not os.path.isdir(self.sandbox_checker):
            os.mkdir(self.sandbox_checker)

    def mkdir_logs(self):
        if not os.path.isdir(self.logs):
            os.mkdir(self.logs)

    def clear_sandbox(self):
        self.mkdir_sandbox()
        for item in Path(self.sandbox).iterdir():
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)

    def mkdir_clean_testcases(self):
        self.mkdir_testcases()
        for item in Path(self.testcases).iterdir():
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)

    def mkdir_clean_logs(self):
        self.mkdir_logs()
        for item in Path(self.logs).iterdir():
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)

    def _is_regular_file(self, path: str):
        if not os.path.exists(path):
            return False
        return True

    def _is_directory(self, path: str):
        if not os.path.exists(path):
            return False
        st = os.stat(path)
        if stat.S_ISDIR(st.st_mode):
            return True
        return False

    def _is_executable(self, path: str):
        if not os.path.exists(path):
            return False
        st = os.stat(path)
        if stat.S_ISREG(st.st_mode) and (st.st_mode & stat.S_IXUSR):
            return True
        return False

    def has_checker_directory(self):
        return self._is_directory(self.checker)

    def replace_with_generator(self, file: str):
        test_files = [
            os.path.join(self.generator, file),
            os.path.join(self.generator, file + ".exe")
        ]
        for test_file in test_files:
            if self._is_executable(test_file):
                return test_file
        raise FileNotFoundError(errno.ENOENT, f"Generator {file} could not be found.", file)

    def replace_with_validator(self, file: str):
        test_files = [
            os.path.join(self.validator, file),
            os.path.join(self.validator, file + ".exe")
        ]
        for test_file in test_files:
            if self._is_executable(test_file):
                return test_file
        raise FileNotFoundError(errno.ENOENT, f"Validator {file} could not be found.", file)

    def replace_with_solution(self, file: str):
        test_files = [
            os.path.join(self.solutions, file),
        ]
        for test_file in test_files:
            if self._is_regular_file(test_file):
                return test_file
        raise FileNotFoundError(errno.ENOENT, f"Solution {file} could not be found.", file)

    def replace_with_grader(self, file: str):
        test_files = [
            os.path.join(self.graders, file),
        ]
        for test_file in test_files:
            if self._is_regular_file(test_file):
                return test_file
        raise FileNotFoundError(errno.ENOENT, f"Grader {file} could not be found.", file)

    def replace_with_manual(self, file: str):
        if self._is_regular_file(os.path.join(self.generator_manuals, file)):
            return os.path.join(self.generator_manuals, file)
        else:
            raise FileNotFoundError(errno.ENOENT, f"Manual {file} could not be found.", file)


class TMTConfig:
    def __init__(self, yaml: dict):
        self.problem_name = yaml["id"]
        self.time_limit = yaml["time_limit"] / 1000.0
        self.memory_limit = yaml["memory_limit"]
        self.output_limit = yaml["output_limit"]
        if self.output_limit == "unlimited":
            self.output_limit = resource.RLIM_INFINITY
        self.input_extension = yaml["input_extension"]
        self.output_extension = yaml["output_extension"]

        self.trusted_step_time_limit = 10.0 # second
        self.trusted_step_memory_limit = 4 * 1024 # MB
        self.trusted_step_output_limit = resource.RLIM_INFINITY


class TMTContext:
    def __init__(self):
        self.path: ProblemDirectoryHelper = None
        """Constructs absolute paths for the problem package. See the class for more information."""
        self.config: TMTConfig = None
        """Stores configs parsed from the problem package. See the class for more information."""

    def construct_test_filename(self, code_name, extension):
        return code_name + make_file_extension(extension)

    def construct_input_filename(self, code_name):
        return self.construct_test_filename(code_name, self.config.input_extension)
    
    def construct_output_filename(self, code_name):
        return self.construct_test_filename(code_name, self.config.output_extension)
    
context = TMTContext()


def _load_config():
    # use PyYAML to parse the problem.yaml file
    with open(context.path.tmt_config, 'r') as file:
        problem_yaml = yaml.safe_load(file)
        context.config = TMTConfig(problem_yaml)


def init_tmt_root(script_root: str) -> pathlib.Path:
    """Initialize the root directory of tmt tasks."""

    tmt_root = pathlib.Path.cwd()
    while tmt_root != tmt_root.parent:
        if (tmt_root / ProblemDirectoryHelper.PROBLEM_YAML).exists():
            context.path = ProblemDirectoryHelper(str(tmt_root), script_root)
            _load_config()
            return tmt_root
        tmt_root = tmt_root.parent

    raise FileNotFoundError(2,
                            f"No tmt root found in the directory hierarchy"
                            f"The directory must contain a {ProblemDirectoryHelper.PROBLEM_YAML} file.",
                            ProblemDirectoryHelper.PROBLEM_YAML)
