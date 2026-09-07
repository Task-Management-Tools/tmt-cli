#!/usr/bin/env python3
import argparse
import os
import sys
import pathlib

from internal import __version__
from internal.context import TMTContext, find_problem_dir
from internal.commands.gen import command_gen
from internal.commands.invoke import command_invoke
from internal.commands.clean import command_clean
from internal.commands.export import command_export_cli
from internal.commands.make_public import command_make_public
from internal.commands.verify import (
    command_verify_cli,
    command_verify_config_cli,
    command_verify_verdicts_cli,
)
from internal.cli import App
from internal.exceptions import TMTMissingFileError, TMTInvalidConfigError
from internal.formatting import Formatter, TerminalFormatter, PlainFormatter


def build_formatter(namespace: argparse.Namespace) -> Formatter:
    # forced by args
    if namespace.color == "always":
        return TerminalFormatter()
    if namespace.color == "never":
        return PlainFormatter()
    # environment variable
    if os.getenv("NO_COLOR") or os.getenv("TERM") == "dumb":
        return PlainFormatter()
    if os.getenv("FORCE_COLOR"):
        return TerminalFormatter()
    # fallback to terminal detection
    if os.isatty(sys.stdout.fileno()):
        return TerminalFormatter()
    return PlainFormatter()


def build_context(formatter: Formatter) -> TMTContext:
    cwd = pathlib.Path.cwd()
    problem_dir = find_problem_dir(cwd)  # TODO specify it in args
    script_dir = str(pathlib.Path(__file__).parent.resolve())
    context = TMTContext(problem_dir, script_dir)

    # This check could be placed inside __init__ of TMTContext and check for certain environments,
    # but TMTConfig use __post_init__ for verfication and this is the only entry point of every command from the command line,
    # so placing it here kind of also make sense.
    if context.config.tmt_version == "latest":
        formatter.println(
            formatter.ANSI_YELLOW,
            "Warning: In problem.yaml, tmt_version is set to 'latest' in this problem. You should never use 'latest' in non-unit-test problem repositories.",
            formatter.ANSI_RESET,
        )

    return context


def build_app() -> App:
    app = App("tmt", help="TMT - Task Management Tools")
    app.global_option("--color", choices=["always", "auto", "never"], default="auto")
    app.provide(Formatter, build_formatter)
    app.provide(TMTContext, build_context)

    app.add_command(command_gen)
    app.add_command(command_invoke)
    app.add_command(command_clean)
    app.add_command(command_export_cli)
    app.add_command(command_make_public)

    verify_app = App("verify", help="Check issues.")
    verify_app.add_command(command_verify_cli)
    verify_app.add_command(command_verify_verdicts_cli)
    verify_app.add_command(command_verify_config_cli)
    app.add_group(
        verify_app, "verify", default="all", help="The issue class to be verified."
    )

    return app


if __name__ == "__main__":
    try:
        exit(build_app().run(version=f"TMT {__version__}"))
    except TMTMissingFileError as e:
        print()
        print(e)
        exit(1)
    except TMTInvalidConfigError as e:
        print()
        print(f'Invalid config, at: "{e}"')
        print(e.__cause__)
        exit(1)
