import os

GENERATOR_PATH = "generator"
GENERATOR_MANUAL_PATH = "generator/manual"
TESTS_PATH = "testcases"
SANDBOX_PATH = "sandbox"
LOGS_PATH = "logs"


def prepare_tests_dir(problem_dir):
    tests_path = os.path.join(problem_dir, TESTS_PATH)
    if not os.path.isdir(tests_path):
        os.mkdir(tests_path)


def prepare_sandbox_dir(problem_dir):
    sandbox_path = os.path.join(problem_dir, SANDBOX_PATH)
    if not os.path.isdir(sandbox_path):
        os.mkdir(sandbox_path)


def prepare_logs_dir(problem_dir):
    logs_path = os.path.join(problem_dir, LOGS_PATH)
    if not os.path.isdir(logs_path):
        os.mkdir(logs_path)
