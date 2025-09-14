import os
import shutil
import stat

from internal.errors import TMTMissingFileError
# from internal.errors import TMTParsingError


# Subdirectories properties creation helper
def _problem_path_property(*kwargs):
    def combine_path(self: "ProblemDirectoryHelper") -> str:
        return os.path.join(self.problem_dir, *kwargs)

    return property(combine_path)


def _extend_path_property(parent_prop: property, *kwargs):
    def combine_path(self: "ProblemDirectoryHelper") -> str:
        if parent_prop.fget is None:
            raise ValueError("_extend_path_property: parent_prop.fget is None")
        return os.path.join(parent_prop.fget(self), *kwargs)

    return property(combine_path)


def _internal_path_property(*kwargs):
    def combine_path(self: "ProblemDirectoryHelper"):
        return os.path.join(self.script_dir, *kwargs)

    return property(combine_path)


class ProblemDirectoryHelper:
    """
    Helps everything with files and directories.
    """

    PROBLEM_YAML = "problem.yaml"

    def __init__(self, problem_dir: str, script_dir: str):
        self.problem_dir = problem_dir
        self.script_dir = script_dir

    include = _problem_path_property("include")

    validator = _problem_path_property("validator")
    validator_build = _extend_path_property(validator, "build")

    generator = _problem_path_property("generator")
    generator_build = _extend_path_property(generator, "build")
    generator_manuals = _extend_path_property(generator, "manual")

    solutions = _problem_path_property("solutions")

    checker = _problem_path_property("checker")
    checker_build = _extend_path_property(checker, "build")

    interactor = _problem_path_property("interactor")
    interactor_build = _extend_path_property(interactor, "build")

    testcases = _problem_path_property("testcases")
    testcases_summary = _extend_path_property(testcases, "summary")
    testcases_hashes = _extend_path_property(testcases, "hash.json")

    sandbox = _problem_path_property("sandbox")
    sandbox_generation = _extend_path_property(sandbox, "generation")
    sandbox_validation = _extend_path_property(sandbox, "validation")
    sandbox_solution = _extend_path_property(sandbox, "solution")
    sandbox_checker = _extend_path_property(sandbox, "checker")
    sandbox_interactor = _extend_path_property(sandbox, "interactor")
    sandbox_manager = _extend_path_property(sandbox, "manager")

    logs = _problem_path_property("logs")
    logs_generation = _extend_path_property(logs, "generation")
    logs_invocation = _extend_path_property(logs, "invocation")

    # Important files
    problem_yaml = _problem_path_property("problem.yaml")
    compiler_yaml = _problem_path_property("compiler.yaml")
    tmt_recipe = _problem_path_property("recipe")

    default_checker_icpc = _internal_path_property("internal", "steps", "checker", "default_checkers", "icpc_default_validator.cc")

    def clean_testcases(self, keep_hash=True):
        testcase_hash_exists = os.path.exists(self.testcases_hashes)
        if os.path.exists(self.testcases):
            for filename in os.listdir(self.testcases):
                file_path = os.path.join(self.testcases, filename)
                if (
                    keep_hash
                    and testcase_hash_exists
                    and os.path.samefile(file_path, self.testcases_hashes)
                ):
                    continue
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)

    def clean_logs(self):
        if os.path.exists(self.logs):
            shutil.rmtree(self.logs)

    def empty_directory(self, path: str):
        """Empties a directory."""

        for filename in os.listdir(path):
            file_path = os.path.join(path, filename)
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)

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

    def has_interactor_directory(self):
        return self._is_directory(self.interactor)

    def replace_with_solution(self, full_filename: str):
        test_files = [
            os.path.join(self.solutions, full_filename),
        ]
        for test_file in test_files:
            if self._is_regular_file(test_file):
                return test_file
        raise TMTMissingFileError("solution", full_filename)

    # def replace_with_grader(self, file: str):

    def replace_with_manual(self, full_filename: str):
        if self._is_regular_file(os.path.join(self.generator_manuals, full_filename)):
            return os.path.join(self.generator_manuals, full_filename)
        raise TMTMissingFileError("manual", full_filename)
