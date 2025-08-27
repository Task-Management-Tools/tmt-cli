import os
import errno
import shutil
import stat


class ProblemDirectoryHelper:
    """
    Helps everything with files and directories.
    """

    MAKEFILE_NORMAL = "internal/Makefile"
    MAKEFILE_CHECKER = "internal/CheckerMakefile"

    PROBLEM_YAML = "problem.yaml"

    def __init__(self, problem_dir: str, script_dir: str):
        self.problem_dir = problem_dir
        self.script_dir = script_dir

    # Subdirectories

    def _problem_path_property(*name):
        def combine_path(self: 'ProblemDirectoryHelper'):
            return os.path.join(self.problem_dir, *name)
        return property(combine_path)

    def _extend_path_property(base: property, *name):
        return property(lambda self: os.path.join(base.fget(self), *name))

    include = _problem_path_property("include")

    validator = _problem_path_property("validator")

    generator = _problem_path_property("generator")
    generator_manuals = _extend_path_property(generator, "manual")

    solutions = _problem_path_property("solutions")

    checker = _problem_path_property("checker")

    testcases = _problem_path_property("testcases")
    testcases_summary = _extend_path_property(testcases, "summary")
    testcases_hashes = _extend_path_property(testcases, "hash.json")

    sandbox = _problem_path_property("sandbox")
    sandbox_generation = _extend_path_property(sandbox, "generation")
    sandbox_validation = _extend_path_property(sandbox, "validation")
    sandbox_solution = _extend_path_property(sandbox, "solution")
    sandbox_checker = _extend_path_property(sandbox, "checker")
    sandbox_manager = _extend_path_property(sandbox, "manager")

    logs = _problem_path_property("logs")
    logs_generation = _extend_path_property(logs, "generation")
    logs_invocation = _extend_path_property(logs, "invocation")

    # Important files
    tmt_config = _problem_path_property("problem.yaml")
    tmt_recipe = _problem_path_property("recipe")

    def _internal_path_property(*name):
        def combine_path(self: 'ProblemDirectoryHelper'):
            return os.path.join(self.script_dir, *name)
        return property(combine_path)

    makefile_normal = _internal_path_property("internal", "Makefile")
    makefile_checker = _internal_path_property("internal", "CheckerMakefile")

    def clean_testcases(self, keep_hash=True):
        testcase_hash_exists = os.path.exists(self.testcases_hashes)
        if os.path.exists(self.testcases):
            for filename in os.listdir(self.testcases):
                file_path = os.path.join(self.testcases, filename)
                if keep_hash and testcase_hash_exists and os.path.samefile(file_path, self.testcases_hashes):
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

        if not os.path.exists(path) or not os.path.isdir(path):
            raise ValueError(f"{path} is not a directory")

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
