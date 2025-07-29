import argparse
import pathlib
import os

from internal.recipe_parser import parse_contest_data
from internal.utils import print_compile_string_with_exit, format_single_run_string, make_file_extension
from internal.globals import init_tmt_root, context
from internal.step_generation import GenerationStep
from internal.step_validation import ValidationStep
from internal.outcome import EvaluationOutcome
from internal.step_solution_batch import BatchSolutionStep
from internal.step_checker_icpc import ICPCCheckerStep


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


def generate_testcases():
    """Generate test cases in the given directory."""

    # Compile generators, validators and solutions
    generation_step = GenerationStep()
    validation_step = ValidationStep()
    # TODO: change type and model solution path accordin to setting
    solution_step = BatchSolutionStep(submission_files=[context.path.replace_with_solution("sol.cpp")],
                                       grader=None)

    cprint("Generator  compile ")
    generation_step.prepare_sandbox()
    print_compile_string_with_exit(generation_step.compile())

    cprint("Validator  compile ")
    validation_step.prepare_sandbox()
    print_compile_string_with_exit(validation_step.compile())

    cprint("Solution   compile ")
    solution_step.prepare_sandbox()
    # TODO: this should also compile interactor or manager, if present
    print_compile_string_with_exit(solution_step.compile_solution())


    recipe = parse_contest_data(open(context.path.recipe).readlines())

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

    context.path.mkdir_testcases()
    pathlib.Path(context.path.testcases_summary).touch()

    with open(context.path.testcases_summary, "wt") as testcases_summary:
        for testset in recipe.testsets.values():
            for test in testset.tests:
                cprint(f"\t{test.test_name}\t")
                cprint("gen ")
                gen_result = generation_step.run_generator(test.commands,
                                                            test.test_name,
                                                            list(testset.extra_file))
                cprint(format_single_run_string(gen_result))
                cprint("val ")
                val_result = validation_step.run_validator(validations[test.test_name],
                                                            test.test_name,
                                                            list(testset.extra_file))
                cprint(format_single_run_string(val_result))
                cprint("sol ")
                sol_result = solution_step.run_solution(test.test_name,
                                                         os.path.join(context.path.testcases,
                                                                      context.construct_output_filename(test.test_name)))
                sol_result = sol_result.verdict == EvaluationOutcome.RUN_SUCCESS
                cprint(format_single_run_string(sol_result))
                cprint("\n")

                if gen_result and val_result and sol_result:
                    testcases_summary.write(f"{test.test_name}\n")


def invoke_solution(files: list[str]):
    actual_files = [os.path.join(os.getcwd(), file) for file in files]

    if pathlib.Path(context.path.testcases_summary).exists():
        solution_step = BatchSolutionStep(submission_files=actual_files, grader=None)
        checker_step = ICPCCheckerStep()

        cprint("Solution   compile ")
        solution_step.prepare_sandbox()
        print_compile_string_with_exit(solution_step.compile_solution())

        cprint("Checker    compile ")
        checker_step.prepare_sandbox()
        # TODO: this should also compile interactor or manager, if present
        print_compile_string_with_exit(checker_step.compile())

    with open(context.path.testcases_summary, "rt") as testcases_summary:
        for test_name in testcases_summary.readlines():
            test_name = test_name.strip()

            cprint(f"\t{test_name}\t")
            cprint("sol ")
            sol_result = solution_step.run_solution(test_name, False)
            cprint(format_single_run_string(sol_result.verdict == EvaluationOutcome.RUN_SUCCESS))
            cprint("check ")
            # TODO: find actual argument to pass to checker
            testcase_input = os.path.join(context.path.testcases, test_name + make_file_extension(context.config.input_extension))
            testcase_answer = os.path.join(context.path.testcases, test_name + make_file_extension(context.config.output_extension))
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
        return

    init_tmt_root(str(pathlib.Path(__file__).parent.resolve()))

    if args.command == "gen":
        generate_testcases()
    elif args.command == "invoke":
        invoke_solution(remaining)
    elif args.command == "clean":
        # clean_testcases(root_dir)
        raise NotImplementedError(
            "The 'clean' command is not implemented yet."
        )


if __name__ == "__main__":
    main()
