import argparse
import pathlib
import os
import shutil
import yaml

from internal.recipe_parser import parse_contest_data
from internal.utils import is_apport_active
from internal.formatting import Formatter
from internal.config import CheckerType, ProblemType, TMTConfig
from internal.context import TMTContext
from internal.paths import ProblemDirectoryHelper
from internal.step_generation import GenerationStep
from internal.step_validation import ValidationStep
from internal.outcome import EvaluationResult, ExecutionOutcome, eval_outcome_to_grade_outcome, eval_outcome_to_run_outcome
from internal.step_checker_icpc import ICPCCheckerStep


def init_tmt_root(script_root: str) -> TMTContext:
    """Initialize the root directory of tmt tasks."""

    context = TMTContext()

    tmt_root = pathlib.Path.cwd()
    while tmt_root != tmt_root.parent:
        if (tmt_root / ProblemDirectoryHelper.PROBLEM_YAML).exists():
            context.path = ProblemDirectoryHelper(str(tmt_root), script_root)
            with open(context.path.tmt_config, 'r') as file:
                problem_yaml = yaml.safe_load(file)
                context.config = TMTConfig(problem_yaml)
            return context
        tmt_root = tmt_root.parent

    raise FileNotFoundError(2,
                            f"No tmt root found in the directory hierarchy"
                            f"The directory must contain a {ProblemDirectoryHelper.PROBLEM_YAML} file.",
                            ProblemDirectoryHelper.PROBLEM_YAML)


def command_init(root_dir: pathlib.Path):
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


