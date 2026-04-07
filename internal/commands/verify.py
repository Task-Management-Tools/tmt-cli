from collections import Counter
import os

from internal.formatting import Formatter
from internal.context import TMTContext
from internal.verify import VerdictsVerifier
from internal.verify.verifier import TMTVerifyIssue, TMTVerifyIssueType

def command_verify(
    *,
    formatter: Formatter,
    context: TMTContext,
) -> list[TMTVerifyIssue]:
    """
    Check issues.
    """
    issues: list[TMTVerifyIssue] = []
    issues += verify_verdicts(formatter=formatter, context=context)

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
                formatter.println(formatter.ANSI_YELLOW, print_message, formatter.ANSI_RESET)
            case TMTVerifyIssueType.ERROR:
                formatter.println(formatter.ANSI_RED, print_message, formatter.ANSI_RESET)
            case _:
                raise NotImplementedError(f"Unknown issue type {issue_type}.")

    formatter.println(f"{counter[TMTVerifyIssueType.WARNING]} warning, {counter[TMTVerifyIssueType.ERROR]} error")

    return issues

def verify_verdicts(
    *,
    formatter: Formatter,
    context: TMTContext
) -> list[TMTVerifyIssue]:
    verifier = VerdictsVerifier(context)
    verifier.verify(formatter)
    return verifier.issues