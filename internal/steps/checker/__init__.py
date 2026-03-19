from typing import Type

from .base import CheckerStep
from .icpc import ICPCCheckerStep
from .cms import CMSCheckerStep

from internal.context import ProblemType, JudgeConvention


def get_checker_step_type(
    problem_type: ProblemType, judge_convention: JudgeConvention
) -> Type[CheckerStep] | None:
    match (problem_type, judge_convention):
        case (ProblemType.BATCH, JudgeConvention.ICPC):
            return ICPCCheckerStep
        case (ProblemType.BATCH, JudgeConvention.CMS):
            return CMSCheckerStep
        case (ProblemType.INTERACTIVE, JudgeConvention.ICPC):
            return None
        case (ProblemType.COMMUNICATION, JudgeConvention.CMS):
            return None
        case (ProblemType.OUTPUT_ONLY, JudgeConvention.CMS):
            return CMSCheckerStep
        case (_, JudgeConvention.TIOJ_OLD) | (_, JudgeConvention.TIOJ_NEW):
            raise ValueError(str(judge_convention) + " is not supported yet.")
        case _:
            raise ValueError(
                str(problem_type)
                + " with "
                + str(judge_convention)
                + " is not supported yet."
            )


__all__ = [
    "CheckerStep",
    "get_checker_step_type",
]
