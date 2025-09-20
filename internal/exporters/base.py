import re
import zipfile
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, List, Optional, IO
import tempfile

from internal.formatting import Formatter
from internal.context import TMTContext


class ConversionOperation(ABC):
    """Base class for different types of conversion operations"""
    
    @abstractmethod
    def execute(self, formatter: Formatter, context: TMTContext, output_folder: Path) -> None:
        """Execute the conversion operation"""
        pass


class CopyFileOperation(ConversionOperation):
    """Simple file copy operation"""
    
    def __init__(self, source_path: str, target_path: str):
        self.source_path = source_path
        self.target_path = target_path
    
    def target_name(self) -> str:
        return self.target_path
    
    def execute(self, formatter: Formatter, context: TMTContext, output_folder: Path) -> None:
        source = Path(context.path.problem_dir) / Path(self.source_path)
        target = output_folder / Path(self.target_path)
        
        # Ensure target directory exists
        target.parent.mkdir(parents=True, exist_ok=True)
        
        if source.exists():
            shutil.copy2(source, target)
            formatter.println("[", formatter.ANSI_GREEN, "OK", formatter.ANSI_RESET, "]")
        else:
            formatter.println("[", formatter.ANSI_YELLOW, "WARN", formatter.ANSI_RESET, "]", f" Source {self.source_path} does not exist")


