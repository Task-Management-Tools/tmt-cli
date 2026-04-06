from internal.formatting import Formatter
from internal.context import TMTContext
from internal.verify import VerdictsVerifier
from internal.verify.verifier import TMTVerifyIssue

def command_verify(
    *,
    formatter: Formatter,
    context: TMTContext,
) -> list[TMTVerifyIssue]:
    """
    Check issues.
    """
    issues = []
    issues += verify_solutions(formatter=formatter, context=context)
    return issues


def verify_solutions(
    *,
    formatter: Formatter,
    context: TMTContext
) -> list[TMTVerifyIssue]:
    verifier = VerdictsVerifier(context)
    verifier.verify(formatter)
    return verifier.issues