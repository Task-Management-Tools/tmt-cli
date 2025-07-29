import os
import stat
import errno
import shutil

from pathlib import Path

class ProblemDirectoryHelper:
    """
    Helps everything with files and directories.
    """

    PROBLEM_YAML = "problem.yaml"
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

    def __init__(self, problem_dir: str):
        self.problem_dir = problem_dir

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
    def testcases_summary(self): return os.path.join(self.problem_dir, self.TESTCASES_SUMMARY_PATH)

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
