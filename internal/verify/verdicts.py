from collections import Counter
import os
from pathlib import Path

from internal.commands.invoke import CommandInvokeSummary
from internal.compilation import languages
from internal.exceptions import TMTInvalidConfigError, TMTMissingFileError
from internal.formatting.base import Formatter
from internal.verdicts import ExpectedVerdict, SolutionVerdict, SubtaskVerdict, VerdictRule, parse_verdicts
from internal.formatting import Formatter, EmptyFormatter
from internal.commands import command_invoke
from internal.outcomes import EvaluationResult
from . import TMTVerifyIssueType, Verifier

class VerdictsVerifier(Verifier):
    name = "verdicts"
    registered_issue_code = {
        "missing_config": TMTVerifyIssueType.WARNING,
        "invalid_config": TMTVerifyIssueType.ERROR,
        "missing_solution": TMTVerifyIssueType.WARNING,
        "testcases_not_generated": TMTVerifyIssueType.ERROR,
        "compile_error": TMTVerifyIssueType.ERROR,
        "verdict_rule": TMTVerifyIssueType.ERROR,
        "score_range": TMTVerifyIssueType.ERROR,
        "default_rule": TMTVerifyIssueType.ERROR,
    }

    def _get_tests_outcome(
        self,
        results: dict[str, EvaluationResult | None],
        tests: list[str] | set[str],
    ) -> tuple[float, str, Counter[ExpectedVerdict]]:
        counter = Counter[ExpectedVerdict]()
        score = 1.0
        for testcase in tests:
            result = results[testcase]
            if not result:
                counter[ExpectedVerdict.UNKNOWN] += 1
                score = min(score, 0.0)
            else:
                counter[ExpectedVerdict.from_evaluation_outcome(result.verdict)] += 1
                score = min(score, result.score)
        incorrect = False
        partial = False
        for verdict in counter:
            if verdict == ExpectedVerdict.PARTIAL:
                partial = True
            if verdict not in [ExpectedVerdict.PARTIAL, ExpectedVerdict.ACCEPTED]:
                incorrect = True
        result_str = "Incorrect" if incorrect else "Partial" if partial else "Correct"
        # TODO: compute score based on judge convention
        return score, result_str, counter

    def _check_verdict_rule(
        self,
        filename: str,
        subtask_name: str,
        verdicts: set[ExpectedVerdict],
        rule: VerdictRule,
    ) -> None:
        if not rule.check_rule(verdicts):
            self.add_issue("verdict_rule", filename, f"{subtask_name} violates verdict rule {rule}")

    def _check_default_rule(
        self,
        filename: str,
        subtask_name: str,
        verdicts: set[ExpectedVerdict],
    ) -> None:
        rule = VerdictRule(never=[ExpectedVerdict.JUDGE_ERROR,
                            ExpectedVerdict.TIME_LIMIT_EXCEEDED_WALL,
                            ExpectedVerdict.UNKNOWN])
        if not rule.check_rule(verdicts):
            self.add_issue("default_rule", filename, f"{subtask_name} violates default verdict rule {rule}")

    def verify_single_solution(
        self,
        *,
        formatter: Formatter,
        solution: SolutionVerdict,
        invoke_summary: CommandInvokeSummary | None = None,
    ):
        context = self.context
        path_helper = context.path
        subtask_list = context.recipe.subtasks

        submission_file = os.path.join(path_helper.solutions, solution.filename)
        formatter.println()
        formatter.println(f"Solution {solution.filename}:")
        result = invoke_summary if invoke_summary else command_invoke(
            formatter=formatter,
            context=context,
            submission_files=[submission_file],
            show_reason=False
        )

        if result.is_compilation_error():
            self.add_issue("compile_error", submission_file, "Solution compilation error")
            return

        # Compute column width
        max_subtask_len = len("Subtask")
        for subtask in subtask_list:
            max_subtask_len = max(max_subtask_len, len(subtask))
        max_subtask_len += 1
        print_subtask = bool(subtask_list)
        result_len = len("Incorrect") + 1
        score_num_len = len("100.00") + 1
        score_percent_len = len("(100%)") + 1
        score_len = score_num_len + score_percent_len

        # Print table header
        if print_subtask:
            formatter.print_fixed_width("Subtask", width=max_subtask_len)
        formatter.print_fixed_width("Result", width=result_len)
        if print_subtask:
            formatter.print_fixed_width("Score", width=score_len)
        formatter.println("Verdicts")
        def print_row(subtask_name, result_str, score_num, score_percent, verdict_count: Counter[ExpectedVerdict]):
            if print_subtask:
                formatter.print_fixed_width(subtask_name, width=max_subtask_len)
            formatter.print_fixed_width(result_str, width=result_len)
            if print_subtask:
                formatter.print_fixed_width(f"{round(score_num, 2)}", width=score_num_len)
                formatter.print_fixed_width(f"({round(score_percent * 100)}%)", width=score_percent_len)
            formatter.println(', '.join([f"{verdict}*{count}" for verdict, count in verdict_count.items()]))

        # Collect subtask rules
        subtask_rules: dict[str, SubtaskVerdict] = dict()
        for subtask_verdict in solution.subtask:
            for subtask in subtask_verdict.subtask:
                subtask_rules[subtask] = subtask_verdict
        default_subtask_rule = SubtaskVerdict([], solution.verdict, solution.score)

        max_score = 0 # sum of subtask score
        if print_subtask:
            for subtask_name, subtask in subtask_list.items():
                max_score += subtask.score
                score, result_str, verdict_count = self._get_tests_outcome(result.testcase_results, subtask.get_all_test_names()) # type: ignore
                score_num = score * subtask.score
                score_percent = score
                print_row(subtask_name, result_str, score_num, score_percent, verdict_count)
                subtask_rule = subtask_rules[subtask_name] if subtask_name in subtask_rules else default_subtask_rule
                self._check_verdict_rule(
                    submission_file,
                    f"Subtask {subtask_name}",
                    set(verdict_count.keys()),
                    subtask_rule.verdict
                )
                if not subtask_rule.score.check_score(score):
                    self.add_issue("score_range", submission_file,
                                   f"Subtask {subtask_name} score {score} violates the score range {subtask_rule.score}")
                
            formatter.println("-" * (max_subtask_len + result_len + score_len + 20))

        # Overall outcome
        score, result_str, verdict_count = self._get_tests_outcome(
            result.testcase_results, 
            context.recipe.get_all_test_names()
        )
        print_row("Overall", result_str, score * max_score, score, verdict_count)

        # Check overall verdict only if no subtask
        if not subtask_list:
            self._check_verdict_rule(
                submission_file,
                "Overall result",
                set(verdict_count.keys()), 
                default_subtask_rule.verdict
            )
            if not default_subtask_rule.score.check_score(score):
                self.add_issue("score_range", submission_file,
                               f"Overall score {score} violates the score range {default_subtask_rule.score}")
        

    def verify(
        self, 
        formatter: Formatter, 
    ):
        context = self.context

        # Parse verdicts.yaml
        try:
            solutions = parse_verdicts(context)
        except (ValueError, TypeError, TMTInvalidConfigError) as e:
            self.add_issue("invalid_config", context.path.verdicts_yaml, str(e))
            return
        except TMTMissingFileError as e:
            self.add_issue("missing_config", context.path.verdicts_yaml, str(e))
            return

        # Check testcase generated
        if not (
            os.path.exists(context.path.testcase_summary)
            and os.path.isfile(context.path.testcase_summary)
        ):
            self.add_issue("testcases_not_generated", context.path.testcase_summary, 
                           "Testcases not generated, run tmt gen first")
            return

        all_filename = set(solution.filename for solution in solutions)

        # Check missing solutions
        for language_type in languages.languages:
            language = language_type(context)
            for ext in language.source_extensions:
                for file in Path(context.path.solutions).rglob(f"*{ext}"):
                    filename = os.path.relpath(file, context.path.solutions)
                    if filename not in all_filename:
                        self.add_issue("missing_solution", context.path.verdicts_yaml,
                                       f"Solution {filename} is missing in verdicts.yaml")

        # Verify verdicts
        for solution in solutions:
            self.verify_single_solution(
                formatter=formatter,
                solution=solution
            )
        
