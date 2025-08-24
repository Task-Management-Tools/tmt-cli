import os
import platform
import subprocess

from pathlib import Path

from internal.context import TMTContext
from internal.runner import Process, wait_for_outputs
from internal.outcome import EvaluationResult, CompilationResult, CompilationOutcome


class MetaSolutionStep:
    def __init__(self):
        # TODO: the following passage does not make sense since I don't know how to setup virtual ctor properly
        
        # The reason of why the limits must be passed is because in testcase generation, the actual
        # "solution" run might not be the expected solution in contest: they could be slower or 
        # more precise solution to generate, for example, exact solution or a closer approximation.
        # This can occur in floating point problems, randomized problems (where the model solution 
        # might be slower because of derandomization), and approximation problems.
        pass

    def prepare_sandbox(self):
        pass

    def compile_solution(self) -> CompilationResult:
        pass

    def compile_interactor(self) -> CompilationResult:
        pass

    def compile_manager(self) -> CompilationResult:
        pass

    def run_solution(self, code_name: str, store_output: None | str) -> EvaluationResult:
        """
        Runs solution for input file code_name. If store_output is not None, then move the solution to store_output.
        Otherwise, keep the output in the sandbox and report the file in EvaluationResult.
        """
        raise NotImplementedError
