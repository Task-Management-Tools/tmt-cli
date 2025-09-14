import os
import shutil

from internal.formatting import Formatter
from internal.context import CheckerType, TMTContext
from internal.steps.generation import GenerationStep
from internal.steps.validation import ValidationStep
from internal.steps.solution import make_solution_step
from internal.steps.checker.icpc import ICPCCheckerStep
from internal.steps.interactor import InteractorStep


def command_clean(*, formatter: Formatter, context: TMTContext, skip_confirm: bool):
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
        GenerationStep(context).clean_up()
        ValidationStep(context).clean_up()
        if (
            context.config.checker is not None
            and context.config.checker.type is not CheckerType.DEFAULT
        ):
            ICPCCheckerStep(context).clean_up()
        if context.config.interactor is not None:
            InteractorStep(context=context).clean_up()
        make_solution_step(
            solution_type=context.config.solution.type,
            context=context,
            is_generation=False,
            submission_files=[],
        ).clean_up()

    formatter.println("Cleanup completed.")
