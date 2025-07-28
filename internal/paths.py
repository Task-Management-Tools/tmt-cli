import os
import stat
import errno

class ProblemDirectoryHelper:
    """
    Helps everything with files and directories.
    """

    GENERATOR_PATH = "generator"
    GENERATOR_MANUAL_PATH = "generator/manual"
    TESTCASES_PATH = "testcases"
    SANDBOX_PATH = "sandbox"
    LOGS_PATH = "logs"

    def __init__(self, problem_dir: str):
        self.problem_dir = problem_dir

    @property
    def generator(self): return os.path.join(self.problem_dir, self.GENERATOR_PATH)

    @property
    def generator_manuals(self): return os.path.join(self.problem_dir, self.GENERATOR_MANUAL_PATH)

    @property
    def testcases(self): return os.path.join(self.problem_dir, self.TESTCASES_PATH)

    @property
    def sandbox(self): return os.path.join(self.problem_dir, self.SANDBOX_PATH)

    @property
    def logs(self): return os.path.join(self.problem_dir, self.SANDBOX_PATH)

    def mkdir_testcases(self):
        if not os.path.isdir(self.testcases):
            os.mkdir(self.testcases)

    def mkdir_sandbox(self):
        if not os.path.isdir(self.sandbox):
            os.mkdir(self.sandbox)

    def mkdir_logs(self):
        if not os.path.isdir(self.logs):
            os.mkdir(self.logs)

    def _is_regular_file(self, path: str):
        if not os.path.exists(path):
            return False
        return True

    def _is_executable(self, path: str):
        if not os.path.exists(path):
            return False
        st = os.stat(path)
        if stat.S_ISREG(st.st_mode) and (st.st_mode & stat.S_IXUSR):
            return True
        return False

    def replace_with_generator(self, file: str):
        test_files = [
            os.path.join(self.generator, file),
            os.path.join(self.generator, file + ".exe")
        ]
        for test_file in test_files:
            if self._is_executable(test_file):
                return test_file
        raise FileNotFoundError(errno.ENOENT, f"Generator {file} could not be found.", file)

    def replace_with_manual(self, file: str):
        if self._is_regular_file(os.path.join(self.generator_manuals, file)):
            return os.path.join(self.generator_manuals, file)
        else:
            raise FileNotFoundError(errno.ENOENT, f"Manual {file} could not be found.", file)
