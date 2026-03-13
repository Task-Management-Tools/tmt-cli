from typing import Type
from .base import SolutionStep
from .batch import BatchSolutionStep
from .interactive import ICPCInteractiveSolutionStep

from internal.context import ProblemType, JudgeConvention


def make_solution_step_type(
    problem_type: ProblemType, judge_convention: JudgeConvention
) -> Type[SolutionStep]:
    match problem_type:
        case ProblemType.BATCH:
            return BatchSolutionStep
        case ProblemType.INTERACTIVE:
            match judge_convention:
                case JudgeConvention.ICPC:
                    return ICPCInteractiveSolutionStep
                case JudgeConvention.CMS:
                    raise ValueError(
                        str(problem_type) + " in CMS is not supported yet."
                    )
                case JudgeConvention.TIOJ_OLD | JudgeConvention.TIOJ_NEW:
                    raise ValueError(
                        str(problem_type)
                        + " is not supported on TIOJ. Please set this problem in Batch and encrypt inputs and outputs."
                    )

        case _:
            raise ValueError(str(problem_type) + " is not supported yet.")


__all__ = [
    "SolutionStep",
    "make_solution_step",
]
