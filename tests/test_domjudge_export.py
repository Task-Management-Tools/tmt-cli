import os
import pathlib
import zipfile

import pytest

from internal.commands.clean import command_clean
from internal.commands.export import command_export
from internal.commands.gen import command_gen
from internal.context import TMTContext
from internal.exporters import DOMJudgeLegacyExporter
from internal.formatting import TerminalFormatter

# Expected result: dict[file path, sha256sum]
# fmt: off
expected_result_batch_floatcmp = {
    "problem.yaml":                                 "_expected_export/problem.yaml",
    ".timelimit":                                   "_expected_export/.timelimit",
    "data/secret/1-full-1.in":                      "testcases/1-full-1.in",
    "data/secret/1-full-1.ans":                     "testcases/1-full-1.out",
    "submissions/accepted/model-solution.cpp":      "solutions/model-solution.cpp",
    "submissions/accepted/exact.cpp":               "solutions/exact.cpp",
    "submissions/wrong_answer/no-setprecision.cpp": "solutions/no-setprecision.cpp",
    "submissions/wrong_answer/abs1e-4.cpp":         "solutions/abs1e-4.cpp",
    "submissions/accepted/abs1e-6.cpp":             "solutions/abs1e-6.cpp",
    "submissions/accepted/abs1e-7.cpp":             "solutions/abs1e-7.cpp",
    "submissions/wrong_answer/rel1e-4.cpp":         "solutions/rel1e-4.cpp",
    "submissions/accepted/rel1e-6.cpp":             "solutions/rel1e-6.cpp",
    "submissions/accepted/rel1e-7.cpp":             "solutions/rel1e-7.cpp",
    "input_validators/validator.cpp":               "validator/validator.cpp",
    "problem_statement/problem.pdf":                "statement/problem.pdf",
}
expected_result_batch_checker = {
    "problem.yaml":                                 "_expected_export/problem.yaml",
    ".timelimit":                                   "_expected_export/.timelimit",
    "data/sample/1-samples-1.in":                   "testcases/1-samples-1.in",
    "data/sample/1-samples-1.ans":                  "testcases/1-samples-1.out",
    "data/secret/2-full-1.in":                      "testcases/2-full-1.in",
    "data/secret/2-full-1.ans":                     "testcases/2-full-1.out",
    "submissions/accepted/model-solution.cpp":      "solutions/model-solution.cpp",
    "submissions/accepted/alt.py":                  "solutions/alt.py",
    "submissions/wrong_answer/wrong.cpp":           "solutions/wrong.cpp",
    "output_validators/checker.cpp":                "checker/checker.cpp",
    "output_validators/header.h":                   "include/header.h",
    "problem_statement/problem.pdf":                "statement/problem.pdf",
}
expected_result_interactive_guess = {
    "problem.yaml":                                 "_expected_export/problem.yaml",
    ".timelimit":                                   "_expected_export/.timelimit",
    "data/secret/1-full-1.in":                      "testcases/1-full-1.in",
    "data/secret/1-full-1.ans":                     "testcases/1-full-1.out",
    "data/secret/1-full-2.in":                      "testcases/1-full-2.in",
    "data/secret/1-full-2.ans":                     "testcases/1-full-2.out",
    "data/secret/1-full-3.in":                      "testcases/1-full-3.in",
    "data/secret/1-full-3.ans":                     "testcases/1-full-3.out",
    "submissions/accepted/sol.cpp":                 "solutions/sol.cpp",
    "submissions/wrong_answer/brute.cpp":           "solutions/brute.cpp",
    "submissions/wrong_answer/exit.cpp":            "solutions/exit.cpp",
    "submissions/time_limit_exceeded/no-flush.cpp": "solutions/no-flush.cpp",
    "submissions/time_limit_exceeded/sleep.cpp":    "solutions/sleep.cpp",
    "output_validators/checker.cc":                 "interactor/checker.cc",
    "input_validators/validator.cpp":               "validator/validator.cpp",
}
# fmt: on


@pytest.mark.parametrize(
    "problem_path, file_mapping",
    [
        ("problems/batch/icpc-default-floatcmp", expected_result_batch_floatcmp),
        ("problems/batch/icpc-checker-export", expected_result_batch_checker),
        ("problems/interactive/guess", expected_result_interactive_guess),
    ],
)
def test_domjudge_export(
    problem_path: str,
    file_mapping: dict[str, str],
):
    script_dir = pathlib.Path(__file__).parent.parent.resolve()
    problem_dir = pathlib.Path(__file__).parent.resolve() / problem_path
    formatter = TerminalFormatter()
    context = TMTContext(str(problem_dir), str(script_dir))

    export_path = problem_dir / "archive.zip"
    command_clean(formatter=formatter, context=context, skip_confirm=True)
    command_gen(
        formatter=formatter, context=context, verify_hash=False, show_reason=False
    )
    try:
        command_export(
            formatter=formatter,
            context=context,
            output_path=str(export_path),
            package_format=DOMJudgeLegacyExporter,
            force_output=False,
        )

        checklist = dict(file_mapping)
        with zipfile.ZipFile(export_path, "r") as f:
            for file in f.filelist:
                path = os.path.normpath(file.filename)
                if path not in checklist:
                    raise AssertionError(f"Extra file in exported archive: {path}")

                with open(problem_dir / checklist.pop(path), "rb") as rf:
                    expected_content = rf.read()
                actual_content = f.read(path)
                if actual_content != expected_content:
                    raise AssertionError(
                        f"File content mismatch: {path} has {actual_content.decode()}, "
                        f"expecting {expected_content.decode()}"
                    )

        if checklist:
            raise AssertionError(f"Missing file(s): {', '.join(checklist.keys())}")

    finally:
        export_path.unlink()
