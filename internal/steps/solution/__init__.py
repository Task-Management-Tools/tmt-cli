from .base import SolutionStep
from .batch import BatchSolutionStep
from .interactive_icpc import InteractiveICPCSolutionStep

from internal.context import ProblemType


def make_solution_step(problem_type: ProblemType, *args, **kwargs) -> SolutionStep:
    match problem_type:
        case ProblemType.BATCH:
            return BatchSolutionStep(*args, **kwargs)
        case ProblemType.INTERACTIVE:
            return InteractiveICPCSolutionStep(*args, **kwargs)
        case _:
            raise ValueError(str(problem_type) + " is not a valid problem type.")


__all__ = [
    "SolutionStep",
    "make_solution_step",
]
