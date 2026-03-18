from typing import Type

from .base import SolutionStep
from .batch import BatchSolutionStep
from .interactive import ICPCInteractiveSolutionStep
from .communication import CommunicationSolutionStep

from internal.context import ProblemType, JudgeConvention


def get_solution_step_type(
    problem_type: ProblemType, judge_convention: JudgeConvention
) -> Type[SolutionStep]:
    match (problem_type, judge_convention):
        case (ProblemType.BATCH, _):
            return BatchSolutionStep

        case (ProblemType.INTERACTIVE, JudgeConvention.ICPC):
            return ICPCInteractiveSolutionStep
        case (ProblemType.INTERACTIVE, JudgeConvention.CMS):
            raise ValueError(
                "Interactive task in CMS is supported by Communication task type."
            )
        case (ProblemType.INTERACTIVE, _):
            raise ValueError(
                f"Interactive task is not supported in {str(judge_convention)}"
            )

        case (ProblemType.COMMUNICATION, JudgeConvention.CMS):
            return CommunicationSolutionStep
        case (ProblemType.COMMUNICATION, _):
            raise ValueError(
                f"Communication task is not supported in {str(judge_convention)}"
            )

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
    "SolutionStep",
    "get_solution_step_type",
]
