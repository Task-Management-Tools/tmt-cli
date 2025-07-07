#!/usr/bin/env python3
"""
Contest Test Data Parser

This module parses a custom format file to generate contest test data structure objects.
The parsed data includes testsets, subtasks, and validation rules for programming contests.
"""

import re
from typing import Dict, List, Set, Optional, Union


class Executable:
    """
    Represents an executable command with multiple programs to run sequentially.
    
    Each executable contains a list of command lists, where each command list
    follows the subprocess format (executable name + arguments).
    """
    
    def __init__(self):
        self.commands: List[List[str]] = []
    
    def add_command_sequence(self, command_sequence: str):
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
        commands = command_sequence.split('|')
        for cmd in commands:
            cmd = cmd.strip()
            if not cmd:
                raise ValueError("Empty command found in sequence")
            
            # Split command into executable and arguments
            parts = cmd.split()
            if not parts:
                raise ValueError("Invalid command format")
            
            # Get the actual executable name using the external function
            executable_name = get_executable_name(parts[0])
            command_list = [executable_name] + parts[1:]
            self.commands.append(command_list)


class Testset:
    """
    Represents a set of test cases for contest problems.
    
    Contains metadata about the testset and a list of test generation commands.
    """
    
    def __init__(self, testset_name: str, testset_index: int):
        self.testset_name: str = testset_name
        self.testset_index: int = testset_index
        self.description: Optional[str] = None
        self.tests: List[Executable] = []
    
    def add_test(self, command_sequence: str):
        """
        Add a test case by parsing the command sequence.
        
        Args:
            command_sequence (str): Command sequence to generate test data
        """
        try:
            executable = Executable()
            executable.add_command_sequence(command_sequence)
            self.tests.append(executable)
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
            raise ValueError(f"Description already set for testset '{self.testset_name}'")
        self.description = description


class Subtask:
    """
    Represents a subtask in a contest problem.
    
    Contains scoring information, validation rules, and associated testsets.
    """
    
    def __init__(self, subtask_name: str, subtask_index: int, score: int):
        self.subtask_name: str = subtask_name
        self.subtask_index: int = subtask_index
        self.score: int = score
        self.description: Optional[str] = None
        self.validation: List[Executable] = []
        self.tests: Set[str] = set()
    
    def add_validation(self, command: str, *args):
        """
        Add a validation command for this subtask.
        
        Args:
            command (str): Validation executable name
            *args: Arguments for the validation command
        """
        try:
            executable = Executable()
            command_sequence = f"{command} {' '.join(args)}"
            executable.add_command_sequence(command_sequence)
            self.validation.append(executable)
        except ValueError as e:
            raise ValueError(f"Error adding validation to subtask '{self.subtask_name}': {e}")
    
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
            raise ValueError(f"Description already set for subtask '{self.subtask_name}'")
        self.description = description


class ContestData:
    """
    Main container for all contest test data information.
    
    Includes testsets, subtasks, and global validation rules.
    """
    
    def __init__(self):
        self.testsets: Dict[str, Testset] = {}
        self.subtasks: Dict[str, Subtask] = {}
        self.global_validation: List[Executable] = []


def get_executable_name(command: str) -> str:
    """
    Convert command name to actual executable name.
    
    This function should be implemented by the user to handle
    command name mapping and resolution.
    
    Args:
        command (str): Command name from the input file
        
    Returns:
        str: Actual executable name to use
    """
    # Placeholder implementation - user should override this
    return command


class ParserContext:
    """
    Manages the parsing context and state during file processing.
    
    This class serves as a shared context for all handlers, allowing them
    to access and modify parsing state, share information, and store
    temporary data that doesn't belong in the final ContestData object.
    """
    
    def __init__(self):
        self.contest_data = ContestData()
        self.current_context = None
        self.current_object = None
        self.testset_counter = 1  # 1-based counter
        self.subtask_counter = 1  # 1-based counter
        self.used_names = set()
        
        # Shared data storage for inter-handler communication
        self.constants = {}  # For storing user-defined constants
        self.shared_data = {}  # For any other shared data between handlers
    
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
        import re
        
        def replace_var(match):
            var_name = match.group(1)
            if var_name not in self.constants:
                raise ValueError(f"Undefined constant: ${{{var_name}}}")
            return str(self.constants[var_name])
        
        # Replace ${constant_name} patterns
        return re.sub(r'\$\{([^}]+)\}', replace_var, text)
    
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

    def get_shared_data(self, key: str, default=None):
        """
        Get shared data by key.
        
        Args:
            key (str): Data key
            default: Default value if key doesn't exist
            
        Returns:
            Shared data value or default
        """
        return self.shared_data.get(key, default)
    
    def set_shared_data(self, key: str, value):
        """
        Set shared data.
        
        Args:
            key (str): Data key
            value: Data value
        """
        self.shared_data[key] = value
    
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
    
    def validate_args(self, parts: List[str], min_args: int, max_args: int = None):
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
        self.context.contest_data.testsets[testset_name] = testset
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
        self.context.contest_data.subtasks[subtask_name] = subtask
        self.context.current_context = "subtask"
        self.context.current_object = subtask
        self.context.subtask_counter += 1


class GlobalValidationHandler(CommandHandler):
    """Handler for @global_validation commands."""
    
    def handle(self, parts: List[str]):
        self.validate_args(parts, 1)
        
        executable = Executable()
        self.context.list_expand_constants(parts)
        command_sequence = ' '.join(parts[1:])
        executable.add_command_sequence(command_sequence)
        self.context.contest_data.global_validation.append(executable)
        self.context.current_context = None
        self.context.current_object = None


