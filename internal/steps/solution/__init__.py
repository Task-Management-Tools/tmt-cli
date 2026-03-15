from typing import Type

from .base import SolutionStep
from .batch import BatchSolutionStep
from .interactive import ICPCInteractiveSolutionStep
from .communication import CommunicationSolutionStep

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
                        str(problem_type)
                        + " in CMS is not supported by Communication task type."
                    )
                case JudgeConvention.TIOJ_OLD | JudgeConvention.TIOJ_NEW:
                    raise ValueError(
                        str(problem_type)
                        + " is not supported on TIOJ. Please set this problem in Batch and encrypt inputs and outputs."
                    )
        case ProblemType.COMMUNICATION:
            match judge_convention:
                case JudgeConvention.CMS:
                    return CommunicationSolutionStep
                case _:
                    raise ValueError(
                        str(problem_type) + " is not supported on ICPC/TIOJ."
                    )

        case _:
            raise ValueError(str(problem_type) + " is not supported yet.")


__all__ = [
    "SolutionStep",
    "make_solution_step",
]
