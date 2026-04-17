from dataclasses import dataclass
import os
import hashlib
import pathlib
import pytest

from internal.context import TMTContext
from internal.formatting.terminal import TerminalFormatter

from internal.outcomes import (
    CompilationOutcome,
    CompilationResult,
    GenerationResult,
    ExecutionOutcome,
)
from internal.commands import command_clean
from internal.commands.gen import command_gen
from internal.steps.utils import CompilationSlot


def expected_result_helper(*, gen, val, ans, checker=ExecutionOutcome.UNKNOWN):
    result = GenerationResult()
    result.input_generation = gen
    result.input_validation = val
    result.output_generation = ans
    result.output_validation = checker
    return result


@dataclass(kw_only=True)
class ExpectedCompilation:
    gen: bool = False
    val: bool = False
    sol: bool = False
    check: bool = False
    interact: bool = False
    manager: bool = False


OK = ExecutionOutcome.SUCCESS
RTE = ExecutionOutcome.CRASHED
FAIL = ExecutionOutcome.FAILED
SKIP = ExecutionOutcome.SKIPPED
SKIP_OK = ExecutionOutcome.SKIPPED_SUCCESS
TLE = ExecutionOutcome.TIMEDOUT

# fmt: off
expected_results_batch_no_testdata = (
    ExpectedCompilation(gen=True, val=True, sol=True), {}
)

expected_results_batch_cms_checker = (
    ExpectedCompilation(gen=True, val=True, sol=True, check=True),
    { "1-full-1": expected_result_helper(gen=OK,   val=OK,   ans=OK,   checker=OK), }
)

expected_results_batch_cms_whitediff = (
    ExpectedCompilation(gen=True, val=True, sol=True),
    { "1-full-1": expected_result_helper(gen=OK,   val=OK,   ans=OK), }
)

expected_results_batch_cms_grader = (
    ExpectedCompilation(gen=True, val=True, sol=True),
    { "1-full-1": expected_result_helper(gen=OK,   val=OK,   ans=OK), }
)

expected_results_batch_icpc_checker = (
    ExpectedCompilation(gen=True, val=True, sol=True, check=True),
    {
        "1-input-1":        expected_result_helper(gen=OK, val=OK, ans=OK,      checker=OK),
        "2-override-1":     expected_result_helper(gen=OK, val=OK, ans=SKIP_OK, checker=OK),
        "3-bad-override-1": expected_result_helper(gen=OK, val=OK, ans=SKIP_OK, checker=FAIL),
    }
)

expected_results_batch_icpc_floatcmp = (
    ExpectedCompilation(gen=True, val=True, sol=True),
    {
        "1-full-1":        expected_result_helper(gen=OK, val=OK, ans=OK),
    }
)

expected_results_batch_icpc_generator = (
    ExpectedCompilation(gen=True, val=True, sol=True),
    {
        "1-good-1":  expected_result_helper(gen=OK,   val=OK,   ans=OK),
        "1-good-2":  expected_result_helper(gen=OK,   val=OK,   ans=OK),
        "1-good-3":  expected_result_helper(gen=OK,   val=OK,   ans=OK),
        "1-good-4":  expected_result_helper(gen=OK,   val=OK,   ans=OK),
        "1-good-5":  expected_result_helper(gen=OK,   val=OK,   ans=OK),
        "1-good-6":  expected_result_helper(gen=OK,   val=OK,   ans=OK),
        "2-proof-1": expected_result_helper(gen=OK,   val=OK,   ans=OK),
        "3-bad-1":   expected_result_helper(gen=OK,   val=FAIL, ans=SKIP),
        "3-bad-2":   expected_result_helper(gen=OK,   val=FAIL, ans=SKIP),
        "3-bad-3":   expected_result_helper(gen=RTE,  val=SKIP, ans=SKIP),
        "3-bad-4":   expected_result_helper(gen=RTE,  val=SKIP, ans=SKIP),
        "3-bad-5":   expected_result_helper(gen=TLE,  val=SKIP, ans=SKIP),
        "3-bad-6":   expected_result_helper(gen=FAIL, val=SKIP, ans=SKIP),
        "3-bad-7":   expected_result_helper(gen=RTE,  val=SKIP, ans=SKIP),
    }
)

