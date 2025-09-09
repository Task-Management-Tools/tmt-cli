#!/usr/bin/env python3
"""
Recipe Data Parser

This module parses a custom format file to generate recipe data structure objects.
The parsed data includes testsets, subtasks, and validation rules for programming contests.
"""

import re
from typing import Dict, List, Set, Optional


class Executable:
    """
    Represents an executable command with multiple programs to run sequentially.

    Each executable contains a list of command lists, where each command list
    follows the subprocess format (executable name + arguments).
    """

    def __init__(self, command_sequence: str):
        self.commands: List[List[str]] = []

        """
        Parse and add a command sequence separated by pipes.
        
        Args:
            command_sequence (str): Commands separated by '|' character
            
        Raises:
            ValueError: If command sequence is empty or malformed
        """
        if not command_sequence.strip():
            raise ValueError("Command sequence cannot be empty")

        # Split by pipe and process each command
        commands = command_sequence.split("|")
        for cmd in commands:
            cmd = cmd.strip()
            if not cmd:
                raise ValueError("Empty command found in sequence")

            # Split command into executable and arguments
            parts = cmd.split()
            if not parts:
                raise ValueError("Invalid command format")

            executable_name = parts[0]
            command_list = [executable_name] + parts[1:]
            self.commands.append(command_list)


class Testcase:
    """
    Represents a test case.

    Each test case contains an Executable object and its name
    """

    def __init__(self, command_sequence: str):
        self.execute: Executable = Executable(command_sequence)
        self.validation: List[Executable] = []
        self.test_name: Optional[str] = None  # Added for naming functionality

    def set_test_name(self, test_name: str):
        """
        Set the standardized test name for this executable.
        Also replaces '_tmt_internal_testcase_name' in all commands with the actual test name.

        Args:
            test_name (str): Standardized test name
        """
        self.test_name = test_name

        # Replace '_tmt_internal_testcase_name' with actual test name in all commands
        for command_list in self.execute.commands:
            for i, arg in enumerate(command_list):
                if "_tmt_internal_testcase_name" in arg:
                    command_list[i] = arg.replace(
                        "_tmt_internal_testcase_name", test_name
                    )

    def add_validation(self, validation: Executable):
        """
        Add a validation Executable object for this test case.

        Args:
            validation (Executable): An Executable object representing a validation
        """
        self.validation.append(validation)


class Testset:
    """
    Represents a set of test cases for problems.

    Contains metadata about the testset and a list of test generation commands.
    """

    def __init__(self, testset_name: str, testset_index: int):
        self.testset_name: str = testset_name
        self.testset_index: int = testset_index
        self.description: Optional[str] = None
        self.validation: List[Executable] = []
        self.tests: List[Testcase] = []
        self.extra_file: Set[str] = set()

    def add_validation(self, command: str, *args):
        """
        Add a validation command for this testset.

        Args:
            command (str): Validation executable name
            *args: Arguments for the validation command
        """
        try:
            command_sequence = f"{command} {' '.join(args)}"
            executable = Executable(command_sequence)
            self.validation.append(executable)
        except ValueError as e:
            raise ValueError(
                f"Error adding validation to testset '{self.testset_name}': {e}"
            )

    def add_test(self, command_sequence: str):
        """
        Add a test case by parsing the command sequence.

        Args:
            command_sequence (str): Command sequence to generate test data
        """
        try:
            self.tests.append(Testcase(command_sequence))
        except ValueError as e:
            raise ValueError(f"Error adding test to testset '{self.testset_name}': {e}")

    def set_description(self, description: str):
        """
        Set the description for this testset.

        Args:
            description (str): Description text

        Raises:
            ValueError: If description is already set
        """
        if self.description is not None:
            raise ValueError(
                f"Description already set for testset '{self.testset_name}'"
            )
        self.description = description

    def add_extrafile(self, extension: str):
        """
        Add an extra file for this testset. The extra file will be opened during the generation of this testset.

        Args:
            extension (str): Extra file extension, should start with a dot (.)

        Raises:
            ValueError: If the extension format error or it is already added
        """
        if len(extension) == 0 or extension[0] != ".":
            raise ValueError(f"Extra file {extension} should start with a dot (.)")
        if extension in self.extra_file:
            raise ValueError(
                f"Extra file {extension} already added for testset '{self.testset_name}'"
            )
        self.extra_file.add(extension)

    def generate_test_names(self, testset_index_width: int):
        """
        Generate standardized names for all test cases in this testset.

        Args:
            testset_index_width (int): Width for zero-padding testset index
        """
        testcase_index_width = len(str(len(self.tests)))
        testset_index_padded = str(self.testset_index).zfill(testset_index_width)

        for i, test in enumerate(self.tests, 1):
            testcase_index_padded = str(i).zfill(testcase_index_width)
            test_name = (
                f"{testset_index_padded}_{self.testset_name}_{testcase_index_padded}"
            )
            test.set_test_name(test_name)


