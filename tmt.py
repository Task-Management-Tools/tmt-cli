import argparse
import pathlib

from internal.formatting import Formatter
from internal.context import TMTContext, find_problem_dir
from internal.commands import command_gen, command_invoke, command_clean, command_export
from internal.errors import TMTMissingFileError, TMTInvalidConfigError


def main():
    parser = argparse.ArgumentParser(description="TMT - Task Management Tools")
    parser.add_argument(
        "--version",
        action="version",
        version="TMT 0.0.0",
        help="Show the version of TMT.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    parser_init = subparsers.add_parser("init", help="Init a TMT problem directory.")

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

    args = parser.parse_args()

    if args.command == "init":
        print("Directory initialization is not implemented yet.")
        return

    formatter = Formatter()
    cwd = pathlib.Path.cwd()
    problem_dir = find_problem_dir(cwd)  # TODO specify it in args
    script_dir = str(pathlib.Path(__file__).parent.resolve())
    context = TMTContext(problem_dir, script_dir)

    if args.command == "gen":
        command_gen(
            formatter=formatter,
            context=context,
            verify_hash=args.verify_hash,
            show_reason=args.show_reason,
        )
        return

    if args.command == "invoke":
        command_invoke(
            formatter=formatter,
            context=context,
            show_reason=args.show_reason,
            submission_files=args.submission_files,
        )
        return

    if args.command == "clean":
        command_clean(formatter=formatter, context=context, skip_confirm=args.yes)
        return

    if args.command == "export":
        command_export(formatter=formatter, context=context, output_path=args.output)
        return


if __name__ == "__main__":
    try:
        main()
    except TMTMissingFileError as e:
        print()
        print(e)
    except TMTInvalidConfigError as e:
        print()
        print(f'Invalid config, at: "{e}"')
        print(e.__cause__)