class DescriptionHandler(CommandHandler):
    """Handler for @description commands."""
    
    def handle(self, parts: List[str]):
        self.validate_args(parts, 1)
        
        if self.context.current_context is None:
            raise ValueError("@description can only be used within testset or subtask context")

        self.context.list_expand_constants(parts)
        description = ' '.join(parts[1:])
        self.context.current_object.set_description(description)


class IncludeHandler(CommandHandler):
    """Handler for @include commands."""
    
    def handle(self, parts: List[str]):
        self.validate_args(parts, 1, 1)
        
        if self.context.current_context != "subtask":
            raise ValueError("@include can only be used within subtask context")
        
        include_name = parts[1]
        
        # Check if it's a testset or subtask
        if include_name in self.context.contest_data.testsets:
            self.context.current_object.include_testset(include_name)
        elif include_name in self.context.contest_data.subtasks:
            # Include all testsets from the referenced subtask
            referenced_subtask = self.context.contest_data.subtasks[include_name]
            for testset_name in referenced_subtask.tests:
                self.context.current_object.include_testset(testset_name)
        else:
            raise ValueError(f"Unknown testset or subtask name: '{include_name}'")


class ValidationHandler(CommandHandler):
    """Handler for @validation commands."""
    
    def handle(self, parts: List[str]):
        self.validate_args(parts, 1)
        
        if self.context.current_context != "subtask":
            raise ValueError("@validation can only be used within subtask context")
        
        self.context.list_expand_constants(parts)
        self.context.current_object.add_validation(parts[1], *parts[2:])


class ConstantHandler(CommandHandler):
    """Handler for @constant commands."""
    
    def handle(self, parts: List[str]):
        self.validate_args(parts, 2, 2)
        
        self.context.set_constant(parts[1], parts[2])


class CommandRegistry:
    """
    Registry for all available command handlers.
    """
    
    def __init__(self, parser_context: ParserContext):
        self.handlers = {
            'testset': TestsetHandler(parser_context),
            'subtask': SubtaskHandler(parser_context),
            'global_validation': GlobalValidationHandler(parser_context),
            'description': DescriptionHandler(parser_context),
            'include': IncludeHandler(parser_context),
            'validation': ValidationHandler(parser_context),
            'constant': ConstantHandler(parser_context),
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


def parse_contest_data(file_path: str) -> ContestData:
    """
    Parse a contest data file and return the structured data.
    
    Args:
        file_path (str): Path to the input file
        
    Returns:
        ContestData: Parsed contest data structure
        
    Raises:
        FileNotFoundError: If the input file doesn't exist
        ValueError: If the file format is invalid
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        raise FileNotFoundError(f"Input file not found: {file_path}")
    except Exception as e:
        raise ValueError(f"Error reading file '{file_path}': {e}")
    
    parser_context = ParserContext()
    command_registry = CommandRegistry(parser_context)
    
    for line_num, line in enumerate(lines, 1):
        line = line.strip()
        
        # Skip empty lines and comments
        if not line or line.startswith('#'):
            continue
        
        try:
            # Handle command lines starting with @
            if line.startswith('@'):
                parts = line[1:].split()
                if not parts:
                    raise ValueError("Empty command after '@'")
                
                command = parts[0]
                handler = command_registry.get_handler(command)
                handler.handle(parts)
            
            else:
                # Handle test generation commands (only valid in testset context)
                if parser_context.current_context != "testset":
                    raise ValueError("Test generation commands can only be used within testset context")
                
                # Expand constants in test generation commands
                expanded_line = parser_context.expand_constants(line)
                parser_context.current_object.add_test(expanded_line)
        
        except ValueError as e:
            raise ValueError(f"Error on line {line_num}: {e}")
    
    return parser_context.contest_data


if __name__ == '__main__':
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
@description generate some edge cases for N <= ${SMALL_N}
special --N=1 seed=1
special --N=2 seed=1
gen --N=${SMALL_N} seed=1 | make_extreme

@global_validation validator --N=${MAX_N}
@global_validation validator2
# validator2 is written by a tester

@subtask s1 20
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
    
    # Write sample data to a temporary file
    with open('test_input.txt', 'w') as f:
        f.write(sample_data)
    
    try:
        # Parse the sample data
        contest_data = parse_contest_data('test_input.txt')
        
        # Print parsed results
        print("=== TESTSETS ===")
        for name, testset in contest_data.testsets.items():
            print(f"Testset '{name}' (index: {testset.testset_index})")
            if testset.description:
                print(f"  Description: {testset.description}")
            print(f"  Tests: {len(testset.tests)}")
            for i, test in enumerate(testset.tests):
                print(f"    Test {i+1}: {len(test.commands)} commands")
                for j, cmd in enumerate(test.commands):
                    print(f"      Command {j+1}: {cmd}")
        
        print("\n=== GLOBAL VALIDATION ===")
        print(f"Global validation: {len(contest_data.global_validation)} validators")
        for i, validation in enumerate(contest_data.global_validation):
            print(f"  Global validation {i+1}: {validation.commands}")
        
        print("\n=== SUBTASKS ===")
        for name, subtask in contest_data.subtasks.items():
            print(f"Subtask '{name}' (index: {subtask.subtask_index}, score: {subtask.score})")
            if subtask.description:
                print(f"  Description: {subtask.description}")
            print(f"  Tests: {sorted(subtask.tests)}")
            print(f"  Validation: {len(subtask.validation)} validators")
            for i, validation in enumerate(subtask.validation):
                print(f"    Validator {i+1}: {validation.commands}")
        
        print("\nParsing completed successfully!")
        
    except Exception as e:
        print(f"Error: {e}")
    
    # Clean up
    import os
    if os.path.exists('test_input.txt'):
        os.remove('test_input.txt')