class Subtask:
    """
    Represents a subtask in a problem.

    Contains scoring information, validation rules, and associated testsets.
    """

    def __init__(self, subtask_name: str, subtask_index: int, score: int):
        self.subtask_name: str = subtask_name
        self.subtask_index: int = subtask_index
        self.score: int = score
        self.description: str | None = None
        self.validation: List[Executable] = []
        self.tests: Set[str] = set()
        self.independent_testset: Testset | None = None

    def add_validation(self, command: str, *args):
        """
        Add a validation command for this subtask.

        Args:
            command (str): Validation executable name
            *args: Arguments for the validation command
        """
        try:
            command_sequence = f"{command} {' '.join(args)}"
            executable = Executable(command_sequence)
            self.validation.append(executable)
        except ValueError as e:
            raise ValueError(
                f"Error adding validation to subtask '{self.subtask_name}': {e}"
            )

    def include_testset(self, testset_name: str):
        """
        Include a testset in this subtask.

        Args:
            testset_name (str): Name of the testset to include
        """
        self.tests.add(testset_name)

    def set_description(self, description: str):
        """
        Set the description for this subtask.

        Args:
            description (str): Description text

        Raises:
            ValueError: If description is already set
        """
        if self.description is not None:
            raise ValueError(
                f"Description already set for subtask '{self.subtask_name}'"
            )
        self.description = description

    def set_independent_testset(self, context: "ParserContext"):
        """
        Set an independent testset for this subtask.

        Args:
            context (ParserContext): Current parser context

        Raises:
            ValueError: If the independent testset is already set
        """
        if self.independent_testset is not None:
            raise ValueError(
                f"Independent testset already set for subtask '{self.subtask_name}'"
            )
        self.independent_testset = Testset(self.subtask_name, context.testset_counter)
        context.recipe_data.testsets[self.subtask_name] = self.independent_testset
        self.tests.add(self.subtask_name)
        context.testset_counter += 1

    def add_test(self, command_sequence: str):
        """
        Add a test case into self.independent_testset by parsing the command sequence.

        Args:
            command_sequence (str): Command sequence to generate test data

        Raises:
            ValueError: If the independent testset is not set
        """
        if self.independent_testset is None:
            raise ValueError(
                f"Independent testset is not set for subtask '{self.subtask_name}'"
            )
        self.independent_testset.add_test(command_sequence)

    def add_extrafile(self, extension: str):
        """
        Add an extra file for self.independent_testset.

        Args:
            extension (str): Extra file extension, should start with a dot (.)
        """
        if self.independent_testset is None:
            raise ValueError(
                f"Independent testset is not set for subtask '{self.subtask_name}'"
            )
        self.independent_testset.extra_file.add(extension)