class CustomFileOperation(ConversionOperation):
    """Custom file processing operation"""
    
    def __init__(self, source_paths: List[str], target_path: str, 
                 processor_func: Callable[[List[Path], IO], None]):
        self.source_paths = source_paths
        self.target_path = target_path
        self.processor_func = processor_func
    
    def target_name(self) -> str:
        return self.target_path
    
    def execute(self, formatter: Formatter, context: TMTContext, output_folder: Path) -> None:
        source_files = []
        for path in self.source_paths:
            source_file = Path(context.path.problem_dir) / Path(path)
            if source_file.exists():
                source_files.append(source_file)
            else:
                formatter.println("[", formatter.ANSI_YELLOW, "WARN", formatter.ANSI_RESET, "]", f" Source {path} does not exist")
                return
        
        target = output_folder / Path(self.target_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        
        with open(target, 'w') as output_file:
            self.processor_func(source_files, output_file)
        formatter.println("[", formatter.ANSI_GREEN, "OK", formatter.ANSI_RESET, "]")


class RegexCopyOperation(ConversionOperation):
    """Copy files matching regex pattern"""
    
    def __init__(self, pattern: str, target_path: str, 
                 keep_original_name: bool = True,
                 rename_func: Optional[Callable[[List[Path], List[Path]], str]] = None,
                 custom_func: Optional[Callable[[List[Path], List[Path], IO], None]] = None,
                 additional_sources: Optional[List[str]] = None):
        self.pattern = re.compile(pattern)
        self.target_path = target_path
        self.keep_original_name = keep_original_name
        self.rename_func = rename_func
        self.custom_func = custom_func
        self.additional_sources = additional_sources or []
        
    def target_name(self) -> str:
        return self.target_path + "/ (" + self.pattern.pattern + ")"
    
    def execute(self, formatter: Formatter, context: TMTContext, output_folder: Path) -> None:
        target_dir = output_folder / Path(self.target_path)
        target_dir.mkdir(parents=True, exist_ok=True)
        
        # Find all matching files recursively
        matching_files = []
        for file_path in Path(context.path.problem_dir).rglob('*'):
            #print(str(file_path.relative_to(context.path.problem_dir)))
            if file_path.is_file() and self.pattern.search(str(file_path.relative_to(context.path.problem_dir))):
                matching_files.append(file_path)
        
        if not matching_files:
            formatter.println("[", formatter.ANSI_YELLOW, "WARN", formatter.ANSI_RESET, "]", " Cannot find any matched files")
            return
        
        # Collect additional source files
        additional_files = []
        for source_path in self.additional_sources:
            source_file = Path(context.path.problem_dir) / Path(source_path)
            if source_file.exists():
                additional_files.append(source_file)
            else:
                formatter.println("[", formatter.ANSI_YELLOW, "WARN", formatter.ANSI_RESET, "]", f" Additional files {source_path} does not exist")
                return
        
        for file_path in matching_files:
            if self.keep_original_name:
                target_name = file_path.name
            else:
                if self.rename_func:
                    target_name = self.rename_func([file_path], additional_files)
                else:
                    target_name = file_path.name

            target_file = target_dir / Path(target_name)
            target_file.parent.mkdir(parents=True, exist_ok=True)
            
            if self.custom_func:
                with open(target_file, 'w') as output_file:
                    self.custom_func([file_path], additional_files, output_file)
            else:
                # Simple copy (ignoring additional files in default behavior)
                shutil.copy2(file_path, target_file)
        
        formatter.println("[", formatter.ANSI_GREEN, "OK", formatter.ANSI_RESET, "]")


class ExternalFileOperation(ConversionOperation):
    """Copy external files (not from input folder)"""
    
    def __init__(self, external_path: str, target_path: str):
        self.external_path = Path(external_path)
        self.target_path = target_path
    
    def target_name(self) -> str:
        return self.target_path
    
    def execute(self, formatter: Formatter, context: TMTContext, output_folder: Path) -> None:
        target = output_folder / Path(self.target_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        
        if self.external_path.exists():
            if self.external_path.is_file():
                shutil.copy2(self.external_path, target)
            elif self.external_path.is_dir():
                shutil.copytree(self.external_path, target, dirs_exist_ok=True)
            formatter.println("[", formatter.ANSI_GREEN, "OK", formatter.ANSI_RESET, "]")
        else:
            formatter.println("[", formatter.ANSI_YELLOW, "WARN", formatter.ANSI_RESET, "]", f" Source {self.external_path} does not exist")


class FolderFormatExporter:
    """Base class for folder format conversion"""
    
    def __init__(self, formatter: Formatter, context: TMTContext, output_path: str):
        self.output_path = output_path
        self.operations: List[ConversionOperation] = []
        self.formatter = formatter
        self.context = context
    
    def add_copy_operation(self, source_path: str, target_path: str) -> None:
        """Add a simple file copy operation"""
        operation = CopyFileOperation(source_path, target_path)
        self.operations.append(operation)
    
    def add_custom_operation(self, source_paths: List[str], target_path: str,
                           processor_func: Callable[[List[Path], IO], None]) -> None:
        """Add a custom file processing operation"""
        operation = CustomFileOperation(source_paths, target_path, processor_func)
        self.operations.append(operation)
    
    def add_regex_copy_operation(self, pattern: str, target_folder: str,
                               keep_original_name: bool = True,
                               rename_func: Optional[Callable[[List[Path], List[Path]], str]] = None,
                               custom_func: Optional[Callable[[List[Path], List[Path], IO], None]] = None,
                               additional_sources: Optional[List[str]] = None) -> None:
        """
        Add a regex-based file copy operation
        
        Args:
            pattern: Regex pattern to match files
            target_folder: Target folder name
            keep_original_name: Whether to keep original filenames (ignored if rename_func provided)
            rename_func: Function that takes (matched_files, additional_files) and returns target filename
            custom_func: Function that takes (matched_files, additional_files, output_file)
            additional_sources: List of additional file paths from problem director to include
        """
        operation = RegexCopyOperation(pattern, target_folder, keep_original_name, 
                                     rename_func, custom_func, additional_sources)
        self.operations.append(operation)
    
    def add_external_file_operation(self, external_path: str, target_path: str) -> None:
        """Add an external file copy operation"""
        operation = ExternalFileOperation(external_path, target_path)
        self.operations.append(operation)
    
    def export(self, create_zip: bool = True) -> None:
        """Export folder format"""
        
        name_length = max(len(operation.target_name()) for operation in self.operations) + 2

        self.formatter.println(f"Exporting {self.output_path}...")
        
        # Create temporary directory for conversion
        with tempfile.TemporaryDirectory() as temp_dir:
            if not create_zip:
                output_dir = Path(self.output_path)
                if output_dir.exists():
                    self.formatter.println(formatter.ANSI_RED, f"Error: path {output_dir} already exists.", formatter.ANSI_RESET)
                    return
                output_dir.mkdir();
            else:
                output_dir = Path(temp_dir)

            try:
                # Execute all operations
                for operation in self.operations:
                    self.formatter.print(" " * 4)
                    self.formatter.print_fixed_width(operation.target_name(), width=name_length)
                    operation.execute(self.formatter, self.context, output_dir)
                
                # Handle output
                if create_zip:
                    self.formatter.println(f"Creating zip file...")
                    zip_path = Path(self.output_path)
                    
                    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        for file_path in output_dir.rglob('*'):
                            if file_path.is_file():
                                arcname = file_path.relative_to(output_dir)
                                zipf.write(file_path, arcname)
                    
                    self.formatter.println(f"Export completed.")
                else:
                    self.formatter.println(f"Export completed.")
                
                return True
                
            except Exception as e:
                self.formatter.println(f"Error during exporting: {e}")
                return False
