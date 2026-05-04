#!/usr/bin/env python3
import argparse
import os
import sys
import pathlib

from internal import __version__
from internal.commands.verify import command_verify_config, command_verify_verdicts
from internal.context import TMTContext, find_problem_dir
from internal.commands import (
    command_gen,
    command_invoke,
    command_clean,
    command_export,
    command_make_public,
    command_verify,
)
from internal.exporters import exporters
from internal.exceptions import TMTMissingFileError, TMTInvalidConfigError
from internal.formatting import TerminalFormatter, PlainFormatter
from internal.verify.verifier import TMTVerifyIssueType


def main():
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--color", choices=["always", "auto", "never"], default="auto")

    parser = argparse.ArgumentParser(
        description="TMT - Task Management Tools", parents=[shared]
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"TMT {__version__}",
        help="Show the version of TMT.",
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
        "export_args",
        nargs="*",
        metavar="FORMAT OUTPUT",
        help="If none of the --package and --output flags are given, "
        "automatically infers the export operation if possible. "
        "If only one of them is given, FORMAT must match a package format and OUTPUT must end with .zip (for file) or a slash (for directory)",
    )
    parser_export.add_argument(
        "-p",
        "--package",
        help="Specifies package format. If not set, use default exporter of the judge convention. "
        "Otherwise, must be one of: \n"
        + "".join(f" - {k}: {v.description}\n" for k, v in exporters.items()),
        choices=list(exporters.keys()),
        metavar="FORMAT",
        default=None,
    )
    parser_export.add_argument(
        "-o",
        "--output",
        help="Output file or directory for the exported zip archive.",
        default=None,
    )
    parser_export.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Force overwriting the output file even if it exists.",
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
        if len(args.export_args) > 2:
            parser_export.error(
                "too many arguments: too many positional provided for tmt-export"
            )
        if (args.output is not None) + (args.package is not None) + len(
            args.export_args
        ) > 2:
            parser_export.error(
                "ambiguous arguments: mixed positional argument and flags for package and output"
            )

        package_format = args.package
        output_path = args.output

        # both missing
        if package_format is None and output_path is None:
            if len(args.export_args) == 1:
                if args.export_args[0] in exporters.keys():
                    package_format = args.export_args[0]
                elif args.export_args[0].endswith("/") or args.export_args[0].endswith(
                    ".zip"
                ):
                    output_path = args.export_args[0]
                else:
                    parser_export.error(
                        f"ambiguous argument: '{args.export_args[0]}' is not a valid format ({', '.join(exporters.keys())}) "
                        "and doesn't look like an archive name (expected .zip or trailing /). "
                        "Use explicit flags if you want to use it for output path."
                    )
            elif len(args.export_args) == 2:
                package_format, output_path = args.export_args
        # one missing; must be another
        elif package_format is None:
            package_format = args.export_args[0] if args.export_args else None
        elif output_path is None:
            output_path = args.export_args[0] if args.export_args else None

        if package_format is not None and package_format not in exporters.keys():
            parser_export.error(
                f"invalid package format: must be one of {', '.join(exporters.keys())}"
            )

        if output_path is None:
            output_path = "."

        res = command_export(
            formatter=formatter,
            context=context,
            output_path=output_path,
            package_format=exporters[package_format]
            if package_format is not None
            else None,
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
