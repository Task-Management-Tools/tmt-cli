from .base import SolutionStep
from .batch import BatchSolutionStep

from internal.context import SolutionType


def make_solution_step(solution_type: SolutionType, *args, **kwargs) -> SolutionStep:
    match solution_type:
        case SolutionType.DEFAULT:
            return BatchSolutionStep(*args, **kwargs)
        case _:
            raise ValueError(str(problem_type) + " is not a valid problem type.")


__all__ = [
    "SolutionStep",
    "make_solution_step",
]
