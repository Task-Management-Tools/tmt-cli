from internal.formatting import Formatter
from internal.context import TMTContext
from internal.verify import VerdictsVerifier

def command_verify(
    *,
    formatter: Formatter,
    context: TMTContext,
):
    """
    Check issues.
    """
    verify_solutions(formatter=formatter, context=context)


def verify_solutions(
    *,
    formatter: Formatter,
    context: TMTContext
):
    verifier = VerdictsVerifier(context)
    verifier.verify(formatter)