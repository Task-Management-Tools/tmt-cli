import pathlib
import pytest

from internal.formatting import Formatter
from internal.context import TMTContext, AnswerGenerationType
from internal.steps.generation import GenerationStep
from internal.steps.validation import ValidationStep
from internal.steps.solution import SolutionStep, make_solution_step
from internal.steps.interactor import InteractorStep
from internal.steps.checker.icpc import ICPCCheckerStep

from internal.outcome import (
    CompilationOutcome,
    CompilationResult,
    GenerationResult,
    ExecutionOutcome,
)
from internal.commands import command_clean
from internal.commands.gen import gen_single


def expected_result_helper(*, gen, val, ans, checker=ExecutionOutcome.UNKNOWN):
    result = GenerationResult()
    result.input_generation = gen
    result.input_validation = val
    result.output_generation = ans
    result.output_validation = checker
    return result


OK = ExecutionOutcome.SUCCESS
RTE = ExecutionOutcome.CRASHED
FAIL = ExecutionOutcome.FAILED
SKIP = ExecutionOutcome.SKIPPED
SKIP_OK = ExecutionOutcome.SKIPPED_SUCCESS
TLE = ExecutionOutcome.TIMEDOUT

# fmt: off
expected_results_aplusb = {
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

expected_results_floatcmp = {
    "1_handmade_1":       expected_result_helper(gen=OK, val=OK, ans=OK),
}

expected_results_guess = {
    "1_testset_1":        expected_result_helper(gen=OK, val=OK, ans=OK),
    "1_testset_2":        expected_result_helper(gen=OK, val=OK, ans=OK),
    "1_testset_3":        expected_result_helper(gen=OK, val=OK, ans=OK),
    "1_testset_4":        expected_result_helper(gen=OK, val=OK, ans=OK),
}

expected_results_parity = {
    "1_handmade_1":               expected_result_helper(gen=OK, val=OK, ans=OK,      checker=OK),
    "1_handmade_2":               expected_result_helper(gen=OK, val=OK, ans=OK,      checker=OK),
    "2_override_1":               expected_result_helper(gen=OK, val=OK, ans=SKIP_OK, checker=OK),
    "3_override-wrong-answer_1":  expected_result_helper(gen=OK, val=OK, ans=SKIP_OK, checker=FAIL),
}

expected_results_aplusb_py = {
    "1_handmade_1":       expected_result_helper(gen=OK,   val=OK,   ans=OK),
    "1_handmade_2":       expected_result_helper(gen=OK,   val=OK,   ans=OK),
    "1_handmade_3":       expected_result_helper(gen=OK,   val=OK,   ans=OK),
    "1_handmade_4":       expected_result_helper(gen=OK,   val=FAIL, ans=SKIP),
    "1_handmade_5":       expected_result_helper(gen=OK,   val=OK,   ans=OK),
    "1_handmade_6":       expected_result_helper(gen=OK,   val=OK,   ans=OK)
}
# fmt: on


@pytest.mark.parametrize(
    "problem_shortname, expected_results",
    [
        ("aplusb", expected_results_aplusb),
        ("aplusb-py", expected_results_aplusb_py),
        ("floatcmp", expected_results_floatcmp),
        ("guess", expected_results_guess),
        ("parity", expected_results_parity),
    ],
)
def test_gen(problem_shortname: str, expected_results: dict[str, GenerationResult]):
    script_dir = pathlib.Path(__file__).parent.parent.resolve()
    problem_dir = pathlib.Path(__file__).parent.resolve() / problem_shortname
    formatter = Formatter()
    context = TMTContext(str(problem_dir), str(script_dir))

    command_clean(formatter=formatter, context=context, skip_confirm=True)

    generation_step = GenerationStep(context)
    validation_step = ValidationStep(context)
    assert context.config.answer_generation.type is AnswerGenerationType.SOLUTION
    solution_step: SolutionStep = make_solution_step(
        solution_type=context.config.solution.type,
        context=context,
        is_generation=True,
        submission_files=[context.config.answer_generation.filename],
    )

    generation_step.prepare_sandbox()
    generation_compile_result: CompilationResult = generation_step.compile()
    assert generation_compile_result.verdict == CompilationOutcome.SUCCESS

    validation_step.prepare_sandbox()
    validation_compile_result: CompilationResult = validation_step.compile()
    assert validation_compile_result.verdict == CompilationOutcome.SUCCESS

    solution_step.prepare_sandbox()
    solution_compile_result: CompilationResult = solution_step.compile_solution()
    assert solution_compile_result.verdict == CompilationOutcome.SUCCESS

    checker_step = None
    if context.config.checker is not None:
        checker_step = ICPCCheckerStep(context)
        checker_step.prepare_sandbox()
        checker_compile_result: CompilationResult = checker_step.compile()
        assert checker_compile_result.verdict == CompilationOutcome.SUCCESS

    interactor_step = None
    if context.config.interactor is not None:
        interactor_step = InteractorStep(context=context)
        interactor_step.prepare_sandbox()
        interactor_compile_result: CompilationResult = interactor_step.compile()
        assert interactor_compile_result.verdict == CompilationOutcome.SUCCESS

    # TODO assert that tests are sorted?
    for testset in context.recipe.testsets.values():
        for test in testset.tests:
            codename = test.test_name
            assert codename is not None
            result = gen_single(
                formatter=formatter,
                codename_display_width=100,
                generation_step=generation_step,
                validation_step=validation_step,
                solution_step=solution_step,
                checker_step=checker_step,
                interactor_step=interactor_step,
                show_reason=False,
                testset=testset,
                test=test,
            )
            expected_result = expected_results[codename]
            assert result.input_generation == expected_result.input_generation
            assert result.input_validation == expected_result.input_validation
            assert result.output_generation == expected_result.output_generation
            if expected_result.output_validation is not ExecutionOutcome.UNKNOWN:
                assert result.output_validation == expected_result.output_validation
