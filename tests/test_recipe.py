import pathlib
import pytest
from typing import Callable
from dataclasses import dataclass

import internal.recipe_parser as rp
from internal.recipe_parser import parse_recipe_data


class CommandMatcher:
    def __init__(self, *args):
        self.cmds: list[list[str]]
        if len(args) == 0:
            self.cmds = [[]]
        elif all(
            isinstance(arg, list) and all(isinstance(x, str) for x in arg)
            for arg in args
        ):
            self.cmds = list(args)
        elif all(isinstance(arg, str) for arg in args):
            self.cmds = [list(args)]
        elif len(args) == 1:
            self.cmds = args[0]
        else:
            raise ValueError(f"Cannot construct CommandMatcher from {args}")

    def match(self, rhs):
        assert isinstance(rhs, rp.Command)
        assert self.cmds == rhs.commands

    @classmethod
    def list_match(cls, expect: list["CommandMatcher"], actual: list[rp.Command]):
        assert len(expect) == len(actual)
        expect.sort(key=lambda e: e.cmds)
        actual.sort(key=lambda e: e.commands)
        for expect_exe, actual_exe in zip(expect, actual):
            expect_exe.match(actual_exe)


class TestcaseMatcher:
    __test__ = False

    def __init__(
        self, name: str, gen: list[list[str]] | list[str], val: list[list[str]] | None
    ):
        self.name = name
        self.gen = CommandMatcher(gen)
        self.val = [CommandMatcher([v]) for v in val] if val else None

    def match(self, rhs):
        assert isinstance(rhs, rp.Testcase)
        assert self.name == rhs.name
        self.gen.match(rhs.execute)
        if self.val is not None:
            CommandMatcher.list_match(self.val, rhs.validation)

    @classmethod
    def list_match(cls, expect: list["TestcaseMatcher"], actual: list[rp.Testcase]):
        assert len(expect) == len(actual)
        expect.sort(key=lambda e: e.name)
        actual.sort(key=lambda e: e.name)
        for expect_exe, actual_exe in zip(expect, actual):
            expect_exe.match(actual_exe)


class TestsetMatcher:
    __test__ = False

    def __init__(self, name: str, index: int | None, desc: str | None):
        self.name = name
        self.index = index
        self.desc = desc
        self.validation: list[CommandMatcher] = []
        self.testcases: list[TestcaseMatcher] = []
        self.dependency: list["TestsetMatcher"] = []
        self.extra_file: list[str] = []

        self._already_matched: rp.Testset | None = None

    def val(self, *args):
        self.validation.append(CommandMatcher(*args))
        return self

    def testcase(
        self,
        name: str,
        gen: list[list[str]] | list[str],
        val: list[list[str]] | None = None,
    ):
        self.testcases.append(TestcaseMatcher(name=name, gen=gen, val=val))
        return self

    def depend(self, *testsets: "TestsetMatcher"):
        for ts in testsets:
            self.dependency.append(ts)
        return self

    def extra(self, file: str):
        self.extra_file.append(file)
        return self

    def match(self, rhs):
        assert isinstance(rhs, rp.Testset)
        assert self.name == rhs.name
        assert self.index == rhs.index
        assert self.desc == rhs.description
        CommandMatcher.list_match(self.validation, rhs.validation)
        TestcaseMatcher.list_match(self.testcases, rhs.testcases)
        TestsetMatcher.list_match(self.dependency, rhs.dependency)
        assert set(self.extra_file) == rhs.extra_file

        if self._already_matched is None:
            self._already_matched = rhs
        assert self._already_matched is rhs

    @classmethod
    def list_match(cls, expect: list["TestsetMatcher"], actual: list[rp.Testset]):
        assert len(expect) == len(actual)
        expect.sort(key=lambda e: e.name)
        actual.sort(key=lambda e: e.name)
        for expect_exe, actual_exe in zip(expect, actual):
            expect_exe.match(actual_exe)


class SubtaskMatcher(TestsetMatcher):
    def __init__(self, name: str, index: int | None, desc: str | None, score: float):
        super().__init__(name, index, desc)
        self.score = score

    def match(self, rhs):
        assert isinstance(rhs, rp.Subtask)
        super().match(rhs)
        assert self.score == rhs.score


@dataclass(frozen=True)
class RecipeMatcher:
    testsets: list[TestsetMatcher]
    global_val: list[CommandMatcher]

    def match(self, rhs):
        assert isinstance(rhs, rp.RecipeData)
        TestsetMatcher.list_match(self.testsets, list(rhs.testsets.values()))
        TestsetMatcher.list_match(
            [s for s in self.testsets if isinstance(s, SubtaskMatcher)],
            [s for s in rhs.testsets.values() if isinstance(s, rp.Subtask)],
        )
        CommandMatcher.list_match(self.global_val, rhs.global_validation)


