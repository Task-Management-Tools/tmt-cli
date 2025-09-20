import yaml
import re
from pathlib import Path
from typing import List, IO

from internal.formatting import Formatter
from internal.context import TMTContext
from internal.errors import TMTMissingFileError, TMTInvalidConfigError
from internal.context.config import parse_time_to_second, parse_bytes_to_mib

from .base import FolderFormatExporter

def load_yaml(yaml_path: Path) -> dict: 
    try:
        with open(yaml_path, "r") as file:
            input_yaml = yaml.safe_load(file)
        # self.config stores the parsed config from problem.yaml
    except (FileNotFoundError, IsADirectoryError, PermissionError) as e:
        raise TMTMissingFileError("config", self.path.problem_yaml) from e
    except yaml.YAMLError as e:
        raise TMTInvalidConfigError(self.path.problem_yaml) from e
    except Exception as e:
        raise
    return input_yaml 

def yaml_converter(source_files: List[Path], output_file: IO) -> None:
    """
    source_files: [proble_yaml]
    """
    input_yaml = load_yaml(source_files[0])
    output_yaml = {
        "problem_format_version": "2023-07-draft",
        "name": input_yaml.get("short_name", "null"),
        "author": input_yaml.get("author", "anonymous"),
        "license": "cc by-sa",
        "limits": {}
    }

    """Setup limits"""
    #time_multipliers:
    #  ac_to_time_limit: 2.0
    #  time_limit_to_tle: 1.5
    if "solution" in input_yaml and "time_limit" in input_yaml["solution"]:
        output_yaml["limits"]["time_limit"] = parse_time_to_second("problem.yaml['solution']['time_limit']", input_yaml["solution"]["time_limit"])
    if "solution" in input_yaml and "memory_limit" in input_yaml["solution"]:
        output_yaml["limits"]["memory"] = parse_bytes_to_mib("problem.yaml['solution']['memory_limit']", input_yaml["solution"]["memory_limit"])
    #time_resolution: 1.0
    if "solution" in input_yaml and "output_limit" in input_yaml["solution"]:
        if input_yaml["solution"]["output_limit"] == "unlimited":
            output_yaml["limits"]["output"] = 2048 # there's no unlimited in icpc format 
        else:
            output_yaml["limits"]["output"] = parse_bytes_to_mib("problem.yaml['solution']['output_limit']", input_yaml["solution"]["output_limit"])
    #code: 128
    #compilation_time: 60
    #compilation_memory: 2048
    #validation_time: 60
    #validation_memory: 2048
    #validation_output: 8

    """Setup validation"""
    if "checker" in input_yaml:
        if "type" not in input_yaml["checker"]:
            output_yaml["validation"] = "default"
        else:
            command = input_yaml["checker"]["type"]
            if "arguments" in input_yaml["checker"]:
                command += " " + input_yaml["checker"]["arguments"]
            output_yaml["validation"] = command
    elif "interactor" in input_yaml:
        output_yaml["validation"] = "custome interactive"

    yaml.dump(output_yaml, output_file, sort_keys=False)

class ICPCExporter(FolderFormatExporter):
    """ICPC exporter implementation"""
    
    def __init__(self, formatter: Formatter, context: TMTContext, output_path: str):
        super().__init__(formatter, context, output_path)
        self.setup_operations()
    
    def setup_operations(self):
        """Setup conversion operations"""

        """Setup problem config file"""
        self.add_custom_operation(
            ["problem.yaml"],
            "problem.yaml",
            yaml_converter
        )
   
        """Setup statement"""
        self.add_regex_copy_operation(
            r"^statement/.*\.pdf", 
            "problem_statement" 
        )

        """Setup submissions"""
        def recognize_verdict(matched_files: List[Path], additional_files: List[Path]) -> str:
            verdicts_folder = "unknown"
            idx = matched_files[0].parts.index('solutions')
            file_name = Path(*matched_files[0].parts[idx+1:]) 
            try:
                verdicts = load_yaml(additional_files[0])
                for file in verdicts:
                    if 'filename' not in file or 'verdict' not in file:
                        continue
                    if str(file['filename']) == str(file_name):
                        if isinstance(file['verdict'], list):
                            verdicts_folder = file['verdict'][0]
                        else:
                            verdicts_folder = file['verdict']
            except TMTMissingFileError as e:
                verdicts_folder = "unknown"
            except Exception as e:
                raise
            return Path(verdicts_folder) / file_name

        self.add_regex_copy_operation(
            r"^solutions/.*\..*", 
            "submissions", 
            keep_original_name=False,
            rename_func=recognize_verdict,
            additional_sources=["verdicts.yaml"]
        )

        """Setup output_validators"""
        self.add_regex_copy_operation(
            r"^checker/.*\.(?:cc|cpp)", 
            "output_validators/cpp_validator" 
        )
        self.add_regex_copy_operation(
            r"^interactor/.*\.(?:cc|cpp)", 
            "output_validators/cpp_validator" 
        )

        """Setup data"""
        self.add_regex_copy_operation(
            rf"^testcases/.*_samples_.*\{self.context.config.input_extension}", 
            "data/sample" 
        )
        self.add_regex_copy_operation(
            rf"^testcases/.*_samples_.*\{self.context.config.output_extension}", 
            "data/sample" 
        )
        self.add_regex_copy_operation(
            rf"^testcases/(?!.*_samples_).*\{self.context.config.input_extension}", 
            "data/secret" 
        )
        self.add_regex_copy_operation(
            rf"^testcases/(?!.*_samples_).*\{self.context.config.output_extension}", 
            "data/secret" 
        )

        """Setup include headers"""
        """It is hard to detect required headers, so we copy all of them to all possible directories"""
        self.add_regex_copy_operation(
            r"^include/.*\.(?:h|hpp)", 
            "output_validators/cpp_validator" 
        )
        