class RecipeData:
    """
    Main container for all recipe data information.

    Includes testsets, subtasks, and global validation rules.
    """

    def __init__(self):
        self.testsets: Dict[str, Testset] = {}
        self.subtasks: Dict[str, Subtask] = {}
        self.global_validation: List[Executable] = []

    def get_all_test_names(self) -> List[str]:
        """
        Get all test names in order.

        Returns:
            List[str]: List of all test names sorted by testset index and testcase index
        """
        all_names = []

        # Sort testsets by index
        sorted_testsets = sorted(
            self.testsets.values(), key=lambda ts: ts.testset_index
        )

        for testset in sorted_testsets:
            for test in testset.tests:
                if test.test_name:
                    all_names.append(test.test_name)

        return all_names

    def generate_all_test_names(self):
        """
        Generate standardized names for all test cases across all testsets.
        This should be called after parsing is complete.
        """
        if not self.testsets:
            return

        # Calculate the width needed for testset index padding
        max_testset_index = max(
            testset.testset_index for testset in self.testsets.values()
        )
        testset_index_width = len(str(max_testset_index))

        # Generate names for each testset
        for testset in self.testsets.values():
            testset.generate_test_names(testset_index_width)

    def push_validation_to_testcases(self):
        """
        Let all test cases own their validations Executable
        This should be called after parsing is complete.
        """
        for testset in self.testsets.values():
            for test in testset.tests:
                for validation in testset.validation:
                    test.add_validation(validation)
        for subtask in self.subtasks.values():
            for testset in subtask.tests:
                for test in self.testsets[testset].tests:
                    for validation in subtask.validation:
                        test.add_validation(validation)
        for testset in self.testsets.values():
            for test in testset.tests:
                for validation in self.global_validation:
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
        self.current_context = None
        self.current_object = None
        self.testset_counter = 1  # 1-based counter
        self.subtask_counter = 1  # 1-based counter
        self.used_names = set()

        # Shared data storage for inter-handler communication
        self.constants = {}  # For storing user-defined constants

    def get_constant(self, name: str, default=None):
        """
        Get a constant value by name.

        Args:
            name (str): Constant name
            default: Default value if constant doesn't exist

        Returns:
            Constant value or default
        """
        return self.constants.get(name, default)

    def set_constant(self, name: str, value):
        """
        Set a constant value.

        Args:
            name (str): Constant name
            value: Constant value
        """
        if self.has_constant(name) and self.constants[name] != value:
            raise ValueError(f"Redefinition on constant {name}")
        self.constants[name] = value

    def has_constant(self, name: str) -> bool:
        """
        Check if a constant exists.

        Args:
            name (str): Constant name

        Returns:
            bool: True if constant exists
        """
        return name in self.constants

    def expand_constants(self, text: str) -> str:
        """
        Expand constants in text using ${constant_name} syntax.

        Args:
            text (str): Text potentially containing constant references

        Returns:
            str: Text with constants expanded

        Raises:
            ValueError: If referenced constant doesn't exist
        """

        def replace_var(match):
            var_name = match.group(1)
            if not self.has_constant(var_name):
                raise ValueError(f"Undefined constant: ${{{var_name}}}")
            return str(self.constants[var_name])

        # Replace ${constant_name} patterns
        return re.sub(r"\$\{([^}]+)\}", replace_var, text)

    def list_expand_constants(self, list_of_text: List[str]):
        """
        Expand constants in list of text using ${constant_name} syntax.

        Args:
            list_of_text (list of str): List of text potentially containing constant references

        Raises:
            ValueError: If referenced constant doesn't exist
        """
        for i, s in enumerate(list_of_text):
            list_of_text[i] = self.expand_constants(s)

    def next_testset_index(self) -> int:
        """
        Get the next testset index and increment counter.

        Returns:
            int: Current testset index (1-based)
        """
        current = self.testset_counter
        self.testset_counter += 1
        return current

    def next_subtask_index(self) -> int:
        """
        Get the next subtask index and increment counter.

        Returns:
            int: Current subtask index (1-based)
        """
        current = self.subtask_counter
        self.subtask_counter += 1
        return current


class CommandHandler:
    """
    Base class for handling different types of commands.
    """

    def __init__(self, parser_context: ParserContext):
        self.context = parser_context

    def validate_args(
        self, parts: List[str], min_args: int, max_args: int | None = None
    ):
        """
        Validate the number of arguments for a command.

        Args:
            parts (List[str]): Command parts including the command name
            min_args (int): Minimum number of arguments (excluding command name)
            max_args (int, optional): Maximum number of arguments
        """
        arg_count = len(parts) - 1
        if arg_count < min_args:
            raise ValueError(f"@{parts[0]} requires at least {min_args} argument(s)")
        if max_args is not None and arg_count > max_args:
            raise ValueError(f"@{parts[0]} requires at most {max_args} argument(s)")

    def handle(self, parts: List[str]):
        """
        Handle the command. Must be implemented by subclasses.

        Args:
            parts (List[str]): Command parts including the command name
        """
        raise NotImplementedError


class TestsetHandler(CommandHandler):
    """Handler for @testset commands."""

    def handle(self, parts: List[str]):
        self.validate_args(parts, 1, 1)

        testset_name = parts[1]
        if testset_name in self.context.used_names:
            raise ValueError(f"Name '{testset_name}' already used")

        self.context.used_names.add(testset_name)
        testset = Testset(testset_name, self.context.testset_counter)
        self.context.recipe_data.testsets[testset_name] = testset
        self.context.current_context = "testset"
        self.context.current_object = testset
        self.context.testset_counter += 1


