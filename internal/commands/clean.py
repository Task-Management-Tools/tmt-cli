import os
import shutil

from internal.formatting import Formatter
from internal.context import TMTContext
from internal.steps.generation import GenerationStep
from internal.steps.validation import ValidationStep
from internal.steps.solution import get_solution_step_type
from internal.steps.checker import get_checker_step_type


def command_clean(*, formatter: Formatter, context: TMTContext, skip_confirm: bool):
    context.log_directory = None

    def confirm(message: str) -> bool:
        if skip_confirm:
            formatter.println(message + ".")
            return True

        formatter.print(message + "? [Y/n] ")
        while True:
            yesno = input().strip().lower()
            if yesno in ["y", "yes"]:
                return True
            if yesno in ["n", "no"]:
                return False
            formatter.print("Please answer yes or no. [Y/n] ")

    if confirm("Cleanup logs and sandbox"):
        if os.path.exists(context.path.logs):
            shutil.rmtree(context.path.logs)
        if os.path.exists(context.path.sandbox):
            shutil.rmtree(context.path.sandbox)

    if confirm("Cleanup testcases"):
        context.path.clean_testcases()
    # TODO: clean statement?

    if confirm("Cleanup compiled generators, validators and solutions"):
        GenerationStep(context=context, sandbox=None).clean_up()
        ValidationStep(context=context, sandbox=None).clean_up()

        solution_step_type = get_solution_step_type(
            problem_type=context.config.problem_type,
            judge_convention=context.config.judge_convention,
        )
        solution_step_type(
            context=context,
            sandbox=None,
            is_generation=False,
            submission_files=[],
        ).clean_up()

        checker_step_type = get_checker_step_type(
            problem_type=context.config.problem_type,
            judge_convention=context.config.judge_convention,
        )
        if checker_step_type is not None:
            checker_step_type(
                context=context, sandbox=None, is_generation=False
            ).clean_up()

    public_zip_path = os.path.join(
        context.path.public, context.config.short_name + ".zip"
    )
    if os.path.exists(public_zip_path) and confirm("Cleanup generated attachment"):
        os.remove(public_zip_path)

    # TODO: clean statement?

    formatter.println("Cleanup completed.")
