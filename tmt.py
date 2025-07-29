import argparse
import pathlib
import subprocess
import yaml
import os

from internal.recipe_parser import parse_contest_data
from internal.utils import format_make_compile_string, format_single_compile_string, format_single_run_string, make_file_extension
from internal.paths import ProblemDirectoryHelper
from internal.step_generation import GenerationStep
from internal.step_validation import ValidationStep
from internal.step_solution import EvaluationOutcome
from internal.step_solution_batch import BatchSolutionStep
from internal.step_checker_icpc import ICPCCheckerStep


def find_tmt_root() -> pathlib.Path:
    """Find the root directory of tmt tasks."""

    current = pathlib.Path.cwd()
    while current != current.parent:
        if (current / "problem.yaml").exists():
            return current
        current = current.parent
    raise FileNotFoundError(
        "No tmt root found in the directory hierarchy. The directory must contain a problem.yaml file.")


def initialize_directory(root_dir: pathlib.Path):
    """Initialize the given directory for tmt tasks."""

    if not root_dir.exists():
        raise FileNotFoundError(f"Directory {root_dir} does not exist.")
    if not root_dir.is_dir():
        raise NotADirectoryError(f"{root_dir} is not a directory.")
    if any(root_dir.iterdir()):
        raise ValueError(f"Directory {root_dir} is not empty.")

    raise NotImplementedError(
        "Directory initialization is not implemented yet.")


def cprint(*args, **kwargs):
    print(*args, **kwargs, end='', flush=True)


def load_config(root_dir: pathlib.Path):
    # use PyYAML to parse the problem.yaml file
    problem_yaml_path = root_dir / "problem.yaml"
    with open(problem_yaml_path, 'r') as file:
        problem_yaml = yaml.safe_load(file)
    return problem_yaml


def generate_testcases(root_dir: pathlib.Path):
    """Generate test cases in the given directory."""

    if not root_dir.exists():
        raise FileNotFoundError(f"Directory {root_dir} does not exist.")
    if not root_dir.is_dir():
        raise NotADirectoryError(f"{root_dir} is not a directory.")

    print(f"Generating test cases in {root_dir}...")

    config = load_config(root_dir)

    script_path = pathlib.Path(__file__).parent.resolve()
    internal_makefile_path = script_path / "internal" / "Makefile"
    # Compile generators, validators and solutions

    generation_stage = GenerationStep(str(root_dir), str(internal_makefile_path))
    validation_stage = ValidationStep(str(root_dir), str(internal_makefile_path))
    # TODO: change type and model solution path accordin to setting
    solution_stage = BatchSolutionStep(executable_name=config["id"],
                                       problem_dir=str(root_dir),
                                       submission_file="sol.cpp",
                                       time_limit=config["time_limit"],
                                       memory_limit=config["memory_limit"] * 1024,
                                       output_limit=config["output_limit"],
                                       grader=None)

    cprint("Generator\tcompile ")
    generation_stage.prepare_sandbox()
    compile_out, compile_err, compile_exitcode = generation_stage.compile()
    cprint(format_make_compile_string(compile_out, compile_err, compile_exitcode))
    if compile_exitcode != 0:
        exit(compile_exitcode)

    cprint("Validator\tcompile ")
    validation_stage.prepare_sandbox()
    compile_out, compile_err, compile_exitcode = validation_stage.compile()
    cprint(format_make_compile_string(compile_out, compile_err, compile_exitcode))
    if compile_exitcode != 0:
        exit(compile_exitcode)

    cprint("Solution\tcompile ")
    solution_stage.prepare_sandbox()
    compile_err, compile_exitcode = solution_stage.compile_solution()
    cprint(format_single_compile_string(compile_err, compile_exitcode))
    if compile_exitcode != 0:
        exit(compile_exitcode)

    recipe = parse_contest_data(open(str(root_dir / "recipe")).readlines())

    # TODO: it is better to do this in recipe_parser.py but I fear not to touch the humongous multiclass structure
    # so I temporarily write it here
    validations = {test.test_name: [] for testset in recipe.testsets.values() for test in testset.tests}
    for subtask in recipe.subtasks.values():
        for testset in subtask.tests:
            for attempt_testset_match in recipe.testsets.values():
                if attempt_testset_match.testset_name == testset:
                    for tests in attempt_testset_match.tests:
                        for validator in subtask.validation:
                            if len(validator.commands) > 1:
                                raise ValueError("Validator with pipe is not supported")
                            validations[tests.test_name].append(validator.commands[0])

    working_dir_helper = ProblemDirectoryHelper(str(root_dir))
    working_dir_helper.mkdir_testcases()
    pathlib.Path(working_dir_helper.testcases_summary).touch()

    with open(working_dir_helper.testcases_summary, "wt") as testcases_summary:
        for testset in recipe.testsets.values():
            for test in testset.tests:
                cprint(f"\t{test.test_name}\t")
                cprint("gen ")
                gen_result = generation_stage.run_generator(test.commands,
                                                            test.test_name,
                                                            config['input_extension'],
                                                            list(testset.extra_file))
                cprint(format_single_run_string(gen_result))
                cprint("val ")
                val_result = validation_stage.run_validator(validations[test.test_name],
                                                            test.test_name,
                                                            config['input_extension'],
                                                            list(testset.extra_file))
                cprint(format_single_run_string(val_result))
                cprint("sol ")
                sol_result = solution_stage.run_solution(test.test_name,
                                                         config['input_extension'],
                                                         config['output_extension'],
                                                         True)
                sol_result = sol_result.verdict == EvaluationOutcome.RUN_SUCCESS
                cprint(format_single_run_string(sol_result))
                cprint("\n")

                if gen_result and val_result and sol_result:
                    testcases_summary.write(f"{test.test_name}\n")

    print(config)
    print("Test cases generated successfully.")


