from collections import Counter
from itertools import count
import os

from internal.verdicts import Verdict, VerdictRule, parse_verdicts
from internal.formatting import Formatter, EmptyFormatter
from internal.context import TMTContext
from internal.commands import command_invoke
from internal.outcomes import EvaluationOutcome, EvaluationResult

def command_verify(
    *,
    formatter: Formatter,
    context: TMTContext,
):
    """
    Check issues.
    """
    verify_solutions(formatter=formatter, context=context)

def verify_solutions(
    *,
    formatter: Formatter,
    context: TMTContext
):
    solutions = parse_verdicts(context)
    path_helper = context.path

    def get_tests_outcome(
            results: dict[str, EvaluationResult | None],
            tests: list[str] | set[str],
    ) -> tuple[float, str, Counter[Verdict]]:
        counter = Counter[Verdict]()
        score = 1.0
        for testcase in tests:
            result = results[testcase]
            if not result:
                counter[Verdict.UNKNOWN] += 1
                score = min(score, 0.0)
            else:
                counter[Verdict.from_evaluation_outcome(result.verdict)] += 1
                score = min(score, result.score)
        incorrect = False
        partial = False
        for verdict in counter:
            if verdict == Verdict.PARTIAL:
                partial = True
            if verdict not in [Verdict.PARTIAL, Verdict.ACCEPTED]:
                incorrect = True
        result_str = "Incorrect" if incorrect else "Partial" if partial else "Correct"
        return score, result_str, counter
                
    def check_verdict_rule(
            name: str,
            verdicts: set[Verdict],
            rules: list[VerdictRule],
    ) -> list[str]:
        err_msg = []
        for rule in rules:
            if not rule.check_rule(verdicts):
                err_msg.append(f"{name} violates verdict rule {rule}")
        return err_msg

    default_rules: list[VerdictRule] = [
        VerdictRule(never=[Verdict.JUDGE_ERROR,
                           Verdict.TIME_LIMIT_EXCEEDED_WALL,
                           Verdict.UNKNOWN]),
    ]

    for solution in solutions:
        submission_file = os.path.join(path_helper.solutions, solution.filename)

        formatter.println()
        formatter.println(f"Solution {solution.filename}:")
        result = command_invoke(
            formatter=EmptyFormatter(),
            context=context,
            submission_files=[submission_file],
            show_reason=False
        )

        subtask_list = context.recipe.subtasks
        max_subtask_len = len("Subtask")
        for subtask in subtask_list:
            max_subtask_len = max(max_subtask_len, len(subtask))
        max_subtask_len += 1
        result_len = len("Incorrect") + 1
        score_num_len = len("100.00") + 1
        score_percent_len = len("(100%)") + 1
        score_len = score_num_len + score_percent_len

        formatter.print_fixed_width("Subtask", width=max_subtask_len)
        formatter.print_fixed_width("Result", width=result_len)
        formatter.print_fixed_width("Score", width=score_len)
        formatter.println("Verdicts")
        formatter.println("-" * (max_subtask_len + result_len + score_len + 20))
        def print_row(subtask_name, result_str, score_num, score_percent, verdict_count: Counter[Verdict]):
            formatter.print_fixed_width(subtask_name, width=max_subtask_len)
            formatter.print_fixed_width(result_str, width=result_len)
            formatter.print_fixed_width(f"{round(score_num, 2)}", width=score_num_len)
            formatter.print_fixed_width(f"({round(score_percent * 100)}%)", width=score_percent_len)
            formatter.println(', '.join([f"{verdict}*{count}" for verdict, count in verdict_count.items()]))

        subtask_rules: dict[str, list[VerdictRule]] = dict()
        for subtask_verdict in solution.subtask:
            for subtask in subtask_verdict.subtask:
                subtask_rules[subtask] = subtask_verdict.verdict

        max_score = 0
        verify_fail_msg: list[str] = []
        for subtask_name, subtask in subtask_list.items():
            max_score += subtask.score
            score, result_str, verdict_count = get_tests_outcome(result.testcase_results, subtask.get_all_test_names())
            score_num = score * subtask.score
            score_percent = score
            print_row(subtask_name, result_str, score_num, score_percent, verdict_count)
            verify_fail_msg += check_verdict_rule(
                f"Subtask {subtask_name}",
                set(verdict_count.keys()),
                subtask_rules[subtask_name] if subtask_name in subtask_rules else solution.verdict + default_rules
            )
        formatter.println("-" * (max_subtask_len + result_len + score_len + 20))

        score, result_str, verdict_count = get_tests_outcome(
            result.testcase_results, 
            context.recipe.get_all_test_names()
        )
        print_row("Overall", result_str, score * max_score, score, verdict_count)

        verify_fail_msg += check_verdict_rule(
            "Overall result",
            set(verdict_count.keys()), 
            solution.verdict + default_rules,
        )
        if verify_fail_msg:
            for msg in verify_fail_msg:
                formatter.println(msg)
