import os
import subprocess
import platform

from internal.runner import Process, wait_for_outputs
from internal.outcome import CompilationOutcome, CompilationResult
from internal.context import TMTContext

MAKE = "make"


class CppCompileStep:
    def __init__(
        self,
        *,
        directory: str,
        target: None | tuple[str, list[str]],
        # target = None means compile all
        # otherwise, target = (target_name, dependency)
        context: TMTContext,
    ):
        self.directory = directory
        self.target = target
        if self.target is None:
            self.makefile_path = context.path.makefile_wildcard
        else:
            self.makefile_path = context.path.makefile_target

        self.time_limit_sec = context.config.trusted_compile_time_limit_sec
        self.memory_limit_mib = context.config.trusted_compile_memory_limit_mib

        self.include_paths = [context.path.include]
        self.compile_flags = context.compile_flags("cpp")

        # On MacOS, this has to be set during compile time
        if platform.system() == "Darwin":
            executable_stack_size_mib = min(self.memory_limit_mib, 512)
            self.compile_flags += [
                "-Wl,-stack_size",
                f"-Wl,{executable_stack_size_mib * 1024 * 1024:x}",
            ]

    def _run_make(self, extra_args: list[str]):
        command = [MAKE, "-C", self.directory, "-f", self.makefile_path] + extra_args
        env = {
            "CXXFLAGS": " ".join(self.compile_flags),
            "INCLUDE_PATHS": " ".join(self.include_paths),
        } | os.environ
        if self.target is not None:
            target_name, source_files = self.target
            env = env | {
                "SOURCE_FILES": " ".join(source_files),
                "TARGET_NAME": target_name,
            }

        proc = Process(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            time_limit_sec=self.time_limit_sec,
            memory_limit_mib=self.memory_limit_mib,
            env=env,
        )
        stdout, stderr = wait_for_outputs(proc)
        return stdout, stderr, proc

    def run_make_all(self) -> CompilationResult:
        stdout, stderr, compile_process = self._run_make([])  # make
        logs, _, _ = self._run_make(["-s", "logs"])  # obtain the path of logs

        # We have to obtain stderr again from files if they are piped out.
        for log in logs.split():
            if os.path.exists(log):
                with open(log, "r") as infile:
                    stderr += infile.read()
            else:
                stderr += f"warning: compilation log file {logs} could not be found"

        if compile_process.status == 0:
            verdict = CompilationOutcome.SUCCESS
        elif compile_process.is_timedout:
            verdict = CompilationOutcome.TIMEDOUT
        else:
            verdict = CompilationOutcome.FAILED

        return CompilationResult(
            verdict=verdict,
            standard_output=stdout,
            standard_error=stderr,
            exit_status=compile_process.status,
        )

    def run_make_clean(self) -> None:
        self._run_make(["clean"])