class SubtaskHandler(CommandHandler):
    """Handler for @subtask commands."""

    def handle(self, parts: List[str]):
        self.validate_args(parts, 2, 2)

        subtask_name = parts[1]
        if subtask_name in self.context.used_names:
            raise ValueError(f"Name '{subtask_name}' already used")

        try:
            score = int(parts[2])
        except ValueError:
            raise ValueError(f"Invalid score '{parts[2]}' for subtask")

        self.context.used_names.add(subtask_name)
        subtask = Subtask(subtask_name, self.context.subtask_counter, score)
        self.context.recipe_data.subtasks[subtask_name] = subtask
        self.context.current_context = "subtask"
        self.context.current_object = subtask
        self.context.subtask_counter += 1


class GlobalValidationHandler(CommandHandler):
    """Handler for @global_validation commands."""

    def handle(self, parts: List[str]):
        self.validate_args(parts, 1)

        self.context.list_expand_constants(parts)
        command_sequence = " ".join(parts[1:])
        executable = Executable(command_sequence)
        self.context.recipe_data.global_validation.append(executable)
        self.context.current_context = None
        self.context.current_object = None


class DescriptionHandler(CommandHandler):
    """Handler for @description commands."""

    def handle(self, parts: List[str]):
        self.validate_args(parts, 1)

        if self.context.current_context is None:
            raise ValueError(
                "@description can only be used within testset or subtask context"
            )

        self.context.list_expand_constants(parts)
        description = " ".join(parts[1:])
        self.context.current_object.set_description(description)


class IncludeHandler(CommandHandler):
    """Handler for @include commands."""

    def handle(self, parts: List[str]):
        self.validate_args(parts, 1, 1)

        if self.context.current_context != "subtask":
            raise ValueError("@include can only be used within subtask context")

        include_name = parts[1]

        # Check if it's a testset or subtask
        if include_name in self.context.recipe_data.testsets:
            self.context.current_object.include_testset(include_name)
        elif include_name in self.context.recipe_data.subtasks:
            # Include all testsets from the referenced subtask
            referenced_subtask = self.context.recipe_data.subtasks[include_name]
            for testset_name in referenced_subtask.tests:
                self.context.current_object.include_testset(testset_name)
        else:
            raise ValueError(f"Unknown testset or subtask name: '{include_name}'")


class ValidationHandler(CommandHandler):
    """Handler for @validation commands."""

    def handle(self, parts: List[str]):
        self.validate_args(parts, 1)

        if self.context.current_context not in ("testset", "subtask"):
            raise ValueError(
                "@validation can only be used within testset or subtask context"
            )

        self.context.list_expand_constants(parts)
        self.context.current_object.add_validation(parts[1], *parts[2:])


class ConstantHandler(CommandHandler):
    """Handler for @constant commands."""

    def handle(self, parts: List[str]):
        self.validate_args(parts, 2, 2)

        self.context.set_constant(parts[1], parts[2])


class ExtrafileHandler(CommandHandler):
    """Handler for @extra_file commands."""

    def handle(self, parts: List[str]):
        self.validate_args(parts, 2, 2)

        if self.context.current_context not in ("testset", "subtask"):
            raise ValueError(
                "@extra_file can only be used within testset or subtask context"
            )

        if (
            self.context.current_context == "subtask"
            and self.context.current_object.independent_testset is None
        ):
            self.context.current_object.set_independent_testset(self.context)

        self.context.current_object.add_extrafile(parts[2])
        self.context.set_constant(parts[1], "_tmt_internal_testcase_name" + parts[2])


class CommandRegistry:
    """
    Registry for all available command handlers.
    """

    def __init__(self, parser_context: ParserContext):
        self.handlers = {
            "testset": TestsetHandler(parser_context),
            "subtask": SubtaskHandler(parser_context),
            "global_validation": GlobalValidationHandler(parser_context),
            "description": DescriptionHandler(parser_context),
            "include": IncludeHandler(parser_context),
            "validation": ValidationHandler(parser_context),
            "constant": ConstantHandler(parser_context),
            "extra_file": ExtrafileHandler(parser_context),
        }

    def get_handler(self, command: str) -> CommandHandler:
        """
        Get the handler for a specific command.

        Args:
            command (str): Command name

        Returns:
            CommandHandler: Handler for the command

        Raises:
            ValueError: If command is not recognized
        """
        if command not in self.handlers:
            raise ValueError(f"Unknown command: '@{command}'")
        return self.handlers[command]

    def register_handler(self, command: str, handler: CommandHandler):
        """
        Register a new command handler.

        Args:
            command (str): Command name
            handler (CommandHandler): Handler instance
        """
        self.handlers[command] = handler


