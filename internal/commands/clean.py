def command_clean(context: TMTContext, args):
    formatter = Formatter()

    def confirm(message: str) -> bool:
        if args.yes:
            formatter.println(message + ".")
            return True

        formatter.print(message + "? [Y/n] ")
        while True:
            yesno = input().strip().lower()
            if yesno in ["y", "yes"]:
                return True
            if yesno in ["n", "no"]:
                return False
            formatter.print("Please answer yes or no. [Y/n] ")

    if confirm("Cleanup logs and sandbox"):
        if os.path.exists(context.path.logs):
            shutil.rmtree(context.path.logs)
        if os.path.exists(context.path.sandbox):
            shutil.rmtree(context.path.sandbox)

    if confirm("Cleanup testcases"):
        context.path.clean_testcases()
    # TODO: clean statement?

    if confirm("Cleanup compiled generators, validators and solutions"):
        GenerationStep(context).clean_up()
        ValidationStep(context).clean_up()
        if (
            context.config.problem_type is ProblemType.BATCH
            and context.config.checker_type is not CheckerType.DEFAULT
        ):
            ICPCCheckerStep(context).clean_up()
        make_solution_step(
            problem_type=context.config.problem_type,
            context=context,
            is_generation=False,
            submission_files=[],
        ).clean_up()

    formatter.println("Cleanup completed.")
