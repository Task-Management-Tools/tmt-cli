#!/usr/bin/env python3
"""
Recipe Data Parser

This module parses a custom format file to generate recipe data structure objects.
The parsed data includes testsets, subtasks, and validation rules for programming contests.
"""

import copy
from dataclasses import dataclass
import functools
import inspect
import os
import re
from typing import Literal, overload


class Executable:
    """
    Represents an executable command with multiple programs to run sequentially and connected by pipes.

    Each executable contains a list of command lists, where each command list
    follows the subprocess format (executable name + arguments).
    """

    def __init__(self, commands: list[list[str]]):
        """
        Initialize executable with a list of command lists (one per pipeline stage).

        Args:
            commands: List of command lists, where each inner list contains
                      [command_name, arg1, arg2, ...]. Empty lists are not allowed.

        Raises:
            ValueError: If commands is empty or contains empty subcommands
        """
        if len(commands) == 0:
            raise ValueError("Executable command list should not be empty")
        for cmd in commands:
            if len(cmd) == 0:
                raise ValueError(
                    "Executable command list should not contain empty subcommands"
                )
        self.commands = commands

    def __eq__(self, other):
        if not isinstance(other, Executable):
            return NotImplementedError
        return self.commands == other.commands


class Validation(Executable):
    """Validation command; similar to Executable but only allows one subcommand."""

    def __init__(self, commands: list[list[str]]):
        if len(commands) > 1:
            raise ValueError("Validation command does not support piping")
        super().__init__(commands)


TESTCASE_NAME_PLACE_HOLDER = "_tmt_internal_testcase_name"


class Testcase:
    def __init__(self, exe: Executable):
        """Initialize testcase with an executable."""
        self._raw_execute: Executable = exe
        self.execute: Executable | None = None
        self.validation: list[Validation] = []
        self._name: str | None = None

    @property
    def name(self):
        """
        The name of a testcase. It *can* be set multiple times.
        """
        return self._name

    @name.setter
    def name(self, value: str):
        """
        Setter for test name of this command.
        Also replaces TESTCASE_NAME_PLACE_HOLDER in all commands with the actual test name.
        """
        self._name = value

        # Replace TESTCASE_NAME_PLACE_HOLDER with actual test name in all commands
        self.execute = copy.deepcopy(self._raw_execute)
        for command_list in self.execute.commands:
            for i, arg in enumerate(command_list):
                command_list[i] = arg.replace(TESTCASE_NAME_PLACE_HOLDER, value)

    def add_validation(self, validation: Validation):
        """
        Add a validation for this test case.
        """
        if validation not in self.validation:
            self.validation.append(validation)


class Testset:
    """
    Represents a set of test cases for problems.

    Contains metadata about the testset and a list of test generation commands.
    """

    def __init__(self, name: str):
        self.name: str = name
        self.index: int | None = None
        self.description: str | None = None
        self.validation: list[Validation] = []
        self.testcases: list[Testcase] = []
        self.dependency: list[Testset] = []
        self.extra_file: set[str] = set()

    def assign_index(self, index: int) -> int:
        """
        Indexes the testset and returns the next available index.
        """
        self.index = index
        return index + 1

    def add_validation(self, validation: Validation):
        if validation not in self.validation:
            self.validation.append(validation)

    def include_testset(self, testset: "Testset"):
        if testset is self:
            return
        for deps in testset.dependency + [testset]:
            if deps not in self.dependency:
                self.dependency.append(deps)

    def add_test(self, exe: Executable):
        """
        Add a test case from the generation Executable.
        """
        tc = Testcase(exe)
        self.testcases.append(tc)

    def set_description(self, description: str):
        """
        Set the description for this testset.

        Raises:
            ValueError: If description is already set
        """
        if self.description is not None:
            raise ValueError(f"Description already set for testset '{self.name}'")
        self.description = description

    def add_extrafile(self, extension: str):
        """
        Add an extra file for this testset. The extra file will be opened during the generation of this testset.

        Args:
            extension (str): Extra file extension, should start with a dot (.)

        Raises:
            ValueError: If the extension is already added
        """
        if extension in self.extra_file:
            raise ValueError(
                f"Extra file '{extension}' already added for testset '{self.name}'"
            )
        self.extra_file.add(extension)

    def generate_test_names(self, testset_index_width: int):
        """
        Generate standardized names for all test cases in this testset.
        """
        testcase_index_width = len(str(len(self.testcases)))
        testset_index_padded = str(self.index).zfill(testset_index_width)

        for i, test in enumerate(self.testcases, 1):
            testcase_index_padded = str(i).zfill(testcase_index_width)
            test.name = f"{testset_index_padded}_{self.name}_{testcase_index_padded}"

    def get_all_test_names(self) -> list[str]:
        """
        Get all test names in this testset, including dependencies.
        """

        return sum(
            ([tc.name for tc in ts.testcases] for ts in (self.dependency + [self])),
            start=[],
        )


