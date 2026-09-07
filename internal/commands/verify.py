from collections import Counter
import os
from pathlib import Path

from internal.cli import command, option
from internal.formatting import Formatter
from internal.context import TMTContext
from internal.verify import (
    TMTVerifyIssue,
    TMTVerifyIssueType,
    VerdictsVerifier,
    ConfigVerifier,
)


def _print_verify_issue(
    issues: list[TMTVerifyIssue], formatter: Formatter, context: TMTContext
):
    formatter.println()
    counter: Counter[TMTVerifyIssueType] = Counter()
    for issue in issues:
        issue_type = issue.type
        relative_path = os.path.relpath(issue.related_file, context.path.problem_dir)
        print_message = f"[{issue.verifier_name}] {relative_path}: {issue.message}"
        counter[issue_type] += 1
        match issue_type:
            case TMTVerifyIssueType.IGNORE:
                pass
            case TMTVerifyIssueType.WARNING:
                formatter.println(
                    formatter.ANSI_YELLOW,
                    "Warning: ",
                    print_message,
                    formatter.ANSI_RESET,
                )
            case TMTVerifyIssueType.ERROR:
                formatter.println(
                    formatter.ANSI_RED, "Error: ", print_message, formatter.ANSI_RESET
                )
            case _:
                raise NotImplementedError(f"Unknown issue type {issue_type}.")

    formatter.println(
        f"{counter[TMTVerifyIssueType.WARNING]} warning, {counter[TMTVerifyIssueType.ERROR]} error"
    )


def command_verify(
    *,
    print_issues: bool,
    formatter: Formatter,
    context: TMTContext,
) -> list[TMTVerifyIssue]:
    """
    Check issues.
    """
    issues: list[TMTVerifyIssue] = []
    issues += command_verify_config(
        print_issues=False, formatter=formatter, context=context
    )
    issues += command_verify_verdicts(
        solution_filename=None, print_issues=False, formatter=formatter, context=context
    )

    if print_issues:
        _print_verify_issue(issues, formatter, context)

    return issues


def command_verify_config(
    *, print_issues: bool, formatter: Formatter, context: TMTContext
) -> list[TMTVerifyIssue]:
    verifier = ConfigVerifier(context)
    verifier.verify()

    if print_issues:
        _print_verify_issue(verifier.issues, formatter, context)

    return verifier.issues


def command_verify_verdicts(
    *,
    solution_filename: str | None,
    print_issues: bool,
    formatter: Formatter,
    context: TMTContext,
) -> list[TMTVerifyIssue]:

    if solution_filename:
        candidate_file_path = Path(solution_filename).resolve()
        if candidate_file_path.is_relative_to(context.path.solutions):
            solution_filename = os.path.relpath(
                candidate_file_path, context.path.solutions
            )

    verifier = VerdictsVerifier(context)
    verifier.verify(solution_filename=solution_filename, formatter=formatter)

    if print_issues:
        _print_verify_issue(verifier.issues, formatter, context)

    return verifier.issues


def _no_errors(issues: list[TMTVerifyIssue]) -> bool:
    return not any(issue.type == TMTVerifyIssueType.ERROR for issue in issues)


@command("all", help="Verify all issue classes.")
def command_verify_cli(*, formatter: Formatter, context: TMTContext) -> bool:
    """CLI entry point for `tmt verify all` (and the bare `tmt verify`)."""
    issues = command_verify(print_issues=True, formatter=formatter, context=context)
    return _no_errors(issues)


@command("config", help="Verify configs.")
def command_verify_config_cli(*, formatter: Formatter, context: TMTContext) -> bool:
    """CLI entry point for `tmt verify config`."""
    issues = command_verify_config(
        print_issues=True, formatter=formatter, context=context
    )
    return _no_errors(issues)


@command("verdicts", help="Verify solution verdicts.")
@option(
    "-s",
    "--solution",
    dest="solution_filename",
    help="The solution filename in solutions/.",
)
def command_verify_verdicts_cli(
    *, solution_filename: str | None, formatter: Formatter, context: TMTContext
) -> bool:
    """CLI entry point for `tmt verify verdicts`."""
    issues = command_verify_verdicts(
        solution_filename=solution_filename,
        print_issues=True,
        formatter=formatter,
        context=context,
    )
    return _no_errors(issues)
