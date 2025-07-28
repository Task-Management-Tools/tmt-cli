import argparse
import pathlib
import subprocess
import yaml
import os

from internal.generation_stage import GenerationStage
from internal.validation_stage import ValidationStage
from internal.recipe_parser import parse_contest_data

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

    generation_stage = GenerationStage(str(root_dir), str(internal_makefile_path))
    validation_stage = ValidationStage(str(root_dir), str(internal_makefile_path))

    ok_or_fail = lambda result: f"[{'OK' if result else 'FAIL'}]"

    cprint("Generator\tcompile ")
    result = generation_stage.compile()
    cprint(f"{ok_or_fail(result)}\n")
    cprint("Validator\tcompile ")
    result = validation_stage.compile()
    cprint(f"{ok_or_fail(result)}\n")
    

    for subdir in ["solution"]:
        subdir_path = root_dir / subdir
        if not subdir_path.exists() or not subdir_path.is_dir():
            raise FileNotFoundError(
                f"Subdirectory {subdir_path} does not exist.")
        cmd = ["make", "-C", str(subdir_path), "-f",
               str(internal_makefile_path)]
        CXXFLAGS = "-std=c++20 -Wall -Wextra -O2"
        subprocess.run(cmd,
                       capture_output=False,
                       check=True,
                       env={
                           "CXXFLAGS": CXXFLAGS,
                       } | os.environ)

    # TODO
    # run recipe's command

    generation_stage.prepare_sandbox()
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