class Subtask(Testset):
    """
    Represents a subtask in a problem.

    Contains scoring information, validation rules, and associated testsets.
    """

    def __init__(self, name: str, score: int):
        super().__init__(name)
        self.score: int = score

    def assign_index(self, index: int) -> int:
        """
        Indexes the subtask and returns the next available index.
        """
        if len(self.testcases):
            self.index = index
            return index + 1
        return index


class RecipeData:
    """
    Main container for all recipe data information.

    Includes testsets, subtasks, and global validation rules.
    """

    def __init__(self):
        self.testsets: dict[str, Testset | Subtask] = {}
        self.subtasks: dict[str, Subtask] = {}
        self.global_validation: list[Validation] = []

    def get_all_test_names(self) -> list[str]:
        """
        Get all test names based on recipe order.
        """
        # From Python 3.7+ dict is order-preserving
        all_names = []
        for testset in self.testsets.values():
            for test in testset.testcases:
                if test.name:
                    all_names.append(test.name)
        return all_names

    def generate_all_test_names(self):
        """
        Generate standardized names for all test cases across all testsets.
        This should be called after parsing is complete.
        """
        if not self.testsets:
            return

        # From Python 3.7+ dict is order-preserving, so no sorting
        i = 1
        for testset in self.testsets.values():
            i = testset.assign_index(i)

        max_testset_index = max(
            filter(None, (testset.index for testset in self.testsets.values())),
            default=0,  # This won't matter anyway, just to prevent ValueError
        )
        testset_index_width = len(str(max_testset_index))

        for testset in self.testsets.values():
            testset.generate_test_names(testset_index_width)

    def generate_testsetless_test_names(self):
        """
        Generate testsetless names for all test cases across all testsets.
        This is specially designed for OutputOnly tasks.
        This should be called after parsing is complete.
        """
        if not self.testsets:
            return

        testcase_cnt = 0
        for testset in self.testsets.values():
            testcase_cnt += len(testset.testcases)

        # Calculate the width needed for testset index padding
        testcase_index_width = len(str(testcase_cnt))

        i = 0
        for testset in self.testsets.values():
            for test in testset.testcases:
                test.name = str(i).zfill(testcase_index_width)
                i += 1

    def push_validation_to_testcases(self):
        """
        Let all test cases own their validations Executable
        This should be called after parsing is complete.
        """
        for testset in self.testsets.values():
            for validation in self.global_validation:
                testset.add_validation(validation)
            for depend in testset.dependency:
                for validation in testset.validation:
                    depend.add_validation(validation)

        for testset in self.testsets.values():
            for test in testset.testcases:
                for validation in testset.validation:
                    test.add_validation(validation)


