import subprocess
import shutil
import os

from internal.context import TMTContext
from internal.outcome import (
    CompilationOutcome,
    CompilationResult,
    SingleCompilationResult,
)
from internal.runner import Process, wait_for_outputs

from .languages import languages


# if platform.system() == "Darwin":
#     MAKE = "make"
# else:
MAKE = "make"


def make_compile_wildcard(
    *, context: TMTContext, directory: str, executable_stack_size_mib: int
) -> CompilationResult:
    compilation_time_limit_sec = context.config.trusted_compile_time_limit_sec
    compilation_memory_limit_mib = context.config.trusted_compile_memory_limit_mib

    allout, allerr = "", ""

    compile_process: Process | None = None

    for lang_type in languages:
        lang = lang_type(context)

        make_info = lang.get_make_wildcard_command(executable_stack_size_mib)

        command = [MAKE, "-C", directory, "-f", make_info.makefile]
        compile_process = Process(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            time_limit_sec=compilation_time_limit_sec,
            memory_limit_mib=compilation_memory_limit_mib,
            env=make_info.env | os.environ,
        )
        stdout, stderr = wait_for_outputs(compile_process)
        allout += stdout
        allerr += stderr

        if compile_process.status != 0 or compile_process.is_timedout:
            break

    verdict: CompilationOutcome
    if compile_process is None:
        verdict = CompilationOutcome.SUCCESS
    elif compile_process.is_timedout:
        verdict = CompilationOutcome.TIMEDOUT
    elif compile_process.status != 0:
        verdict = CompilationOutcome.FAILED
    else:
        verdict = CompilationOutcome.SUCCESS

    return CompilationResult(
        verdict=verdict,
        standard_output=allout,
        standard_error=allerr,
        exit_status=(compile_process.status if compile_process is not None else 0),
    )


def make_compile_targets(
    *,
    context: TMTContext,
    directory: str,
    sources: list[str],
    target: str,
    executable_stack_size_mib: int,
) -> SingleCompilationResult:
    compilation_time_limit_sec = context.config.trusted_compile_time_limit_sec
    compilation_memory_limit_mib = context.config.trusted_compile_memory_limit_mib

    compile_process: Process | None = None

    for lang_type in languages:
        lang = lang_type(context)

        if all(
            [
                any([src.endswith(ext) for ext in lang.source_extensions])
                for src in sources
            ]
        ):
            make_info = lang.get_make_target_command(executable_stack_size_mib)

            command = [MAKE, "-C", directory, "-f", make_info.makefile]
            compile_process = Process(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                time_limit_sec=compilation_time_limit_sec,
                memory_limit_mib=compilation_memory_limit_mib,
                env=make_info.env
                | os.environ
                | {
                    "SRCS": " ".join(sources),
                    "TARGET_NAME": target,
                },
            )

            stdout, stderr = wait_for_outputs(compile_process)

            verdict: CompilationOutcome
            if compile_process.is_timedout:
                verdict = CompilationOutcome.TIMEDOUT
            elif compile_process.status != 0:
                verdict = CompilationOutcome.FAILED
            else:
                verdict = CompilationOutcome.SUCCESS

            return SingleCompilationResult(
                verdict=verdict,
                standard_output=stdout,
                standard_error=stderr,
                exit_status=compile_process.status,
                produced_file=os.path.join(
                    directory, "build", target + (lang.executable_extension or "")
                ),
            )

    return SingleCompilationResult(
        verdict=CompilationOutcome.FAILED,
        standard_error=f"Source files {sources} are not recognized by any language.",
        exit_status=-1,
        produced_file=None,
    )


def make_clean(*, directory: str) -> None:
    # By default, Makefile is not called since we don't need to supply any environment variable for it to work.
    # TODO when custom Makefile is present, invoke it.
    if os.path.exists(os.path.join(directory, "build")):
        shutil.rmtree(os.path.join(directory, "build"))