# fmt: off
def complex_recipe_result():
    t1 = (TestsetMatcher(name="t1", index=1, desc=None)
          .val("validator", "--N=100")
          .val("validator", "--N=2000")
          .val("validator", "--N=200000")
          .val("validator-tester")
          .testcase("1_t1_1", gen=["gen", "--N=100", "seed=1"])
          .testcase("1_t1_2", gen=["gen", "--N=100", "seed=2"]))

    t2 = (TestsetMatcher(name="t2", index=2, desc=None)
          .val("validator", "--N=2000")
          .val("validator", "--N=200000")
          .val("validator-tester")
          .testcase("2_t2_1", gen=["gen", "--N=2000", "seed=1"])
          .testcase("2_t2_2", gen=["gen", "--N=2000", "seed=2"]))

    edge = (TestsetMatcher(name="edge_case", index=3, desc="edge cases for N <= 100")
            .val("validator", "--N=100")
            .val("validator", "--N=2000")
            .val("validator", "--N=200000")
            .val("validator-tester")
            .testcase("3_edge_case_1", gen=["special", "--N=1", "--note=3_edge_case_1.note"])
            .testcase("3_edge_case_2", gen=["special", "--N=2", "--note=3_edge_case_2.note"])
            .testcase("3_edge_case_3", gen=[["gen", "--N=100", "seed=1"], ["make_extreme"]])
            .extra(".note"))

    s1 = (SubtaskMatcher(name="s1", index=4, desc="$N \\leq 100$", score=20)
          .val("validator", "--N=100")
          .val("validator", "--N=2000")
          .val("validator", "--N=200000")
          .val("validator-tester")
          .testcase("4_s1_1", gen=["extra", "--N=5", "--note=4_s1_1.note", "seed=1"])
          .depend(t1, edge)
          .extra(".note"))

    s2 = (SubtaskMatcher(name="s2", index=None, desc="$N \\leq 2000$", score=30)
          .val("validator", "--N=2000")
          .val("validator", "--N=200000")
          .val("validator-tester")
          .depend(t1, t2, edge, s1))

    s3 = (SubtaskMatcher(name="s3", index=5, desc="No additional constraints", score=50)
          .val("validator", "--N=200000")
          .val("validator-tester")
          .testcase("5_s3_1", gen=["gen", "--N=200000", "seed=1"])
          .testcase("5_s3_2", gen=["gen", "--N=200000", "seed=2"])
          .depend(t1, t2, edge, s1, s2))

    return RecipeMatcher([t1, t2, edge, s1, s2, s3],
                         [CommandMatcher("validator", "--N=200000"),
                          CommandMatcher("validator-tester")])

def diamond_recipe_result():
    a = (TestsetMatcher(name="A", index=1, desc=None)
         .val("val")
         .testcase("1_A_1", gen=["gen"], val=[["val"]]))

    b = (TestsetMatcher(name="B", index=2, desc=None)
         .val("val")
         .depend(a))

    c = (TestsetMatcher(name="C", index=3, desc=None)
         .val("val")
         .depend(a))

    d = (SubtaskMatcher(name="D", index=None, desc=None, score=100)
         .val("val")
         .depend(a, b, c))

    return RecipeMatcher([a, b, c, d], [])


def cursed_recipe_result():
    a = (TestsetMatcher(name="space-> <-space", index=1, desc=None)
         .val("|", "  ", "")
         .testcase("1_space-> <-space_1", gen=[["|"], ["| |", '"'], ["|", "|", "'", "'abcdef"]])
         .testcase("1_space-> <-space_2", gen=[["gen", '#'], ["gen", '#']]))

    return RecipeMatcher([a], [])
# fmt: on


@pytest.mark.parametrize(
    "recipe_path, expected",
    [
        ("recipes/complex.recipe", complex_recipe_result),
        ("recipes/diamond.recipe", diamond_recipe_result),
        ("recipes/cursed.recipe", cursed_recipe_result),
    ],
)
def test_recipe(
    recipe_path: str,
    expected: Callable[[], RecipeMatcher],
):
    problem_dir = pathlib.Path(__file__).parent.resolve() / recipe_path
    with open(problem_dir, "r") as f:
        recipe = parse_recipe_data(f.readlines())
    expected().match(recipe)


def parse_invalid_recipes():

    path = pathlib.Path(__file__).parent.resolve() / "recipes/invalid.recipe"
    lines = path.read_text().splitlines(keepends=True)

    recipes = {}
    current_name, current_lines = None, []

    for line in lines:
        if line.startswith("#!pytest"):
            if current_name is not None:
                recipes[current_name] = current_lines
            parts = line.split(maxsplit=1)
            if len(parts) == 1:
                raise ValueError(f"invalid.recipe: test has no name: {line!r}")
            current_name = parts[1].strip()
            if current_name in recipes:
                raise ValueError(
                    f"invalid.recipe: duplicate test name: {current_name!r}"
                )
            current_lines = []
        else:
            current_lines.append(line)

    if current_name is not None:
        recipes[current_name] = current_lines
    return recipes


@pytest.mark.parametrize(
    "recipe_content",
    [pytest.param(v, id=k) for k, v in parse_invalid_recipes().items()],
)
def test_failing_recipe(recipe_content: list[str]):
    recipe = parse_recipe_data(recipe_content)
    print(recipe)
    assert not isinstance(recipe, rp.RecipeData)