class ParserContext:
    """
    Manages the parsing context and state during file processing.

    This class serves as a shared context for all handlers, allowing them
    to access and modify parsing state, share information, and store
    temporary data that doesn't belong in the final RecipeData object.
    """

    def __init__(self):
        self.recipe_data = RecipeData()
        self._scope: Testset | Subtask | None = None

        # For storing user-defined constants
        self.global_const: dict[str, str] = {}
        self.local_const: dict[str, str] = {}

    @property
    def scope(self):
        return self._scope

    @scope.setter
    def scope(self, value: Testset | Subtask | None):
        """Set current scope and clear local constants."""
        self._scope = value
        self.local_const.clear()

    @property
    def const_mapping(self):
        return self.global_const | self.local_const

    def set_constant(self, name: str, value: str):
        """Set a constant value."""

        target_const = self.local_const if self.scope is not None else self.global_const
        if name in target_const:
            raise ValueError(f"Redefinition on constant '{name}'")
        target_const[name] = value

    @overload
    def shell_split(self, cmdline: str, pipe_split: Literal[False]) -> list[str]: ...

    @overload
    def shell_split(
        self, cmdline: str, pipe_split: Literal[True]
    ) -> list[list[str]]: ...

    def substitute(self, text: str) -> str:
        """
        Replace ${constant} patterns with their values.

        Raises:
            ValueError: If a referenced constant is undefined
        """

        def replace_var(match: re.Match):
            var_name = match.group(1)
            var_val = self.const_mapping.get(var_name)
            # TODO: this abruptly stops the substitution; if multiple fails this only reports the first one
            if var_val is None:
                raise ValueError(f"Undefined constant '{var_name}'")
            return var_val

        # Replace ${constant_name} patterns
        return re.sub(r"\$\{([^}]+)\}", replace_var, text)

    def shell_split(self, cmdline: str, pipe_split: bool):
        """
        Tokenize a command line, supporting quotes and pipes.

        Handles double quotes ("..."), single quotes ('...'), unquoted pipes (|),
        and bare words. Constants are substituted in unquoted text only.

        Args:
            cmdline: Command line string to tokenize
            pipe_split: If True, split on pipes and return list of command lists.
                        If False, return flat list of tokens with '|' preserved.
        """
        cmdline = cmdline.strip() + " "
        cmds = []
        cmd = []
        # Python alternative (|) is eager, so the quoted alternatives always matches first if possible.
        for m in re.finditer(r"(?:\"([^\"]*)\"|\'([^\']*)\'|(\|)|(\S+))\s+", cmdline):
            if m.group(1) is not None:  # double-quoted
                cmd.append(self.substitute(m.group(1)))
            elif m.group(2) is not None:  # single-quoted
                cmd.append(m.group(2))
            elif m.group(3):  # unquoted pipe
                if pipe_split:
                    cmds.append(cmd)
                    cmd = []
                else:
                    cmd.append("|")
            else:  # bare word
                cmd.append(self.substitute(m.group(4)))
        cmds.append(cmd)
        return cmds if pipe_split else cmd

    def make_executable(self, cmdline: str, type: type[Executable] | type[Validation]):
        return type(self.shell_split(cmdline, pipe_split=True))


@dataclass
class RecipeParsingError:
    line_no: int
    reason: str

    def to_string(self, recipe_path: str):
        return f"{os.path.relpath(recipe_path, os.getcwd())}:{self.line_no}: error: {self.reason}"


