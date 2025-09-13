if (
    context.path.has_checker_directory()
    and context.config.checker_type is CheckerType.DEFAULT
):
    formatter.println(
        formatter.ANSI_YELLOW,
        "Warning: Directory 'checker' exists but it is not used by this problem. Check problem.yaml or remove the directory.",
        formatter.ANSI_RESET,
    )
