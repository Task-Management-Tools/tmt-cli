import argparse
import pathlib

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
from internal.exceptions import TMTMissingFileError, TMTInvalidConfigError
from internal import __version__
from internal.formatting import TerminalFormatter
from internal.verify.verifier import TMTVerifyIssueType


def main():
    parser = argparse.ArgumentParser(description="TMT - Task Management Tools")
    parser.add_argument(
        "--version",
        action="version",
        version=f"TMT {__version__}",
        help="Show the version of TMT.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # parser_init = subparsers.add_parser("init", help="Init a TMT problem directory.")

    parser_gen = subparsers.add_parser("gen", help="Generate testcases.")
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

    parser_invoke = subparsers.add_parser("invoke", help="Invoke a solution.")
    parser_invoke.add_argument("-r", "--show-reason", action="store_true")
    parser_invoke.add_argument("submission_files", nargs="*")

    parser_clean = subparsers.add_parser(
        "clean", help="Clean-up a TMT problem directory."
    )
    parser_clean.add_argument(
        "-y", "--yes", action="store_true", help="Automatic yes to prompts."
    )

    parser_export = subparsers.add_parser("export", help="Export packages")
    parser_export.add_argument("output", help="The filename of the exported zip file.")

    subparsers.add_parser("make-public", help="Build public attachment archive file")

    parser_verify = subparsers.add_parser("verify", help="Check issues.")
    verify_subparser = parser_verify.add_subparsers(
        dest="issue_class", help="The issue class to be verified."
    )
    verify_subparser.add_parser("all", help="Verify all issue classes.")
    parser_verify_verdicts = verify_subparser.add_parser(
        "verdicts", help="Verify solution verdicts."
    )
    parser_verify_verdicts.add_argument(
        "-s", "--solution", help="The solution filename in solutions/."
    )
    verify_subparser.add_parser("config", help="Verify configs.")

    args = parser.parse_args()

    if args.command == "init":
        print("Directory initialization is not implemented yet.")
        return

    formatter = TerminalFormatter()
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
        command_export(formatter=formatter, context=context, output_path=args.output)
        return True  # Does not fail without exception

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
