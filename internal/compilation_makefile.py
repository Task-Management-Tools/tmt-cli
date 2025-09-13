import os
import subprocess


from internal.runner import Process, wait_for_outputs
from internal.context import TMTContext

MAKE = "make"


def clean_with_make(*, makefile_path: str, directory: str, context: TMTContext) -> None:
    command = [MAKE, "-C", directory, "-f", makefile_path, "clean"]

    compilation_time_limit_sec = context.config.trusted_compile_time_limit_sec
    compilation_memory_limit_mib = context.config.trusted_compile_memory_limit_mib
    compiler = context.compiler("cpp")
    compile_flags = context.compile_flags("cpp")
    include_paths = [context.path.include]

    sandbox_setting = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "time_limit_sec": compilation_time_limit_sec,
        "memory_limit_mib": compilation_memory_limit_mib,
        "env": {
            "CXX": compiler,
            "CXXFLAGS": " ".join(compile_flags),
            "INCLUDE_PATHS": " ".join(include_paths),
        }
        | os.environ,
    }

    clean_process = Process(command, **sandbox_setting)
    wait_for_outputs(clean_process)
