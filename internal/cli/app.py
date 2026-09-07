"""An argparse-based command tree with type-directed dependency injection.

An `App` is a group of commands (leaf functions decorated with `@command`,
optionally `@option`/`@argument`) and/or nested sub-`App`s.
"""

import argparse
import inspect
from dataclasses import dataclass, field
from typing import Any, Callable

from internal.cli.params import ArgumentSpec, OptionSpec

Provider = Callable[..., Any]


@dataclass
class _Registered:
    func: Callable[..., Any]
    available_names: set[str] = field(default_factory=set)


@dataclass
class _Group:
    app: "App"
    default: str | None = None
    subcommand_help: str | None = None


def _add_option(parser: argparse.ArgumentParser, spec: OptionSpec) -> argparse.Action:
    kwargs = dict(spec.kwargs)
    if kwargs.pop("is_flag", False):
        kwargs.setdefault("action", "store_true")
        kwargs.setdefault("default", False)
    return parser.add_argument(*spec.flags, **kwargs)


def _suppressed(spec: OptionSpec) -> OptionSpec:
    """A copy of `spec` whose default is `SUPPRESS`.

    An inherited option is re-declared on every descendant parser so it stays
    usable after the subcommand token too. Only the parser that first introduces
    the option keeps its real default; the descendant copies use `SUPPRESS` so
    that parsing a subcommand never overwrites a value given before it (e.g.
    `tmt --color=never verify config`).
    """
    return OptionSpec(spec.flags, {**spec.kwargs, "default": argparse.SUPPRESS})


def _add_param(
    parser: argparse.ArgumentParser, spec: OptionSpec | ArgumentSpec
) -> argparse.Action:
    if isinstance(spec, ArgumentSpec):
        return parser.add_argument(spec.name, **spec.kwargs)
    return _add_option(parser, spec)


def _to_exit_code(result: Any) -> int:
    if result is None:
        return 0
    if isinstance(result, bool):
        return 0 if result else 1
    if isinstance(result, int):
        return result
    return 0 if result else 1


def _validate(
    func: Callable[..., Any],
    available_names: set[str],
    providers: dict[type, Provider],
    _seen: tuple[type, ...] = (),
) -> None:
    """Check that every parameter of `func` can be resolved, without calling it."""
    for name, param in inspect.signature(func).parameters.items():
        if name in available_names or param.annotation is argparse.Namespace:
            continue
        if param.annotation in providers:
            if param.annotation in _seen:
                raise RuntimeError(
                    f"Circular provider dependency detected for {param.annotation!r}."
                )
            _validate(
                providers[param.annotation],
                available_names,
                providers,
                _seen + (param.annotation,),
            )
            continue
        raise RuntimeError(
            f"{getattr(func, '__cli_name__', func.__qualname__)}: cannot resolve parameter "
            f"'{name}' (no CLI option/argument named '{name}' and no provider for "
            f"{param.annotation!r})."
        )


def _resolve(
    param: inspect.Parameter,
    namespace: argparse.Namespace,
    providers: dict[type, Provider],
    cache: dict[type, Any],
) -> Any:
    if hasattr(namespace, param.name):
        return getattr(namespace, param.name)
    if param.annotation is argparse.Namespace:
        return namespace
    if param.annotation not in cache:
        cache[param.annotation] = _call_with_injection(
            providers[param.annotation], namespace, providers, cache
        )
    return cache[param.annotation]


def _call_with_injection(
    func: Callable[..., Any],
    namespace: argparse.Namespace,
    providers: dict[type, Provider],
    cache: dict[type, Any],
) -> Any:
    kwargs = {
        name: _resolve(param, namespace, providers, cache)
        for name, param in inspect.signature(func).parameters.items()
    }
    return func(**kwargs)


