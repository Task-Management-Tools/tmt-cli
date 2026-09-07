"""Decorators used to declare a function as a CLI command."""
from typing import Callable, TypeVar

from internal.cli.params import ArgumentSpec, OptionSpec

F = TypeVar("F", bound=Callable)


def command(name: str, *, help: str | None = None, **parser_kwargs) -> Callable[[F], F]:
    """Mark `func` as a leaf CLI command named `name`.

    `parser_kwargs` are forwarded as-is to `argparse`'s `add_parser`, as an
    escape hatch for things like `formatter_class`.
    """

    def decorator(func: F) -> F:
        setattr(func, "__cli_name__", name)
        setattr(func, "__cli_help__", help)
        setattr(func, "__cli_parser_kwargs__", parser_kwargs)
        return func

    return decorator


def option(*flags: str, **kwargs) -> Callable[[F], F]:
    """Declare an optional argument (e.g. `-r`, `--show-reason`) for a command.

    `kwargs` are forwarded to `add_argument`, except for `is_flag=True` which
    is sugar for `action="store_true", default=False`.
    """

    def decorator(func: F) -> F:
        params: list = getattr(func, "__cli_params__", [])
        params.append(OptionSpec(flags, kwargs))
        setattr(func, "__cli_params__", params)
        return func

    return decorator


def argument(name: str, **kwargs) -> Callable[[F], F]:
    """Declare a positional argument for a command. `kwargs` are forwarded to `add_argument`."""

    def decorator(func: F) -> F:
        params: list = getattr(func, "__cli_params__", [])
        params.append(ArgumentSpec(name, kwargs))
        setattr(func, "__cli_params__", params)
        return func

    return decorator