def parse_recipe_data(recipe_lines: List[str]) -> RecipeData:
    """
    Parse recipe and return the structured data.

    Args:
        recipe_lines (list of str): List of lines in a recipe file

    Returns:
        RecipeData: Parsed recipe data structure

    Raises:
        ValueError: If the recipe format is invalid
    """

    parser_context = ParserContext()
    command_registry = CommandRegistry(parser_context)

    for line_num, line in enumerate(recipe_lines, 1):
        line = line.strip()

        # Skip empty lines and comments
        if not line or line.startswith("#"):
            continue

        try:
            # Handle command lines starting with @
            if line.startswith("@"):
                parts = line[1:].split()
                if not parts:
                    raise ValueError("Empty command after '@'")

                command = parts[0]
                handler = command_registry.get_handler(command)
                handler.handle(parts)

            else:
                # Handle test generation commands
                if (
                    parser_context.current_context == "subtask"
                    and parser_context.current_object.independent_testset is None
                ):
                    parser_context.current_object.set_independent_testset(
                        parser_context
                    )

                # Expand constants in test generation commands
                expanded_line = parser_context.expand_constants(line)
                parser_context.current_object.add_test(expanded_line)

        except ValueError as e:
            raise ValueError(f"Error on line {line_num}: {e}")

    # Generate test names after parsing is complete
    parser_context.recipe_data.generate_all_test_names()

    # Push validations to all test cases after parsing is complete
    parser_context.recipe_data.push_validation_to_testcases()

    return parser_context.recipe_data


if __name__ == "__main__":
    # Test the parser with sample data
    sample_data = """
@constant MAX_N 200000
@constant SMALL_N 100

@testset t1
gen --N=${SMALL_N} seed=1
gen --N=${SMALL_N} seed=2

@testset t2
gen --N=2000 seed=1
gen --N=2000 seed=2

@testset t3
gen --N=20000 seed=1
gen --N=20000 seed=2

@testset edge_case
@extra_file NOTE .note
@description generate some edge cases for N <= ${SMALL_N}
special --N=1 --note=${NOTE} seed=1
special --N=2 --note=${NOTE} seed=1
gen --N=${SMALL_N} seed=1 | make_extreme

@global_validation validator --N=${MAX_N}
@global_validation validator2
# validator2 is written by a tester

@subtask s1 20
@extra_file NOTE .note
extra --N=5 --note=${NOTE} seed=1
@description $N \\leq ${SMALL_N}$
@include t1
@include edge_case
@validation validator --N=${SMALL_N}

@subtask s2 30
@description $N \\leq 2000$
@include s1
@include t2 
@validation validator --N=2000

@subtask s3 50
@description No additional constraints
@include t3
@include s2
"""

    try:
        # Parse the sample data
        recipe_data = parse_recipe_data(sample_data.split("\n"))

        # Print parsed results
        print("=== TESTSETS ===")
        for name, testset in recipe_data.testsets.items():
            print(f"Testset '{name}' (index: {testset.testset_index})")
            if len(testset.extra_file) != 0:
                print(f"  Extra files: {list(testset.extra_file)}")
            if testset.description:
                print(f"  Description: {testset.description}")
            print(f"  Tests: {len(testset.tests)}")
            for i, test in enumerate(testset.tests):
                print(
                    f"    Test {i + 1} (Name: {test.test_name}): {len(test.execute.commands)} commands"
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
            print(
                f"Subtask '{name}' (index: {subtask.subtask_index}, score: {subtask.score})"
            )
            if subtask.description:
                print(f"  Description: {subtask.description}")
            print(f"  Testsets: {sorted(subtask.tests)}")
            print(f"  Validation: {len(subtask.validation)} validators")
            for i, validation in enumerate(subtask.validation):
                print(f"    Validator {i + 1}: {validation.commands}")

        print("\nParsing completed successfully!")

    except Exception as e:
        print(f"Error: {e}")