def command_gen(context: TMTContext, args):
    """Generate test cases in the given directory."""
    formatter = Formatter()

    # Compile generators, validators and solutions
    generation_step = GenerationStep(context)
    validation_step = ValidationStep(context)
    run_checker = (context.config.problem_type is ProblemType.BATCH and context.config.checker_type is not CheckerType.DEFAULT
                   and (context.config.check_forced_output or context.config.check_generated_output))
    if run_checker:
        checker_step = ICPCCheckerStep(context)

    model_solution_full_path = context.path.replace_with_solution(context.config.model_solution_path)
    solution_step = context.config.get_solution_step()(context=context,
                                                       is_generation=True,
                                                       submission_files=[model_solution_full_path])

    context.path.clean_logs()
    os.makedirs(context.path.logs)
    os.makedirs(context.path.logs_generation, exist_ok=True)

    formatter.print("Generator   compile ")
    generation_step.prepare_sandbox()
    generation_compilation = generation_step.compile()
    formatter.print_compile_string_with_exit(generation_compilation)

    formatter.print("Validator   compile ")
    validation_step.prepare_sandbox()
    validation_compilation = validation_step.compile()
    formatter.print_compile_string_with_exit(validation_compilation)

    formatter.print("Solution    compile ")
    solution_step.prepare_sandbox()
    formatter.print_compile_string_with_exit(solution_step.compile_solution())

    if solution_step.has_interactor():
        formatter.print("Interactor  compile ")
        formatter.print_compile_string_with_exit(solution_step.compile_interactor())

    if solution_step.has_manager():
        formatter.print("Manager     compile ")
        formatter.print_compile_string_with_exit(solution_step.compile_manager())

    if run_checker:
        formatter.print("Checker     compile ")
        checker_step.prepare_sandbox()
        formatter.print_compile_string_with_exit(checker_step.compile())

    recipe = parse_contest_data(open(context.path.tmt_recipe).readlines())

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
    context.path.clean_testcases()
    os.makedirs(context.path.testcases)
    pathlib.Path(context.path.testcases_summary).touch()

    codename_length = max(map(len, validations.keys())) + 2

    with open(context.path.testcases_summary, "wt") as testcases_summary:
        for testset in recipe.testsets.values():
            for test in testset.tests:
                code_name = test.test_name

                formatter.print(' ' * 4)
                formatter.print_fixed_width(code_name, width=codename_length)

                # Run generator
                formatter.print("gen ")
                result = generation_step.run_generator(test.commands, code_name, list(testset.extra_file))
                formatter.print_exec_result(result.input_generation)

                # Run validator: skip if input_generation did not succeed
                formatter.print("val ")
                if result.input_generation is not ExecutionOutcome.SUCCESS:
                    result.input_validation = ExecutionOutcome.SKIPPED
                else:
                    validation_step.run_validator(result, validations[code_name], code_name, list(testset.extra_file))
                formatter.print_exec_result(result.input_validation)

                # Run solution: 
                # skip (and fail) if input validation did not succeed
                # skip if generator already produced output
                formatter.print("ans ")
                if result.input_validation is not ExecutionOutcome.SUCCESS:
                    result.output_generation = ExecutionOutcome.SKIPPED
                elif result.output_generation is ExecutionOutcome.SKIPPED_SUCCESS:
                    pass
                else:
                    solution_result = solution_step.run_solution(code_name)
                    result.output_generation = eval_outcome_to_run_outcome(solution_result)
                    result.reason = solution_result.checker_reason
                formatter.print_exec_result(result.output_generation)
                
                # Run checker
                # If both input is validated and output is available, run checker if the testcase type should apply check
                if run_checker:
                    formatter.print("val ")
                    if (result.output_generation not in [ExecutionOutcome.SUCCESS, ExecutionOutcome.SKIPPED_SUCCESS] or
                            result.input_validation not in [ExecutionOutcome.SUCCESS, ExecutionOutcome.SKIPPED_SUCCESS]):
                        result.output_validation = ExecutionOutcome.SKIPPED
                    elif ((result.is_output_forced and not context.config.check_forced_output) or
                          (not result.is_output_forced and not context.config.check_generated_output)):
                        result.output_validation = ExecutionOutcome.SKIPPED_SUCCESS
                    else:
                        testcase_input = os.path.join(context.path.testcases, context.construct_input_filename(code_name))
                        testcase_answer = os.path.join(context.path.testcases, context.construct_output_filename(code_name))
                        
                        copied_testcase_output = os.path.join(context.path.sandbox_checker, os.path.basename(testcase_answer))
                        shutil.copy(testcase_answer, copied_testcase_output)
                        
                        checker_result = checker_step.run_checker(context.config.checker_arguments, 
                                                                  EvaluationResult(
                                                                      output_file=copied_testcase_output
                                                                  ), testcase_input, testcase_answer)
                        result.output_validation = eval_outcome_to_grade_outcome(checker_result)
                        result.reason = checker_result.checker_reason
                    formatter.print_exec_result(result.output_validation)
                else:
                    result.output_validation = ExecutionOutcome.SKIPPED_SUCCESS

                if args.show_reason:
                    formatter.print_reason(result.reason)
                formatter.println()

                with open(os.path.join(context.path.logs_generation, f"{code_name}.gen.log"), "w+") as f:
                    f.write(result.reason)
                # TODO: this should print more meaningful contents, right now it is only the testcases
                if result:
                    testcases_summary.write(f"{code_name}\n")


