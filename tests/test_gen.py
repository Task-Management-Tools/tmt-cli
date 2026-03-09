import os
import json
import hashlib
import pathlib
import pytest

from internal.formatting import EmptyFormatter
from internal.context import TMTContext, AnswerGenerationType, SandboxDirectory
from internal.formatting.terminal import TerminalFormatter
from internal.steps.generation import GenerationStep
from internal.steps.validation import ValidationStep
from internal.steps.solution import SolutionStep, make_solution_step
from internal.steps.interactor import ICPCInteractorStep
from internal.steps.checker.icpc import ICPCCheckerStep

from internal.outcomes import (
    CompilationOutcome,
    CompilationResult,
    GenerationResult,
    ExecutionOutcome,
)
from internal.commands import command_clean
from internal.commands.gen import command_gen, gen_single


def expected_result_helper(*, gen, val, ans, checker=ExecutionOutcome.UNKNOWN):
    result = GenerationResult()
    result.input_generation = gen
    result.input_validation = val
    result.output_generation = ans
    result.output_validation = checker
    return result


class ExpectedCompilation:
    def __init__(self, *, gen=False, val=False, sol=False, check=False, interact=False):
        self.gen = gen
        self.val = val
        self.sol = sol
        self.check = check
        self.interact = interact


OK = ExecutionOutcome.SUCCESS
RTE = ExecutionOutcome.CRASHED
FAIL = ExecutionOutcome.FAILED
SKIP = ExecutionOutcome.SKIPPED
SKIP_OK = ExecutionOutcome.SKIPPED_SUCCESS
TLE = ExecutionOutcome.TIMEDOUT

# fmt: off
expected_results_aplusb = (
    ExpectedCompilation(gen=True, val=True, sol=True),
    {
        "1_handmade_1":       expected_result_helper(gen=OK,   val=OK,   ans=OK),
        "1_handmade_2":       expected_result_helper(gen=OK,   val=OK,   ans=OK),
        "1_handmade_3":       expected_result_helper(gen=OK,   val=OK,   ans=OK),
        "1_handmade_4":       expected_result_helper(gen=OK,   val=FAIL, ans=SKIP),
        "1_handmade_5":       expected_result_helper(gen=OK,   val=OK,   ans=OK),
        "1_handmade_6":       expected_result_helper(gen=OK,   val=OK,   ans=OK),
        "2_with-proof_1":     expected_result_helper(gen=OK,   val=OK,   ans=OK),
        "3_bad-generators_1": expected_result_helper(gen=RTE,  val=SKIP, ans=SKIP),
        "3_bad-generators_2": expected_result_helper(gen=RTE,  val=SKIP, ans=SKIP),
        "3_bad-generators_3": expected_result_helper(gen=TLE,  val=SKIP, ans=SKIP),
        "3_bad-generators_4": expected_result_helper(gen=FAIL, val=SKIP, ans=SKIP),
    }
)

expected_results_floatcmp = (
    ExpectedCompilation(gen=True, val=True, sol=True, check=True),
    {
        "1_handmade_1":       expected_result_helper(gen=OK, val=OK, ans=OK),
    }
)

expected_results_guess = (
    ExpectedCompilation(gen=True, val=True, sol=True, interact=True),
    {
        "1_testset_1":        expected_result_helper(gen=OK, val=OK, ans=OK),
        "1_testset_2":        expected_result_helper(gen=OK, val=OK, ans=OK),
        "1_testset_3":        expected_result_helper(gen=OK, val=OK, ans=OK),
        "1_testset_4":        expected_result_helper(gen=OK, val=OK, ans=OK),
    }
)

expected_results_parity = (
    ExpectedCompilation(gen=True, val=True, sol=True, check=True),
    {
        "1_handmade_1":               expected_result_helper(gen=OK, val=OK, ans=OK,      checker=OK),
        "1_handmade_2":               expected_result_helper(gen=OK, val=OK, ans=OK,      checker=OK),
        "2_override_1":               expected_result_helper(gen=OK, val=OK, ans=SKIP_OK, checker=OK),
        "3_override-wrong-answer_1":  expected_result_helper(gen=OK, val=OK, ans=SKIP_OK, checker=FAIL),
    }
)

expected_results_aplusb_py = (
    ExpectedCompilation(gen=True, val=True, sol=True),
    {
        "1_handmade_1":       expected_result_helper(gen=OK,   val=OK,   ans=OK),
        "1_handmade_2":       expected_result_helper(gen=OK,   val=OK,   ans=OK),
        "1_handmade_3":       expected_result_helper(gen=OK,   val=OK,   ans=OK),
        "1_handmade_4":       expected_result_helper(gen=OK,   val=FAIL, ans=SKIP),
        "1_handmade_5":       expected_result_helper(gen=OK,   val=OK,   ans=OK),
        "1_handmade_6":       expected_result_helper(gen=OK,   val=OK,   ans=OK)
    }
)
# fmt: on


@pytest.mark.parametrize(
    "problem_path, expected_results",
    [
        ("aplusb", expected_results_aplusb),
        ("aplusb-py", expected_results_aplusb_py),
        ("floatcmp", expected_results_floatcmp),
        ("guess", expected_results_guess),
        ("parity", expected_results_parity),
    ],
)
def test_gen(
    problem_path: str,
    expected_results: tuple[ExpectedCompilation, dict[str, GenerationResult]],
):
    script_dir = pathlib.Path(__file__).parent.parent.resolve()
    problem_dir = pathlib.Path(__file__).parent.resolve() / problem_path
    formatter = TerminalFormatter()
    context = TMTContext(str(problem_dir), str(script_dir))

    command_clean(formatter=formatter, context=context, skip_confirm=True)
    command_result = command_gen(
        formatter=formatter, context=context, verify_hash=False, show_reason=False
    )

    expected_compilation, expected_generation = expected_results

    # Check for compilation
    def check_compilation(expected: bool, found: CompilationResult | None):
        if expected:
            assert isinstance(found, CompilationResult)
            assert found.verdict == CompilationOutcome.SUCCESS
        else:
            assert found is None

    check_compilation(expected_compilation.gen, command_result.generation_compilation)
    check_compilation(expected_compilation.val, command_result.validation_compilation)
    check_compilation(expected_compilation.sol, command_result.solution_compilation)
    check_compilation(expected_compilation.check, command_result.checker_compilation)
    check_compilation(
        expected_compilation.interact, command_result.interactor_compilation
    )

    for testset in context.recipe.testsets.values():
        for test in testset.tests:
            codename = test.test_name
            assert codename is not None
            assert codename in command_result.testcase_results

            result = command_result.testcase_results[codename]
            expected_result = expected_generation[codename]

            assert result.input_generation == expected_result.input_generation
            assert result.input_validation == expected_result.input_validation
            assert result.output_generation == expected_result.output_generation
            if expected_result.output_validation is not ExecutionOutcome.UNKNOWN:
                assert result.output_validation == expected_result.output_validation

            # Verifies hash
            if result:
                for testcase_file_exts in [
                    context.config.input_extension,
                    context.config.output_extension,
                ] + list(testset.extra_file):
                    base_filename = context.construct_test_filename(
                        codename, testcase_file_exts
                    )
                    file = os.path.join(context.path.testcases, base_filename)
                    assert os.path.isfile(file)
                    with open(file, "rb") as f:
                        testcase_hash = hashlib.sha256(f.read()).hexdigest()
                    assert (
                        command_result.testcase_hashes[base_filename] == testcase_hash
                    )

    # TODO assert that tests are sorted in summary file?
