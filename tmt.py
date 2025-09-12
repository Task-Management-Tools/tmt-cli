import argparse
import pathlib

from internal.formatting import Formatter
from internal.context import TMTContext, find_problem_dir
from internal.commands import command_gen, command_invoke, command_clean


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

    args = parser.parse_args()

    if args.command == "init":
        raise NotImplementedError("Directory initialization is not implemented yet.")
        return

    formatter = Formatter()
    script_dir = str(pathlib.Path(__file__).parent.resolve())
    problem_dir = find_problem_dir(script_dir)
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


if __name__ == "__main__":
    main()
