from internal.verify import TMTVerifyIssueType

from . import Verifier


class ConfigVerifier(Verifier):
    name = "config"
    registered_issue_code = {
        # A testcase has no any validator
        "no_validator": TMTVerifyIssueType.ERROR,
        # Use subtasks in judge convention with display_score=False
        "score_not_available": TMTVerifyIssueType.WARNING,
        # No subtask contains all testcases
        "no_full_subtask": TMTVerifyIssueType.WARNING,
    }

    def verify(self):
        context = self.context
        path_helper = context.path

        # score_not_available
        if (
            context.recipe.subtasks
            and not context.config.judge_convention.value.display_score
        ):
            self.add_issue(
                "score_not_available",
                path_helper.problem_yaml,
                f"Subtasks used with judge convention {context.config.judge_convention.name}",
            )

        # no_validator
        no_validator_testcases = []
        for _, testset in context.recipe.testsets.items():
            for testcase in testset.testcases:
                if not testcase.validation:
                    no_validator_testcases.append(testcase.name)
        if no_validator_testcases:
            self.add_issue(
                "no_validator",
                path_helper.tmt_recipe,
                f"There is no validator for testcase {', '.join(no_validator_testcases)}",
            )

        # no_full_subtask
        testcase_count = 0
        for _, testset in context.recipe.testsets.items():
            testcase_count += len(testset.testcases)
        if context.recipe.subtasks and not any(
            len(subtask.get_all_test_names()) == testcase_count
            for _, subtask in context.recipe.subtasks.items()
        ):
            self.add_issue(
                "no_full_subtask",
                path_helper.tmt_recipe,
                "There is no subtask including all testcases",
            )
