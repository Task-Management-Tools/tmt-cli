import subprocess
import os

from .cpp import LanguageCpp

from internal.context import TMTContext
from internal.outcome import CompilationOutcome, CompilationResult
from internal.runner import Process, wait_for_outputs

languages = [LanguageCpp]

__all__ = ["compile_wildcard_make"]

MAKE = "make"


def compile_wildcard_make(
    *, context: TMTContext, directory: str, executable_stack_size_mib: int
) -> CompilationResult:
    compilation_time_limit_sec = context.config.trusted_compile_time_limit_sec
    compilation_memory_limit_mib = context.config.trusted_compile_memory_limit_mib

    allout, allerr = "", ""

    compile_process: Process | None = None

    for lang_type in languages:
        lang = lang_type(context)

        make_info = lang.get_make_wildcard_command(executable_stack_size_mib)
        try:
            command = [MAKE, "-C", directory, "-f", make_info.makefile]
            compile_process = Process(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                time_limit_sec=compilation_time_limit_sec,
                memory_limit_mib=compilation_memory_limit_mib,
                env=os.environ | make_info.env,
            )

            stdout, stderr = wait_for_outputs(compile_process)
        finally:
            if compile_process is not None:
                compile_process.safe_kill()

        if compile_process.status != 0 or compile_process.is_timedout:
            break

        allout += stdout
        allerr += stderr

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
        standard_output=stdout,
        standard_error=stderr,
        exit_status=(compile_process.status if compile_process is not None else 0),
    )


def compile_targets_make(
    *,
    context: TMTContext,
    directory: str,
    sources: list[str],
    target: str,
    executable_stack_size_mib: int,
) -> CompilationResult:
    compilation_time_limit_sec = context.config.trusted_compile_time_limit_sec
    compilation_memory_limit_mib = context.config.trusted_compile_memory_limit_mib

    compile_process: Process | None = None

    for lang_type in languages:
        lang = lang_type(context)
        for ext in lang.source_extensions:
            if all([src.endswith(ext) for src in sources]):
                make_info = lang.get_make_target_command(executable_stack_size_mib)
                try:
                    command = [MAKE, "-C", directory, "-f", make_info.makefile]
                    compile_process = Process(
                        command,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        time_limit_sec=compilation_time_limit_sec,
                        memory_limit_mib=compilation_memory_limit_mib,
                        env={
                            "SRCS": " ".join(sources),
                            "TARGET_NAME": target,
                        }
                        | os.environ
                        | make_info.env,
                    )

                    stdout, stderr = wait_for_outputs(compile_process)
                finally:
                    if compile_process is not None:
                        compile_process.safe_kill()
                break

    if compile_process is None:
        return CompilationResult(
            verdict=CompilationOutcome.FAILED,
            standard_error=f"Source files {sources} is not recognized by any language.",
            exit_status=-1,
        )

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


def compile_targets_make(
    *,
    context: TMTContext,
    directory: str,
    sources: list[str],
    target: str,
    executable_stack_size_mib: int,
) -> CompilationResult:
    compilation_time_limit_sec = context.config.trusted_compile_time_limit_sec
    compilation_memory_limit_mib = context.config.trusted_compile_memory_limit_mib

    compile_process: Process | None = None

    for lang_type in languages:
        lang = lang_type(context)
        for ext in lang.source_extensions:
            if all([src.endswith(ext) for src in sources]):
                make_info = lang.get_make_target_command(executable_stack_size_mib)
                try:
                    command = [MAKE, "-C", directory, "-f", make_info.makefile]
                    compile_process = Process(
                        command,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        time_limit_sec=compilation_time_limit_sec,
                        memory_limit_mib=compilation_memory_limit_mib,
                        env={
                            "SRCS": " ".join(sources),
                            "TARGET_NAME": target,
                        }
                        | os.environ
                        | make_info.env,
                    )

                    stdout, stderr = wait_for_outputs(compile_process)
                finally:
                    if compile_process is not None:
                        compile_process.safe_kill()
                break

    if compile_process is None:
        return CompilationResult(
            verdict=CompilationOutcome.FAILED,
            standard_error=f"Source files {sources} is not recognized by any language.",
            exit_status=-1,
        )

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
