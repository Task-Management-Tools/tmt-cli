import pathlib
import pytest

from internal.context import TMTContext
from internal.formatting.terminal import TerminalFormatter
from internal.commands import command_clean, command_gen
from internal.commands.verify import command_verify, command_verify_config, command_verify_verdicts
from internal.verify.verifier import TMTVerifyIssueType

@pytest.mark.parametrize(
    "problem_path, expected_error_count, expected_warning_count",
    [
        ("problems/verify", 1, 0),
    ],
)
def test_verify_config(
    problem_path: str,
    expected_error_count: int,
    expected_warning_count: int,
):
    script_dir = pathlib.Path(__file__).parent.parent.resolve()
    problem_dir = pathlib.Path(__file__).parent.resolve() / problem_path
    formatter = TerminalFormatter()
    context = TMTContext(str(problem_dir), str(script_dir))

    # Force shorter trusted step time to speed up unit test
    context.config.trusted_step_time_limit_sec = 1.0

    command_clean(formatter=formatter, context=context, skip_confirm=True)
    command_gen(
        formatter=formatter, context=context, verify_hash=False, show_reason=False
    )
    
    issues = command_verify_config(print_issues=False, 
                                   formatter=formatter, 
                                   context=context)
    
    error_count = sum(1 for issue in issues if issue.type == TMTVerifyIssueType.ERROR)
    warning_count = sum(1 for issue in issues if issue.type == TMTVerifyIssueType.WARNING)
    
    assert error_count == expected_error_count, f"Expected {expected_error_count} errors, found {error_count}: {[i.message for i in issues if i.type == TMTVerifyIssueType.ERROR]}"
    assert warning_count == expected_warning_count, f"Expected {expected_warning_count} warnings, found {warning_count}: {[i.message for i in issues if i.type == TMTVerifyIssueType.WARNING]}"

@pytest.mark.parametrize(
    "problem_path, expected_error_count, expected_warning_count",
    [
        ("problems/verify", 4, 1),
    ],
)
def test_verify_verdicts(
    problem_path: str,
    expected_error_count: int,
    expected_warning_count: int,
):
    script_dir = pathlib.Path(__file__).parent.parent.resolve()
    problem_dir = pathlib.Path(__file__).parent.resolve() / problem_path
    formatter = TerminalFormatter()
    context = TMTContext(str(problem_dir), str(script_dir))

    # Force shorter trusted step time to speed up unit test
    context.config.trusted_step_time_limit_sec = 1.0

    command_clean(formatter=formatter, context=context, skip_confirm=True)
    command_gen(
        formatter=formatter, context=context, verify_hash=False, show_reason=False
    )
    
    issues = command_verify_verdicts(solution_filename=None, 
                                     print_issues=False, 
                                     formatter=formatter, 
                                     context=context)
    
    error_count = sum(1 for issue in issues if issue.type == TMTVerifyIssueType.ERROR)
    warning_count = sum(1 for issue in issues if issue.type == TMTVerifyIssueType.WARNING)
    
    assert error_count == expected_error_count, f"Expected {expected_error_count} errors, found {error_count}: {[i.message for i in issues if i.type == TMTVerifyIssueType.ERROR]}"
    assert warning_count == expected_warning_count, f"Expected {expected_warning_count} warnings, found {warning_count}: {[i.message for i in issues if i.type == TMTVerifyIssueType.WARNING]}"

@pytest.mark.parametrize(
    "problem_path, solution_filename, expected_error_count, expected_warning_count",
    [
        ("problems/verify", "model-solution.cpp", 0, 0),
        ("problems/verify", "correct-verdict.cpp", 0, 0),
        ("problems/verify", "incorrect-verdict.cpp", 4, 0),
    ],
)
def test_verify_verdicts_single(
    problem_path: str,
    solution_filename: str,
    expected_error_count: int,
    expected_warning_count: int,
):
    script_dir = pathlib.Path(__file__).parent.parent.resolve()
    problem_dir = pathlib.Path(__file__).parent.resolve() / problem_path
    formatter = TerminalFormatter()
    context = TMTContext(str(problem_dir), str(script_dir))

    # Force shorter trusted step time to speed up unit test
    context.config.trusted_step_time_limit_sec = 1.0

    command_clean(formatter=formatter, context=context, skip_confirm=True)
    command_gen(
        formatter=formatter, context=context, verify_hash=False, show_reason=False
    )
    
    issues = command_verify_verdicts(
        solution_filename=solution_filename,
        print_issues=False,
        formatter=formatter,
        context=context
    )
    
    error_count = sum(1 for issue in issues if issue.type == TMTVerifyIssueType.ERROR)
    warning_count = sum(1 for issue in issues if issue.type == TMTVerifyIssueType.WARNING)
    
    assert error_count == expected_error_count, f"Expected {expected_error_count} errors, found {error_count}: {[i.message for i in issues if i.type == TMTVerifyIssueType.ERROR]}"
    assert warning_count == expected_warning_count, f"Expected {expected_warning_count} warnings, found {warning_count}: {[i.message for i in issues if i.type == TMTVerifyIssueType.WARNING]}"