def command_invoke(context: TMTContext, args):

    formatter = Formatter()
    actual_files = [os.path.join(os.getcwd(), file) for file in args.submission_files]

    if pathlib.Path(context.path.testcases_summary).exists():
        solution_step = context.config.get_solution_step()(context=context,
                                                           is_generation=False,
                                                           submission_files=actual_files)
        checker_step = ICPCCheckerStep(context)

        formatter.print("Solution    compile ")
        solution_step.prepare_sandbox()
        formatter.print_compile_string_with_exit(solution_step.compile_solution())

        if solution_step.has_interactor():
            formatter.print("Interactor  compile ")
            formatter.print_compile_string_with_exit(solution_step.compile_interactor())

        if solution_step.has_manager():
            formatter.print("Manager     compile ")
            formatter.print_compile_string_with_exit(solution_step.compile_manager())

        if not solution_step.skip_checker():
            formatter.print("Checker     compile ")
            checker_step.prepare_sandbox()
            formatter.print_compile_string_with_exit(checker_step.compile())
            if context.path.has_checker_directory() and context.config.checker_type is CheckerType.DEFAULT:
                formatter.println(formatter.ANSI_YELLOW,
                                  "Warning: Directory 'checker' exists but it is not used by this problem. Check problem.yaml or remove the directory.",
                                  formatter.ANSI_RESET)

    recipe = parse_contest_data(open(context.path.tmt_recipe).readlines())
    all_testcases = [test.test_name for testset in recipe.testsets.values() for test in testset.tests]
    with open(context.path.testcases_summary, "rt") as testcases_summary:
        available_testcases = [line.strip() for line in testcases_summary.readlines()]
    unavailable_testcases = [testcase for testcase in all_testcases if available_testcases.count(testcase) == 0]

    if len(unavailable_testcases):
        formatter.println(formatter.ANSI_YELLOW,
                          "Warning: testcases ", ', '.join(unavailable_testcases), " were not available.",
                          formatter.ANSI_RESET)
    if is_apport_active():
        formatter.println(
            formatter.ANSI_YELLOW,
            "Warning: apport is active. Runtime error caused by signal might be treated as wall-clock limit exceeded due to apport crash collector delay.",
            formatter.ANSI_RESET)

    codename_length = max(map(len, available_testcases)) + 2

    for testcase in available_testcases:
        formatter.print(' ' * 4)
        formatter.print_fixed_width(testcase, width=codename_length)

        formatter.print("sol ")
        solution_result = solution_step.run_solution(testcase)
        formatter.print_exec_result(eval_outcome_to_run_outcome(solution_result))
        formatter.print(f"{solution_result.solution_cpu_time_sec:6.3f} s / {solution_result.solution_max_memory_kib / 1024:5.4g} MiB  ")
        with open(os.path.join(context.path.logs_invocation, f"{testcase}.sol.log"), "w+") as f:
            f.write(solution_result.checker_reason)

        if not solution_step.skip_checker():
            formatter.print("check ")
            testcase_input = os.path.join(context.path.testcases, context.construct_input_filename(testcase))
            testcase_answer = os.path.join(context.path.testcases, context.construct_output_filename(testcase))
            solution_result = checker_step.run_checker(context.config.checker_arguments, solution_result, testcase_input, testcase_answer)
            formatter.print_checker_status(solution_result)

        formatter.print_checker_verdict(solution_result, print_reason=args.show_reason)
        formatter.println()

        if solution_result.output_file is not None:
            os.unlink(solution_result.output_file)


def main():
    parser = argparse.ArgumentParser(description="TMT - Task Management Tools")
    parser.add_argument(
        "--version", action="version", version="TMT 0.0.0",
        help="Show the version of TMT."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    parser_init = subparsers.add_parser("init", help="Init a TMT problem directory.")

    parser_gen = subparsers.add_parser("gen", help="Generate testcases.")
    parser_gen.add_argument("-r", "--show-reason", 
                            action="store_true", 
                            help="Show the failed reason and checker's output (in case of checker validation is enabled) of each testcase.")

    parser_invoke = subparsers.add_parser("invoke", help="Invoke a solution.")
    parser_invoke.add_argument("-r", "--show-reason", action="store_true")
    parser_invoke.add_argument('submission_files', nargs='*')

    parser_clean = subparsers.add_parser("clean", help="Clean-up a TMT problem directory.")

    args = parser.parse_args()

    if args.command == "init":
        command_init(pathlib.Path.cwd())
        return

    context = init_tmt_root(str(pathlib.Path(__file__).parent.resolve()))

    if args.command == "gen":
        command_gen(context, args)
        return 
    
    if args.command == "invoke":
        command_invoke(context, args)
        return 
    
    if args.command == "clean":
        # clean_testcases(root_dir)
        raise NotImplementedError(
            "The 'clean' command is not implemented yet."
        )


if __name__ == "__main__":
    main()
