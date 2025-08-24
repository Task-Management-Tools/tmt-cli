import argparse
import pathlib
import os

from internal.recipe_parser import parse_contest_data
from internal.utils import print_compile_string_with_exit, format_exec_result, format_checker_result, is_apport_active
from internal.context import init_tmt_root, TMTContext
from internal.step_generation import GenerationStep
from internal.step_validation import ValidationStep
from internal.outcome import ExecutionResult, ExecutionOutcome, eval_result_to_exec_result
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


def generate_testcases(context: TMTContext):
    """Generate test cases in the given directory."""

    # Compile generators, validators and solutions
    generation_step = GenerationStep(context)
    validation_step = ValidationStep(context)
    # TODO: change type and model solution path accordin to setting
    solution_step = BatchSolutionStep(context=context,
                                      time_limit=context.config.trusted_step_time_limit_sec,
                                      memory_limit=context.config.trusted_step_memory_limit_mib,
                                      output_limit=context.config.trusted_step_output_limit_mib,
                                      submission_files=[context.path.replace_with_solution("sol.cpp")])

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

    # TODO: in case of update testcases, these should be mkdir instead of mkdir_clean.
    context.path.mkdir_clean_testcases()
    context.path.mkdir_clean_logs()
    pathlib.Path(context.path.testcases_summary).touch()

    codename_length = max(map(len, validations.keys())) + 2

    with open(context.path.testcases_summary, "wt") as testcases_summary:
        for testset in recipe.testsets.values():
            for test in testset.tests:
                code_name = test.test_name

                cprint(' ' * 4 + code_name.ljust(codename_length))

                # Run generator
                cprint("gen ")
                generator_result = generation_step.run_generator(test.commands,
                                                                 code_name,
                                                                 list(testset.extra_file))
                cprint(format_exec_result(generator_result))
                generator_internal_log = os.path.join(context.path.logs, f"{code_name}.gen.log")
                with open(generator_internal_log, "w+") as f:
                    f.write(generator_result.reason)

                # Run validator
                cprint("val ")
                if generator_result.verdict is not ExecutionOutcome.SUCCESS:
                    validation_result = ExecutionResult(verdict=ExecutionOutcome.SKIPPED)
                else:
                    validation_result = validation_step.run_validator(validations[code_name],
                                                                      code_name,
                                                                      list(testset.extra_file))
                cprint(format_exec_result(validation_result))
                validator_internal_log = os.path.join(context.path.logs, f"{code_name}.val.log")
                with open(validator_internal_log, "w+") as f:
                    f.write(validation_result.reason)

                # Run solution
                cprint("sol ")
                if validation_result.verdict is not ExecutionOutcome.SUCCESS:
                    solution_result = ExecutionResult(verdict=ExecutionOutcome.SKIPPED)
                else:
                    solution_result = solution_step.run_solution(code_name,
                                                                 os.path.join(context.path.testcases,
                                                                              context.construct_output_filename(code_name)))
                    solution_result = eval_result_to_exec_result(solution_result)
                cprint(format_exec_result(solution_result))
                cprint("\n")
                solution_internal_log = os.path.join(context.path.logs, f"{code_name}.sol.log")
                with open(solution_internal_log, "w+") as f:
                    f.write(solution_result.reason)

                # TODO: this should print more meaningful contents, right now it is only the testcases
                if generator_result and validation_result and solution_result:
                    testcases_summary.write(f"{code_name}\n")


def invoke_solution(context: TMTContext, files: list[str]):

    actual_files = [os.path.join(os.getcwd(), file) for file in files]

    if pathlib.Path(context.path.testcases_summary).exists():
        solution_step = BatchSolutionStep(context=context,
                                          time_limit=context.config.time_limit_sec,
                                          memory_limit=context.config.memory_limit_mib,
                                          output_limit=context.config.output_limit_mib,
                                          submission_files=actual_files)
        checker_step = ICPCCheckerStep(context)

        cprint("Solution   compile ")
        solution_step.prepare_sandbox()
        print_compile_string_with_exit(solution_step.compile_solution())

        cprint("Checker    compile ")
        checker_step.prepare_sandbox()
        # TODO: this should also compile interactor or manager, if present
        print_compile_string_with_exit(checker_step.compile())

    recipe = parse_contest_data(open(context.path.recipe).readlines())
    all_testcases = [test.test_name for testset in recipe.testsets.values() for test in testset.tests]
    with open(context.path.testcases_summary, "rt") as testcases_summary:
        available_testcases = [line.strip() for line in testcases_summary.readlines()]
    unavailable_testcases = [testcase for testcase in all_testcases if available_testcases.count(testcase) == 0]

    from internal.utils import ANSI_YELLOW, ANSI_RESET
    if len(unavailable_testcases):
        cprint(f"{ANSI_YELLOW}Warning: testcases {', '.join(unavailable_testcases)} were not available.{ANSI_RESET}\n")
    if is_apport_active():
        cprint(f"{ANSI_YELLOW}Warning: apport is active. Runtime error caused by signal might be treated as wall-clock limit exceeded due to apport crash collector delay.{ANSI_RESET}\n")

    codename_length = max(map(len, available_testcases)) + 2

    for testcases in available_testcases:
        cprint(' ' * 4 + testcases.ljust(codename_length))
        cprint("sol ")
        sol_result = solution_step.run_solution(testcases, False)
        cprint(format_exec_result(eval_result_to_exec_result(sol_result)))
        cprint(f" {sol_result.execution_time:.3f}  ")
        cprint("check ")
        # TODO: find actual argument to pass to checker
        testcase_input = os.path.join(context.path.testcases, context.construct_input_filename(testcases))
        testcase_answer = os.path.join(context.path.testcases, context.construct_output_filename(testcases))
        check_result = checker_step.run_checker([], sol_result, testcase_input, testcase_answer)
        # TODO: this following check is incorrect, see the actual function body for more information
        cprint(format_checker_result(check_result))
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

    context = init_tmt_root(str(pathlib.Path(__file__).parent.resolve()))

    if args.command == "gen":
        generate_testcases(context)
    elif args.command == "invoke":
        invoke_solution(context, remaining)
    elif args.command == "clean":
        # clean_testcases(root_dir)
        raise NotImplementedError(
            "The 'clean' command is not implemented yet."
        )


if __name__ == "__main__":
    main()