class RecipeParser:
    def __init__(self):
        self.ctx = ParserContext()

        # Register all handlers marked by the decorator
        self.handlers = {
            obj._cmd_name: getattr(self, obj.__name__)
            for obj in self.__class__.__dict__.values()
            if callable(obj) and hasattr(obj, "_cmd_name")
        }

    def _register_command(name: str, preprocess=True):
        """
        Decorator to register command handlers with argument validation.

        Validates handler signature: rejects keyword-only and **kwargs params.
        Wraps handler to check argument count at runtime.

        Args:
            name: Command name (without @ prefix)
            preprocess: If True, shell-split arguments. If False, pass raw string after the command.
        """

        def decorator(func):
            # Count only parameters that are positional or positional-or-keyword
            params = inspect.signature(func).parameters.values()
            num_args = sum(
                1
                for p in params
                if p.kind
                in (
                    inspect.Parameter.POSITIONAL_ONLY,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                )
            )
            variadic = any(
                True for p in params if p.kind == inspect.Parameter.VAR_POSITIONAL
            )

            if any(
                True
                for p in params
                if p.kind
                in (inspect.Parameter.KEYWORD_ONLY, inspect.Parameter.VAR_KEYWORD)
            ):
                raise TypeError(
                    "Command handler registered must not have keyword-only parameter"
                )
            if not preprocess and num_args != 2:
                raise TypeError(
                    "Command handler registered without preprocessing must have exactly one positional parameter"
                )

            @functools.wraps(func)
            def wrapper(*args):
                # Also counts self as one of them, so diagnostics returns -1
                if len(args) < num_args:
                    raise ValueError(
                        f"@{name} requires at least {num_args - 1} argument(s)"
                    )
                if not variadic and len(args) != num_args:
                    raise ValueError(
                        f"@{name} requires exactly {num_args - 1} argument(s)"
                    )
                result = func(*args)
                return result

            wrapper._cmd_name = name
            wrapper.preprocess = preprocess
            return wrapper

        return decorator

    @_register_command("testset")
    def command_testset(self, name: str):

        if name in self.ctx.recipe_data.testsets.keys():
            raise ValueError(f"Testset name '{name}' already used")

        testset = Testset(name)
        self.ctx.recipe_data.testsets[name] = testset
        self.ctx.scope = testset

    @_register_command("subtask")
    def command_subtask(self, name: str, score_s: str):
        try:
            score = int(score_s)
        except ValueError:
            raise ValueError(f"Invalid score '{score_s}' for subtask")

        if name in self.ctx.recipe_data.testsets.keys():
            raise ValueError(f"Subtask name '{name}' already used")

        subtask = Subtask(name, score)
        self.ctx.recipe_data.testsets[name] = subtask
        self.ctx.recipe_data.subtasks[name] = subtask
        self.ctx.scope = subtask

    @_register_command("description", preprocess=False)
    def command_description(self, desc: str):
        if self.ctx.scope is None:
            raise ValueError(
                "@description can only be used within testset or subtask context"
            )

        desc = self.ctx.substitute(desc)
        self.ctx.scope.set_description(desc)

    @_register_command("include")
    def command_include(self, depend: str):

        if self.ctx.scope is None:
            raise ValueError(
                "@include can only be used within testset or subtask context"
            )

        testsets = self.ctx.recipe_data.testsets
        if depend in testsets.keys():
            self.ctx.scope.include_testset(testsets[depend])
        else:
            raise ValueError(f"Unknown testset or subtask name: '{depend}'")

    @_register_command("global_validation", preprocess=False)
    def command_global_validation(self, remain: str):
        val = self.ctx.make_executable(remain, Validation)
        self.ctx.recipe_data.global_validation.append(val)

    @_register_command("validation", preprocess=False)
    def command_validation(self, remain: str):

        if self.ctx.scope is None:
            raise ValueError(
                "@validation can only be used within testset or subtask context"
            )

        val = self.ctx.make_executable(remain, Validation)
        self.ctx.scope.add_validation(val)

    @_register_command("constant")
    def command_constant(self, name: str, value: str):
        self.ctx.set_constant(name, value)

    @_register_command("extra_file")
    def command_extra_file(self, name: str, ext: str):
        if self.ctx.scope is None:
            raise ValueError(
                "@extra_file can only be used within testset or subtask context"
            )
        if not ext.startswith("."):
            raise ValueError(f"Extra file {ext} should start with a dot (.)")

        self.ctx.scope.add_extrafile(ext)
        self.ctx.set_constant(name, TESTCASE_NAME_PLACE_HOLDER + ext)

    def parse(self, recipe_lines: str) -> list[RecipeParsingError]:
        errors = []
        for line_no, line in enumerate(recipe_lines, 1):
            # Remove comments
            line = line.partition("#")[0].strip()
            if not line:
                continue

            try:
                # Handle command lines starting with @
                if line.startswith("@"):
                    cmd, *args = line.split(maxsplit=1)
                    args = args[0] if args else ""

                    handler = self.handlers.get(cmd[1:])
                    if handler is None:
                        raise ValueError(f"Unknown command '{cmd}'")
                    if handler.preprocess:
                        handler(*self.ctx.shell_split(args, pipe_split=False))
                    else:
                        handler(args)

                else:
                    # Expand constants in test generation commands
                    exe = self.ctx.make_executable(line, Executable)
                    if self.ctx.scope is None:
                        raise ValueError(
                            "Stray generation command (not within any subtask or testset)"
                        )
                    self.ctx.scope.add_test(exe)

            except ValueError as e:
                errors.append(RecipeParsingError(line_no, str(e)))
        return errors


