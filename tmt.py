import argparse
import pathlib
import subprocess
import yaml
import os

from internal.step_generation import GenerationStep
from internal.step_validation import ValidationStep
from internal.step_solution_batch import BatchSolutionStep
from internal.recipe_parser import parse_contest_data
from internal.utils import format_make_compile_string, format_single_compile_string


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


def generate_testcases(root_dir: pathlib.Path):
    """Generate test cases in the given directory."""

    if not root_dir.exists():
        raise FileNotFoundError(f"Directory {root_dir} does not exist.")
    if not root_dir.is_dir():
        raise NotADirectoryError(f"{root_dir} is not a directory.")

    print(f"Generating test cases in {root_dir}...")

    # use PyYAML to parse the problem.yaml file
    problem_yaml_path = root_dir / "problem.yaml"
    with open(problem_yaml_path, 'r') as file:
        problem_yaml = yaml.safe_load(file)

    script_path = pathlib.Path(__file__).parent.resolve()
    internal_makefile_path = script_path / "internal" / "Makefile"
    # Compile generators, validators and solutions

    generation_stage = GenerationStep(str(root_dir), str(internal_makefile_path))
    validation_stage = ValidationStep(str(root_dir), str(internal_makefile_path))
    # TODO: change type and model solution path accordin to setting
    solution_stage = BatchSolutionStep(executable_name=problem_yaml["id"],
                                       problem_dir=str(root_dir),
                                       submission_file="sol.cpp",
                                       time_limit=problem_yaml["time_limit"],
                                       memory_limit=problem_yaml["memory_limit"] * 1024,
                                       output_limit=problem_yaml["output_limit"],
                                       grader=None,
                                       )

    ok_or_fail = lambda result: f"[{'OK' if result else 'FAIL'}]"

    cprint("Generator\tcompile ")
    compile_out, compile_err, compile_exitcode = generation_stage.compile()
    cprint(format_make_compile_string(compile_out, compile_err, compile_exitcode))
    if compile_exitcode != 0:
        exit(compile_exitcode)

    cprint("Validator\tcompile ")
    compile_out, compile_err, compile_exitcode = validation_stage.compile()
    cprint(format_make_compile_string(compile_out, compile_err, compile_exitcode))
    if compile_exitcode != 0:
        exit(compile_exitcode)

    cprint("Solution\tcompile ")
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


    for testset in recipe.testsets.values():
        for test in testset.tests:
            cprint(f"\t{test.test_name}\t")
            cprint("gen ")
            result = generation_stage.run_generator(test.commands,
                                                    test.test_name,
                                                    problem_yaml['input_extension'],
                                                    list(testset.extra_file))
            cprint(f"{ok_or_fail(result)}\t")
            cprint("val ")
            result = validation_stage.run_validator(validations[test.test_name],
                                                    test.test_name,
                                                    problem_yaml['input_extension'],
                                                    list(testset.extra_file))
            cprint(f"{ok_or_fail(result)}\t")
            cprint("sol ")
            result = solution_stage.run_solution_for_output(test.test_name,
                                                            problem_yaml['input_extension'],
                                                            problem_yaml['output_extension'])
            cprint(f"{ok_or_fail(result)}\n")

    print(problem_yaml)
    print("Test cases generated successfully.")


def main():
    parser = argparse.ArgumentParser(description="tmt - task management tools")
    parser.add_argument(
        "--version", action="version", version="tmt 0.0.0",
        help="Show the version of tmt"
    )
    parser.add_argument(
        "command", choices=["init", "gen", "clean"],
        help="Command to execute: init, gen, or clean"
    )

    args = parser.parse_args()

    if args.command == "init":
        initialize_directory(pathlib.Path.cwd())
    elif args.command == "gen":
        root_dir = find_tmt_root()
        generate_testcases(root_dir)
    elif args.command == "clean":
        root_dir = find_tmt_root()
        # clean_testcases(root_dir)
        raise NotImplementedError(
            "The 'clean' command is not implemented yet."
        )


if __name__ == "__main__":
    main()
