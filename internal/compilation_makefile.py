import os
import subprocess
import platform


from internal.runner import Process, wait_for_outputs
from internal.outcome import CompilationOutcome, CompilationResult
from internal.context import TMTContext

MAKE = "make"


def compile_with_make(
    *,
    makefile_path: str,
    directory: str,
    context: TMTContext,
    executable_stack_size_mib: int,
) -> CompilationResult:
    command = [MAKE, "-C", directory, "-f", makefile_path]

    compilation_time_limit_sec = context.config.trusted_compile_time_limit_sec
    compilation_memory_limit_mib = context.config.trusted_compile_memory_limit_mib
    compiler = context.compiler
    compile_flags = context.compile_flags
    include_paths = [context.path.include]

    # On MacOS, this has to be set during compile time
    if platform.system() == "Darwin":
        executable_stack_size_mib = min(executable_stack_size_mib, 512) 
        compile_flags += ["-Wl,-stack_size", f"-Wl,{executable_stack_size_mib * 1024 * 1024:x}"]

    sandbox_setting = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "time_limit_sec": compilation_time_limit_sec,
        "memory_limit_mib": compilation_memory_limit_mib,
        "env": {
            "CXX": compiler,
            "CXXFLAGS": " ".join(compile_flags),
            "INCPATHS": " ".join(include_paths),
        }
        | os.environ,
    }

    compile_process = Process(command, **sandbox_setting)
    stdout, stderr = wait_for_outputs(compile_process)

    logs, _ = wait_for_outputs(
        Process(
            [MAKE, "-C", directory, "-f", makefile_path, "-s", "logs"],
            **sandbox_setting,
        )
    )
    # We have to obtain stderr again from files if they are piped out.
    for log in logs.split():
        if os.path.exists(log):
            with open(log, "r") as infile:
                stderr += infile.read()
        else:
            stderr += f"warning: compilation log file {logs} could not be found"

    return CompilationResult(
        verdict=(
            CompilationOutcome.SUCCESS
            if compile_process.status == 0
            else CompilationOutcome.TIMEDOUT
            if compile_process.is_timedout
            else CompilationOutcome.FAILED
        ),
        standard_output=stdout,
        standard_error=stderr,
        exit_status=compile_process.status,
    )


def clean_with_make(*, makefile_path: str, directory: str, context: TMTContext) -> None:
    command = [MAKE, "-C", directory, "-f", makefile_path, "clean"]

    compilation_time_limit_sec = context.config.trusted_compile_time_limit_sec
    compilation_memory_limit_mib = context.config.trusted_compile_memory_limit_mib
    compiler = context.compiler
    compile_flags = context.compile_flags
    include_paths = [context.path.include]

    sandbox_setting = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "time_limit_sec": compilation_time_limit_sec,
        "memory_limit_mib": compilation_memory_limit_mib,
        "env": {
            "CXX": compiler,
            "CXXFLAGS": " ".join(compile_flags),
            "INCPATHS": " ".join(include_paths),
        }
        | os.environ,
    }

    clean_process = Process(command, **sandbox_setting)
    wait_for_outputs(clean_process)
