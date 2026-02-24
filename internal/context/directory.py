# Implements temporary sandbox path helpers

import os
import shutil
import stat

class Directory:
    def __init__(self, directory_root: str):
        self.directory_root = os.path.normpath(directory_root)

    @property
    def path(self):
        return self.directory_root

    def create(self):
        """Create the directory via os.makedirs."""
        os.makedirs(self.directory_root, exist_ok=True)

    def file(self, file_name: str):
        """Return the canonical path of a file under this directory."""
        return os.path.join(self.directory_root, file_name)

    def subdir(self, dir_name: str):
        """Return the canonical path of a file under this directory."""
        return Directory(os.path.join(self.directory_root, dir_name))

    def clean(self):
        """Remove everything under this directory. If the directory itself does not exist, nothing happens."""
        if not os.path.exists(self.directory_root):
            return
        for filename in os.listdir(self.directory_root):
            file_path = os.path.join(self.directory_root, filename)
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)


class SandboxDirectory(Directory):
    """
    Path generator and helper for sandbox.
    """

    def __init__(self, sandbox_directory: str):
        super().__init__(sandbox_directory)
        self.generation = Directory(os.path.join(self.directory_root, "generation"))
        self.validation = Directory(os.path.join(self.directory_root, "validation"))
        self.solution_invocation = Directory(os.path.join(self.directory_root, "solution-invoke"))
        self.solution_compilation = Directory(os.path.join(self.directory_root, "solution-compile"))
        self.checker_compilation = Directory(os.path.join(self.directory_root, "checker-compile"))
        self.checker = Directory(os.path.join(self.directory_root, "checker"))
        self.interactor = Directory(os.path.join(self.directory_root, "interactor"))
        self.manager = Directory(os.path.join(self.directory_root, "manager"))
