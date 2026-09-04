#!/usr/bin/env python3
import argparse
from logging import Formatter
import os
import sys
import pathlib

from internal import __version__
from internal.context import TMTContext, find_problem_dir
from internal.commands.gen import command_gen
from internal.commands.invoke import command_invoke
from internal.commands.clean import command_clean
from internal.commands.export import command_export
from internal.commands.make_public import command_make_public
from internal.commands.verify import (
    command_verify,
    command_verify_config,
    command_verify_verdicts,
)
from internal.exporters import exporters
from internal.exceptions import TMTMissingFileError, TMTInvalidConfigError
from internal.exporters.base import BaseExporter
from internal.formatting import TerminalFormatter, PlainFormatter
from internal.verify.verifier import TMTVerifyIssueType


def main():
    parser = argparse.ArgumentParser(description="TMT - Task Management Tools")
    parser.add_argument("--color", choices=["always", "auto", "never"], default="auto")
    parser.add_argument(
        "--version",
        action="version",
        version=f"TMT {__version__}",
        help="Show the version of TMT.",
    )

    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument(
        "--color", choices=["always", "auto", "never"], default=argparse.SUPPRESS
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # parser_init = subparsers.add_parser("init", help="Init a TMT problem directory.")

    # tmt gen
    parser_gen = subparsers.add_parser(
        "gen", help="Generate testcases.", parents=[shared]
    )
    parser_gen.add_argument(
        "-r",
        "--show-reason",
        action="store_true",
        help="Show the failed reason and checker's output (in case of checker validation is enabled) of each testcase.",
    )
    parser_gen.add_argument(
        "--verify-hash",
        action="store_true",
        help="Check if the hash digest of the testcases matches.",
    )

    # tmt invoke
    parser_invoke = subparsers.add_parser(
        "invoke", help="Invoke a solution.", parents=[shared]
    )
    parser_invoke.add_argument("-r", "--show-reason", action="store_true")
    parser_invoke.add_argument("submission_files", nargs="*")

    # tmt clean
    parser_clean = subparsers.add_parser(
        "clean", help="Clean-up a TMT problem directory.", parents=[shared]
    )
    parser_clean.add_argument(
        "-y", "--yes", action="store_true", help="Automatic yes to prompts."
    )

    # tmt export
    parser_export = subparsers.add_parser(
        "export",
        help="Export packages",
        parents=[shared],
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser_export.add_argument(
        "output_path",
        help="Output path of the archive. "
        "If the path is considered a directory, it will be exported to <short_name>.zip inside the directory. "
        "By default, a path ending with a trailing slash and a path that is a directory are considered a directory. "
        "Specifying --explicit-directory disables the second case and the path will always be treated as a file if it has no trailing slash.",
    )
    parser_export.add_argument(
        "-p",
        "--package",
        help="Specifies package format. "
        "If not set, use default exporter of the judge convention. "
        "Otherwise, must be one of: \n"
        + "".join(f" - {k}: {v.description}\n" for k, v in exporters.items()),
        choices=list(exporters.keys()),
        default=None,
    )
    parser_export.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Force overwriting the output file even if it exists.",
    )
    parser_export.add_argument(
        "-e",
        "--explicit-directory",
        action="store_true",
        help="Prevent outputing into the directory if the path specified is a directory but not specified with trailing slash.",
    )

    # tmt make-public
    subparsers.add_parser(
        "make-public", help="Build public attachment archive file.", parents=[shared]
    )

    # tmt verify ...
    parser_verify = subparsers.add_parser(
        "verify", help="Check issues.", parents=[shared]
    )
    verify_subparser = parser_verify.add_subparsers(
        dest="issue_class", help="The issue class to be verified."
    )
    # tmt verify all
    verify_subparser.add_parser(
        "all", help="Verify all issue classes.", parents=[shared]
    )
    # tmt verify verdicts
    parser_verify_verdicts = verify_subparser.add_parser(
        "verdicts", help="Verify solution verdicts.", parents=[shared]
    )
    parser_verify_verdicts.add_argument(
        "-s", "--solution", help="The solution filename in solutions/."
    )
    # tmt verify config
    verify_subparser.add_parser("config", help="Verify configs.", parents=[shared])

    args = parser.parse_args()

    # forced by args
    formatter: Formatter
    if args.color == "always":
        formatter = TerminalFormatter()
    elif args.color == "never":
        formatter = PlainFormatter()
    # environment variable
    elif os.getenv("NO_COLOR") or os.getenv("TERM") == "dumb":
        formatter = PlainFormatter()
    elif os.getenv("FORCE_COLOR"):
        formatter = TerminalFormatter()
    # fallback to terminal detection
    elif os.isatty(sys.stdout.fileno()):
        formatter = TerminalFormatter()
    else:
        formatter = PlainFormatter()

    if args.command == "init":
        print("Directory initialization is not implemented yet.")
        return

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

    if args.command == "gen":
        cmd_ret = command_gen(
            formatter=formatter,
            context=context,
            verify_hash=args.verify_hash,
            show_reason=args.show_reason,
        )
        return bool(cmd_ret)

    if args.command == "invoke":
        cmd_ret = command_invoke(
            formatter=formatter,
            context=context,
            show_reason=args.show_reason,
            submission_files=args.submission_files,
        )
        return bool(cmd_ret)

    if args.command == "clean":
        command_clean(formatter=formatter, context=context, skip_confirm=args.yes)
        return True  # Does not fail without exception

    if args.command == "export":
        output_path: str = args.output_path

        package_format: type[BaseExporter] | None = None
        if args.package is not None:
            package_format = exporters.get(args.package)
            if package_format is None:
                parser_export.error(
                    f"invalid package format: must be one of {', '.join(exporters.keys())}"
                )

        # UNIX directory
        if output_path.endswith(os.sep):
            output_path += context.config.short_name + ".zip"
        if not args.explicit_directory and (pathlib.Path.cwd() / output_path).is_dir():
            output_path += os.sep + context.config.short_name + ".zip"

        res = command_export(
            formatter=formatter,
            context=context,
            output_path=output_path,
            package_format=package_format,
            force_output=args.force,
        )
        return bool(res)

    if args.command == "make-public":
        ret = command_make_public(formatter=formatter, context=context)
        return ret

    if args.command == "verify":
        if args.issue_class == "all" or args.issue_class is None:
            ret = command_verify(
                print_issues=True, formatter=formatter, context=context
            )
        elif args.issue_class == "config":
            ret = command_verify_config(
                print_issues=True, formatter=formatter, context=context
            )
        elif args.issue_class == "verdicts":
            ret = command_verify_verdicts(
                solution_filename=args.solution,
                print_issues=True,
                formatter=formatter,
                context=context,
            )
        else:
            formatter.println(f"Unknown issue class {args.issue_class}")
            return False
        return not any(issue.type == TMTVerifyIssueType.ERROR for issue in ret)

    return False


if __name__ == "__main__":
    try:
        success = main()
        exit(0 if success else 1)
    except TMTMissingFileError as e:
        print()
        print(e)
        exit(1)
    except TMTInvalidConfigError as e:
        print()
        print(f'Invalid config, at: "{e}"')
        print(e.__cause__)
        exit(1)
