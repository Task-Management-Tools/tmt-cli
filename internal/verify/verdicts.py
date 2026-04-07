from collections import Counter
from dataclasses import dataclass
from enum import Enum, auto
from http.client import ACCEPTED
import os
from pathlib import Path

from internal.commands.invoke import CommandInvokeSummary
from internal.compilation import languages
from internal.exceptions import TMTInvalidConfigError, TMTMissingFileError
from internal.formatting.base import Formatter
from internal.verdicts import ExpectedVerdict, ScoreRange, SolutionVerdict, SubtaskVerdict, VerdictRule, parse_verdicts
from internal.formatting import Formatter
from internal.commands import command_invoke
from internal.outcomes import EvaluationResult
from . import TMTVerifyIssueType, Verifier

class SubtaskResult(Enum):
    INCORRECT = "Incorrect"
    PARTIAL = "Partial"
    CORRECT = "Correct"

@dataclass
class SubtaskOutcome:
    score: float
    result: SubtaskResult
    counter: Counter[ExpectedVerdict]

@dataclass
class VerdictsVerifierResult:
    name: str
    result_type: SubtaskResult
    score: float
    verdicts: Counter[ExpectedVerdict]
    score_range: ScoreRange
    verdict_rule: VerdictRule

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
    ) -> SubtaskOutcome:
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
        result_type = SubtaskResult.INCORRECT if incorrect \
                     else SubtaskResult.PARTIAL if partial \
                     else SubtaskResult.CORRECT
        # TODO: compute score based on judge convention
        return SubtaskOutcome(score, result_type, counter)

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

    def _print_result_table(self, formatter: Formatter, results: list[VerdictsVerifierResult]):

        # Compute column width
        # Result                                          Expected
        # Subtask Result  Score     Verdicts              Score     Verdicts
        max_subtask_len = len("Subtask")
        subtask_list = self.context.recipe.subtasks
        for subtask in subtask_list:
            max_subtask_len = max(max_subtask_len, len(subtask))

        print_subtask = bool(subtask_list)
        print_score = self.context.config.judge_convention.value.display_score

        max_subtask_len += 1
        if not print_subtask:
            max_subtask_len = 0
        result_type_len = len("Incorrect") + 1
        score_len = len("Score") + 1 if print_score else 0
        verdicts_len = 30
        result_part_len = max_subtask_len + result_type_len + score_len + verdicts_len
        score_range_len = len("000-000") if print_score else 0

        def get_displayed_verdict(verdict: ExpectedVerdict):
            match verdict:
                case ExpectedVerdict.ACCEPTED:
                    print_color = formatter.ANSI_GREEN
                case ExpectedVerdict.PARTIAL:
                    print_color = formatter.ANSI_YELLOW
                case ExpectedVerdict.WRONG_ANSWER:
                    print_color = formatter.ANSI_RED
                case ExpectedVerdict.TIME_LIMIT_EXCEEDED | ExpectedVerdict.TIME_LIMIT_EXCEEDED_WALL:
                    print_color = formatter.ANSI_BLUE
                case ExpectedVerdict.RUNTIME_ERROR:
                    print_color = formatter.ANSI_PURPLE
                case ExpectedVerdict.OUTPUT_LIMIT:
                    print_color = formatter.ANSI_GREY
                case _:
                    print_color = formatter.ANSI_RED_BG
            return [print_color, verdict.short_name, formatter.ANSI_RESET]

        formatter.println()

        formatter.print_fixed_width("Result", width=result_part_len)
        formatter.println("Expected")

        if print_subtask:
            formatter.print_fixed_width("Subtask", width=max_subtask_len)
        formatter.print_fixed_width("Result", width=result_type_len)
        if print_score:
            formatter.print_fixed_width("Score", width=score_len)
        formatter.print_fixed_width("Verdicts", width=verdicts_len)

        if print_score:
            formatter.print_fixed_width("Score", width=score_range_len)
        formatter.println("Verdicts")

        for result in results:
            if print_subtask:
                formatter.print_fixed_width(result.name, width=max_subtask_len)
            match result.result_type:
                case SubtaskResult.CORRECT:
                    print_color = formatter.ANSI_GREEN
                case SubtaskResult.PARTIAL:
                    print_color = formatter.ANSI_YELLOW
                case SubtaskResult.INCORRECT:
                    print_color = formatter.ANSI_RED
            formatter.print(print_color)
            formatter.print_fixed_width(result.result_type.value, width=result_type_len)
            formatter.print(formatter.ANSI_RESET)

            if print_score:
                formatter.print_fixed_width(f"{round(result.score, 2)}", width=score_len)
            print_sequence = []
            for verdict, count in result.verdicts.items():
                if print_sequence:
                    print_sequence += ", "
                print_sequence += get_displayed_verdict(verdict)
                print_sequence += f"*{count}"
            formatter.print_fixed_width(*print_sequence, 
                                        width=verdicts_len)

            formatter.print_fixed_width(result.score_range, width=score_range_len)
            print_sequence = []
            if result.verdict_rule.never or len(result.verdict_rule.must) >= 2:
                print_sequence += ["must: "]
                for verdict in result.verdict_rule.must:
                    print_sequence += get_displayed_verdict(verdict) + [", "]
                print_sequence += ["never: "]
                for verdict in result.verdict_rule.never:
                    print_sequence += get_displayed_verdict(verdict) + [", "]
                print_sequence = print_sequence[:-1]
            elif not result.verdict_rule.must:
                pass
            else: # len(result.verdict_rule.must) == 1
                print_sequence += get_displayed_verdict(result.verdict_rule.must[0])

            formatter.println(*print_sequence)

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

        # Collect subtask rules
        subtask_rules: dict[str, SubtaskVerdict] = dict()
        for subtask_verdict in solution.subtask:
            for subtask in subtask_verdict.subtask:
                subtask_rules[subtask] = subtask_verdict
        default_subtask_rule = SubtaskVerdict([], solution.verdict, solution.score)

        verify_result: list[VerdictsVerifierResult] = []

        for subtask_name, subtask in subtask_list.items():
            outcome = self._get_tests_outcome(result.testcase_results, subtask.get_all_test_names()) # type: ignore
            score = outcome.score
            result_type = outcome.result
            verdict_count = outcome.counter

            subtask_rule = subtask_rules[subtask_name] if subtask_name in subtask_rules else default_subtask_rule
            verify_result.append(VerdictsVerifierResult(
                subtask_name, result_type, score, verdict_count,
                subtask_rule.score, subtask_rule.verdict
            ))
            self._check_verdict_rule(
                submission_file,
                f"Subtask {subtask_name}",
                set(verdict_count.keys()),
                subtask_rule.verdict
            )
            if not subtask_rule.score.check_score(score):
                self.add_issue("score_range", submission_file,
                                f"Subtask {subtask_name} score {score} violates the score range {subtask_rule.score}")

        # Overall outcome
        outcome = self._get_tests_outcome(
            result.testcase_results, 
            context.recipe.get_all_test_names()
        )
        score = outcome.score
        result_type = outcome.result
        verdict_count = outcome.counter
        verify_result.append(VerdictsVerifierResult(
            "Overall", result_type, score, verdict_count,
            default_subtask_rule.score if not subtask_list else ScoreRange(),
            default_subtask_rule.verdict if not subtask_list else VerdictRule()
        ))

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
        
        self._print_result_table(formatter, verify_result)
        

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
        
