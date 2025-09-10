import pathlib

from internal.formatting import Formatter
from internal.context import TMTContext
from internal.steps.generation import GenerationStep
from internal.steps.validation import ValidationStep
from internal.steps.solution import SolutionStep, make_solution_step
from internal.outcome import (
    CompilationOutcome,
    CompilationResult,
    GenerationResult,
    ExecutionOutcome,
)
from internal.commands import command_clean
from internal.commands.gen import gen_single


script_dir = pathlib.Path(__file__).parent.parent.resolve()
problem_dir = pathlib.Path(__file__).parent.resolve() / "aplusb"


def test_aplusb_gen():
    formatter = Formatter()
    context = TMTContext(str(problem_dir), str(script_dir))

    command_clean(formatter=formatter, context=context, skip_confirm=True)

    model_solution_full_path = context.path.replace_with_solution(
        context.config.model_solution_path
    )
    generation_step = GenerationStep(context)
    validation_step = ValidationStep(context)
    solution_step: SolutionStep = make_solution_step(
        problem_type=context.config.problem_type,
        context=context,
        is_generation=True,
        submission_files=[model_solution_full_path],
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

    def expected_result_helper(gen, val, ans):
        result = GenerationResult()
        result.input_generation = gen
        result.input_validation = val
        result.output_generation = ans
        return result

    OK = ExecutionOutcome.SUCCESS
    RTE = ExecutionOutcome.CRASHED
    FAIL = ExecutionOutcome.FAILED
    SKIP = ExecutionOutcome.SKIPPED
    TLE = ExecutionOutcome.TIMEDOUT

    # fmt: off
    expected_results = {
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
    # fmt: on

    # TODO assert that tests are sorted?
    for testset in context.recipe.testsets.values():
        for test in testset.tests:
            codename = test.test_name
            result = gen_single(
                formatter=formatter,
                context=context,
                codename_display_width=100,
                generation_step=generation_step,
                validation_step=validation_step,
                solution_step=solution_step,
                checker_step=None,
                show_reason=False,
                testset=testset,
                test=test,
            )
            expected_result = expected_results[codename]
            assert result.input_generation == expected_result.input_generation
            assert result.input_validation == expected_result.input_validation
            assert result.output_generation == expected_result.output_generation