class App:
    """A group of CLI commands, optionally nested under a parent `App`."""

    def __init__(self, name: str, help: str | None = None):
        self.name = name
        self.help = help
        self._global_options: list[OptionSpec] = []
        self._providers: dict[type, Provider] = {}
        self._commands: dict[str, _Registered] = {}
        self._groups: dict[str, _Group] = {}
        self._dest: str | None = None

    def global_option(self, *flags: str, **kwargs) -> None:
        """Register an option inherited by this app and every command/group under it."""
        self._global_options.append(OptionSpec(flags, kwargs))

    def provide(self, type_: type, factory: Provider) -> None:
        """Register a factory injected into any command/provider parameter annotated `type_`.

        `factory` is called at most once per `run()`, and may itself declare
        parameters resolved the same way (by CLI value name, by another
        provider's type, or `argparse.Namespace` for the raw parsed args).
        """
        self._providers[type_] = factory

    def add_command(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Register a function decorated with `@command(...)` as a leaf command."""
        name = getattr(func, "__cli_name__", None)
        if name is None:
            raise TypeError(f"{func!r} is missing @command(...); cannot register it.")
        self._commands[name] = _Registered(func=func)
        return func

    def add_group(
        self,
        sub_app: "App",
        name: str,
        *,
        default: str | None = None,
        help: str | None = None,
    ) -> None:
        """Nest `sub_app` as a subcommand group, e.g. `tmt verify <issue-class>`.

        If `default` is given, invoking `name` without a further subcommand
        dispatches to the command registered under that name in `sub_app`.
        `help` describes `sub_app`'s own subcommand choices (e.g. "The issue
        class to be verified."), shown in `tmt <name> --help` -- distinct from
        `sub_app.help`, which describes `name` itself in this app's own list.
        """
        self._groups[name] = _Group(sub_app, default, help)

    def _build(
        self,
        parser: argparse.ArgumentParser,
        inherited_options: list[OptionSpec],
        providers: dict[type, Provider],
        default: str | None,
        subcommand_help: str | None = None,
    ) -> None:
        # `inherited_options` already carry `SUPPRESS` as their default (their real
        # default was declared on the ancestor that introduced them). `self._global_options`
        # are new at this level, so they keep their real default on `parser` and are
        # passed down suppressed. Registered on `parser` itself too, so options are
        # usable before a subcommand token (e.g. `tmt --color=never verify config`).
        for spec in inherited_options:
            _add_option(parser, spec)
        for spec in self._global_options:
            _add_option(parser, spec)
        down_options = inherited_options + [
            _suppressed(s) for s in self._global_options
        ]

        if not self._commands and not self._groups:
            raise RuntimeError(f"App {self.name!r} has no commands registered.")

        # `dest` only needs to be unique among ancestors/descendants actually on the
        # same invocation path, which self.name already is for this project's tree.
        self._dest = self.name
        subparsers = parser.add_subparsers(
            dest=self._dest, required=default is None, help=subcommand_help
        )

        for name, registered in self._commands.items():
            sub = subparsers.add_parser(
                name,
                help=getattr(registered.func, "__cli_help__", None),
                **getattr(registered.func, "__cli_parser_kwargs__", {}),
            )
            leaf_names = {_add_option(sub, spec).dest for spec in down_options}
            for spec in getattr(registered.func, "__cli_params__", []):
                leaf_names.add(_add_param(sub, spec).dest)
            registered.available_names = leaf_names
            _validate(registered.func, leaf_names, providers)

        for name, group in self._groups.items():
            sub = subparsers.add_parser(name, help=group.app.help)
            group.app._build(
                sub,
                down_options,
                providers,
                group.default,
                subcommand_help=group.subcommand_help,
            )

    def _resolve_leaf(
        self, namespace: argparse.Namespace, default: str | None
    ) -> _Registered:
        assert self._dest is not None
        chosen = getattr(namespace, self._dest, None) or default
        if chosen in self._commands:
            return self._commands[chosen]
        if chosen in self._groups:
            group = self._groups[chosen]
            return group.app._resolve_leaf(namespace, group.default)
        raise RuntimeError(f"Unknown subcommand {chosen!r} for {self.name!r}.")

    def run(self, argv: list[str] | None = None, *, version: str | None = None) -> int:
        """Parse `argv` (default `sys.argv[1:]`), dispatch to the matching command, and
        return a process exit code derived from its return value.

        Only called on the root `App` of a tree (nested groups added via
        `add_group` never have `run()` called on them directly).
        """
        parser = argparse.ArgumentParser(description=self.help)
        self._build(parser, [], self._providers, default=None)
        if version is not None:
            parser.add_argument(
                "--version",
                action="version",
                version=version,
                help="Show the version of TMT.",
            )

        namespace = parser.parse_args(argv)
        registered = self._resolve_leaf(namespace, default=None)
        result = _call_with_injection(registered.func, namespace, self._providers, {})
        return _to_exit_code(result)