expected_results_batch_icpc_validator = (
    ExpectedCompilation(gen=True, val=True, sol=True),
    {
        "1-normal-1":  expected_result_helper(gen=OK,   val=OK,   ans=OK),
        "1-normal-2":  expected_result_helper(gen=OK,   val=FAIL, ans=SKIP),
        "1-normal-3":  expected_result_helper(gen=OK,   val=RTE,  ans=SKIP),
        "1-normal-4":  expected_result_helper(gen=OK,   val=TLE,  ans=SKIP),
        "1-normal-5":  expected_result_helper(gen=OK,   val=OK,   ans=OK),
        "2-proof-1":   expected_result_helper(gen=OK,   val=OK,   ans=OK),
    }
)

expected_results_interactive_guess = (
    ExpectedCompilation(gen=True, val=True, sol=True, interact=True),
    {
        "1-full-1":        expected_result_helper(gen=OK, val=OK, ans=OK),
        "1-full-2":        expected_result_helper(gen=OK, val=OK, ans=OK),
        "1-full-3":        expected_result_helper(gen=OK, val=OK, ans=OK),
        "1-full-4":        expected_result_helper(gen=OK, val=OK, ans=OK),
    }
)

expected_results_communication_general = (
    ExpectedCompilation(gen=True, val=True, manager=True, sol=True),
    { "1-full-1": expected_result_helper(gen=OK,   val=OK,   ans=OK), }
)

expected_results_outputonly_basic = (
    ExpectedCompilation(gen=True, val=True, sol=True, check=True),
    {
        "0": expected_result_helper(gen=OK,   val=OK,   ans=OK),
        "1": expected_result_helper(gen=OK,   val=OK,   ans=OK),
        "2": expected_result_helper(gen=OK,   val=OK,   ans=OK),
        "3": expected_result_helper(gen=OK,   val=OK,   ans=OK),
        "4": expected_result_helper(gen=OK,   val=OK,   ans=OK),
        "5": expected_result_helper(gen=OK,   val=OK,   ans=OK),
    }
)

@pytest.mark.parametrize(
    "problem_path, expected_results",
    [
        ("problems/batch/no-testdata", expected_results_batch_no_testdata),
        ("problems/batch/cms-checker", expected_results_batch_cms_checker),
        ("problems/batch/cms-grader", expected_results_batch_cms_grader),
        ("problems/batch/cms-whitediff", expected_results_batch_cms_whitediff),
        ("problems/batch/icpc-checker", expected_results_batch_icpc_checker),
        ("problems/batch/icpc-default-floatcmp", expected_results_batch_icpc_floatcmp),
        ("problems/batch/icpc-generator", expected_results_batch_icpc_generator),
        ("problems/batch/icpc-validator", expected_results_batch_icpc_validator),
        ("problems/interactive/guess", expected_results_interactive_guess),
        ("problems/communication/1-proc-grader-fifo", expected_results_communication_general),
        ("problems/communication/1-proc-grader-stdio", expected_results_communication_general),
        ("problems/communication/2-proc-grader-fifo", expected_results_communication_general),
        ("problems/communication/2-proc-grader-stdio", expected_results_communication_general),
        ("problems/outputonly/basic", expected_results_outputonly_basic),
    ],
)
# fmt: on
def test_gen(
    problem_path: str,
    expected_results: tuple[ExpectedCompilation, dict[str, GenerationResult]],
):
    script_dir = pathlib.Path(__file__).parent.parent.resolve()
    problem_dir = pathlib.Path(__file__).parent.resolve() / problem_path
    formatter = TerminalFormatter()
    context = TMTContext(str(problem_dir), str(script_dir))

    # Force shorter trusted step time to speed up unit test
    # TODO document this
    context.config.trusted_step_time_limit_sec = 1.0

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

    compilation_result = command_result.compilation_result
    check_compilation(
        expected_compilation.gen, compilation_result.get(CompilationSlot.GENERATOR)
    )
    check_compilation(
        expected_compilation.val, compilation_result.get(CompilationSlot.VALIDATOR)
    )
    check_compilation(
        expected_compilation.sol, compilation_result.get(CompilationSlot.SOLUTION)
    )
    check_compilation(
        expected_compilation.check, compilation_result.get(CompilationSlot.CHECKER)
    )
    check_compilation(
        expected_compilation.interact,
        compilation_result.get(CompilationSlot.INTERACTOR),
    )
    check_compilation(
        expected_compilation.manager, compilation_result.get(CompilationSlot.MANAGER)
    )

    for testset in context.recipe.testsets.values():
        for test in testset.testcases:
            codename = test.name
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