def invoke_solution(root_dir: pathlib.Path, files: list[str]):
    working_dir_helper = ProblemDirectoryHelper(str(root_dir))
    config = load_config(root_dir)

    script_path = pathlib.Path(__file__).parent.resolve()
    checker_makefile_path = str(script_path / "internal" / "CheckerMakefile")

    if pathlib.Path(working_dir_helper.testcases_summary).exists():
        # TODO: change this according to the task configuration
        if len(files) != 1:
            raise ValueError("Please specify exactly 1 file.")

        solution_step = BatchSolutionStep(executable_name=config["id"],
                                          problem_dir=str(root_dir),
                                          submission_file=files[0],
                                          time_limit=config["time_limit"],
                                          memory_limit=config["memory_limit"] * 1024,
                                          output_limit=config["output_limit"],
                                          grader=None)
        checker_step = ICPCCheckerStep(problem_dir=str(root_dir),
                                   makefile_path=checker_makefile_path)

        cprint("Solution\tcompile ")
        solution_step.prepare_sandbox()
        compile_err, compile_exitcode = solution_step.compile_solution()
        cprint(format_single_compile_string(compile_err, compile_exitcode))
        if compile_exitcode != 0:
            exit(compile_exitcode)

        cprint("Checker\tcompile ")
        checker_step.prepare_sandbox()
        compile_out, compile_err, compile_exitcode = checker_step.compile()
        cprint(format_make_compile_string(compile_out, compile_err, compile_exitcode))
        if compile_exitcode != 0:
            exit(compile_exitcode)

    with open(working_dir_helper.testcases_summary, "rt") as testcases_summary:
        for test_name in testcases_summary.readlines():
            test_name = test_name.strip()

            cprint(f"\t{test_name}\t")
            cprint("sol ")
            sol_result = solution_step.run_solution(test_name, config['input_extension'], config['output_extension'], False)
            cprint(format_single_run_string(sol_result.verdict == EvaluationOutcome.RUN_SUCCESS))
            cprint("check ")
            # TODO: find actual argument to pass to checker
            testcase_input = os.path.join(working_dir_helper.testcases, test_name + make_file_extension(config['input_extension']))
            testcase_answer = os.path.join(working_dir_helper.testcases, test_name + make_file_extension(config['output_extension']))
            check_result = checker_step.run_checker([], sol_result, testcase_input, testcase_answer)
            # TODO: this following check is incorrect
            cprint(format_single_run_string(check_result != EvaluationOutcome.CHECKER_CRASHED))
            cprint(check_result.verdict)
            cprint("\n")




def main():
    parser = argparse.ArgumentParser(description="tmt - task management tools")
    parser.add_argument(
        "--version", action="version", version="tmt 0.0.0",
        help="Show the version of tmt"
    )
    parser.add_argument(
        "command", choices=["init", "gen", "clean", "invoke"],
        help="Command to execute: init, gen, clean, or invoke"
    )

    args, remaining = parser.parse_known_args()

    if args.command == "init":
        initialize_directory(pathlib.Path.cwd())
    elif args.command == "gen":
        root_dir = find_tmt_root()
        generate_testcases(root_dir)
    elif args.command == "invoke":
        root_dir = find_tmt_root()
        invoke_solution(root_dir, remaining)
    elif args.command == "clean":
        root_dir = find_tmt_root()
        # clean_testcases(root_dir)
        raise NotImplementedError(
            "The 'clean' command is not implemented yet."
        )


if __name__ == "__main__":
    main()