def parse_recipe_data(
    recipe_lines: list[str], is_outputonly: bool = False
) -> RecipeData | list[RecipeParsingError]:
    """
    Parse recipe and return the structured data.

    Args:
        recipe_lines (list of str): List of lines in a recipe file
        is_outputonly (bool):
            Whether the recipe is for OutputOnly tasks.
            In this case, the name of each testcase will not contain testset information.

    Returns:
        RecipeData: Parsed recipe data structure

    Raises:
        ValueError: If the recipe format is invalid
    """

    parser = RecipeParser()
    error = parser.parse(recipe_lines)
    if error:
        return error

    # Generate test names after parsing is complete
    if is_outputonly:
        parser.ctx.recipe_data.generate_testsetless_test_names()
    else:
        parser.ctx.recipe_data.generate_all_test_names()

    # Push validations to all test cases after parsing is complete
    parser.ctx.recipe_data.push_validation_to_testcases()

    return parser.ctx.recipe_data


if __name__ == "__main__":
    # Test the parser with sample data
    sample_data = """
@global_validation validator

@testset samples
manual s1.in
manual s2.in

@testset handmade
print 30 11 | swap
print 30 22 | swap
print 47 24
print 2147483647 1
print 2147483647 2147483647
manual 1.in

@subtask A 1
print 1 1

@subtask B 2
@include A
@include A

@subtask C 3
@include B
@include B

@subtask D 4
@include C
@include C

@subtask E 5
@include D
@include D

@subtask F 6
@include E
@include E

@subtask G 7
@include F
@include F

@subtask H 8
@validation validator
@include G
@include G
"""

    try:
        # Parse the sample data
        recipe_data = parse_recipe_data(sample_data.split("\n"))

        # Print parsed results
        print("=== TESTSETS ===")
        for name, testset in recipe_data.testsets.items():
            print(f"Testset '{name}' (index: {testset.index})")
            if len(testset.extra_file) != 0:
                print(f"  Extra files: {list(testset.extra_file)}")
            if testset.description:
                print(f"  Description: {testset.description}")
            print(f"  Tests: {len(testset.testcases)}")
            for i, test in enumerate(testset.testcases):
                print(
                    f"    Test {i + 1} (Name: {test.name}): {len(test.execute.commands)} commands"
                )
                for j, cmd in enumerate(test.execute.commands):
                    print(f"      Command {j + 1}: {cmd}")
                print(
                    f"      Validation for test {i + 1}: {len(test.validation)} validators"
                )
                for j, validation in enumerate(test.validation):
                    print(f"        Validator {j + 1}: {validation.commands}")

        print("\n=== GLOBAL VALIDATION ===")
        print(f"Global validation: {len(recipe_data.global_validation)} validators")
        for i, validation in enumerate(recipe_data.global_validation):
            print(f"  Global validation {i + 1}: {validation.commands}")

        print("\n=== SUBTASKS ===")
        for name, subtask in recipe_data.subtasks.items():
            print(f"Subtask '{name}' (index: {subtask.index}, score: {subtask.score})")
            if subtask.description:
                print(f"  Description: {subtask.description}")
            print(f"  Testsets: {subtask.dependency}")
            print(f"  Validation: {len(subtask.validation)} validators")
            for i, validation in enumerate(subtask.validation):
                print(f"    Validator {i + 1}: {validation.commands}")

        print("\nParsing completed successfully!")

    finally:
        pass
    # except Exception as e:
    #     print(f"Error: {e}")
    # print(shell_split("a | b '|' c", {}))
