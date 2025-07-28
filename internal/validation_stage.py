import os
import shutil
import subprocess
from pathlib import Path
from .meta_stage import MetaMakefileCompileStage
from .runner import Process, wait_procs


class ValidationStage(MetaMakefileCompileStage):
    def __init__(self, problem_dir: str, makefile_path: str,
                 time_limit: float = 10_000, memory_limit: int = 4 * 1024 * 1024):
        super().__init__(problem_dir=problem_dir,
                         makefile_path=makefile_path,
                         time_limit=time_limit,
                         memory_limit=memory_limit)

    def compile(self):
        stdout, stderr, returncode = self.compile_with_make(self.working_dir.validator)
        return returncode == 0

    def prepare_sandbox(self):
        self.working_dir.mkdir_sandbox()

    def _make_file_extension(self, ext: str):
        if not ext.startswith('.'):
            ext = '.' + ext
        return ext

    def run_validator(self, commands: list[list[str]], code_name: str,
                      input_ext: str, extra_input_exts: list[str]) -> bool:
        """
        commands should contain all validators all at once (without piping the input file).
        extra_input_ext specifies a list of input extensions, which are the extra files generated through the generator stage.
        
        This function can raise FileNotFoundError (when validator file or expected files do not exist),
        TimeoutError (when the validator timed-out), and ChildProcessError (when the validator crashes by signaled).

        Note the latter is not the same with validation failed: validators could still run sucessfully and return non-zero value.
        """
        # TODO: handle FileNotFoundError and print actual meaningful error in the console.

        input_ext = self._make_file_extension(input_ext)
        for i in range(len(extra_input_exts)):
            extra_input_exts[i] = self._make_file_extension(extra_input_exts[i])

        # preprocess
        for command in commands:
            command[0] = self.working_dir.replace_with_validator(command[0])

        # It is fine to use the same output file: we use O_TRUNC so the logs will be the last
        # validator stdout/stderr.
        file_out_name = f"{code_name}.val.out"
        file_err_name = f"{code_name}.val.err"
        sandbox_output_file = os.path.join(self.working_dir.sandbox, file_out_name)
        sandbox_error_file = os.path.join(self.working_dir.sandbox, file_err_name)
        Path(sandbox_output_file).touch()
        Path(sandbox_error_file).touch()

        valid = True
        try:
            for command in enumerate(commands):
                # Copy input and extra inputs
                for ext in [input_ext] + extra_input_exts:
                    shutil.copy(os.path.join(self.working_dir.testcases, code_name + ext),
                                os.path.join(self.working_dir.sandbox, code_name + ext))

                validator = Process(command,
                            preexec_fn=lambda: os.chdir(self.working_dir.sandbox),
                            stdin_redirect=os.path.join(self.working_dir.testcases, code_name + input_ext),
                            stdout_redirect=sandbox_output_file,
                            stderr_redirect=sandbox_error_file,
                            time_limit=self.time_limit,
                            memory_limit=self.memory_limit)

                wait_procs([validator])
                if validator.is_timedout:
                    raise TimeoutError
                elif validator.is_signaled_exit:
                    raise ChildProcessError
                elif validator.status != 0:
                    valid = False
                    break
        
        except FileNotFoundError as exception:
            # We can simply raise, since there will be no processes left
            raise exception
        
        self.working_dir.mkdir_logs()
        self.working_dir.mkdir_testcases()

        # Move extra files
        try:
            # Move logs
            shutil.move(os.path.join(self.working_dir.sandbox, file_out_name), 
                        os.path.join(self.working_dir.logs, file_out_name))
            shutil.move(os.path.join(self.working_dir.sandbox, file_err_name), 
                        os.path.join(self.working_dir.logs, file_err_name))
        except FileNotFoundError as exception:
            raise exception

        return valid
