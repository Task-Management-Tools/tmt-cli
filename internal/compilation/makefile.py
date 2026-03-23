import subprocess
import shutil
import os
import glob

from internal.context import TMTContext
from internal.outcomes import (
    CompilationOutcome,
    CompilationResult,
    SingleCompilationResult,
)
from internal.process import Process, wait_for_outputs
from internal.exceptions import TMTMissingFileError

from .languages import languages
from .utils import recognize_language


def _get_make() -> list[str]:
    make_flags = os.environ.get("MAKEFLAGS", "").split()

    # TODO: configurable with per-user config
    if make := os.environ.get("MAKE"):
        return [make] + make_flags
    if shutil.which("gmake") is not None:
        return ["gmake"] + make_flags
    if shutil.which("make") is not None:
        return ["make"] + make_flags
    raise TMTMissingFileError("executable", "make", "PATH")


def make_compile_wildcard(
    *, context: TMTContext, directory: str, executable_stack_size_mib: int
) -> CompilationResult:
    """
    Compile all sources recognized by any langauges in the directory.
    """
    compilation_time_limit_sec = context.config.compile_time_limit_sec
    compilation_memory_limit_mib = context.config.compile_memory_limit_mib

    allout = allerr = ""

    make_all_process: Process | None = None

    # First, we detect if any source files could compile to the same executable.
    # This breaks many assuptions of the tool (for example the recipe), therefore it is an immediate error.
    executables: dict[str, str] = {}
    for source in glob.iglob("*", root_dir=directory):
        base, ext = os.path.splitext(source)
        if any(ext in lang(context).source_extensions for lang in languages):
            if base in executables:
                return CompilationResult(
                    verdict=CompilationOutcome.FAILED,
                    standard_output=f"Source files {source} and {executables[base]} are ambigious. Please rename one of them.",
                    exit_status=-1,
                )
            executables[base] = str(source)
    del executables

    # Run every langauge's wildcard Makefile to compile all possible sources
    for lang_type in languages:
        lang = lang_type(context)

        make_info = lang.get_make_wildcard_command(executable_stack_size_mib)

        command = _get_make() + [
            "--no-print-directory",
            "-C",
            directory,
            "-f",
            make_info.makefile,
        ]

        # Run all compilation first, then emit-log;
        # this way, we don't need to get our hands dirty setting them in Makefiles
        kwargs = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "time_limit_sec": compilation_time_limit_sec,
            "memory_limit_mib": compilation_memory_limit_mib,
            "env": make_info.extra_env | os.environ,
        }
        make_all_process = Process(command + ["all"], **kwargs)
        stdout, stderr = wait_for_outputs(make_all_process)
        allout += stdout
        allerr += stderr

        make_emit_log_process = Process(command + ["emit-log"], **kwargs)
        _, stderr = wait_for_outputs(make_emit_log_process)
        allerr += stderr

        if make_all_process.status != 0 or make_all_process.is_timedout:
            break

    verdict: CompilationOutcome
    if make_all_process is None:
        verdict = CompilationOutcome.SUCCESS
    elif make_all_process.is_timedout:
        verdict = CompilationOutcome.TIMEDOUT
    elif make_all_process.status != 0:
        verdict = CompilationOutcome.FAILED
    else:
        verdict = CompilationOutcome.SUCCESS

    return CompilationResult(
        verdict=verdict,
        standard_output=allout,
        standard_error=allerr,
        exit_status=(make_all_process.status if make_all_process is not None else 0),
    )


def make_compile_target(
    *,
    context: TMTContext,
    directory: str,
    sources: list[str],
    target: str,
    executable_stack_size_mib: int,
) -> SingleCompilationResult:
    """
    Compile the specific source file into the target executable recognized by a langauge that recognizes in the directory.

    This function assumes the directory is already set up for running make: it can be roughly thought as just running make in that directory with appropriate settings and returns the captured output.
    """

    compilation_time_limit_sec = context.config.compile_time_limit_sec
    compilation_memory_limit_mib = context.config.compile_memory_limit_mib

    compile_process: Process | None = None

    lang_type = recognize_language(sources, context)
    if lang_type is None:
        return SingleCompilationResult(
            verdict=CompilationOutcome.FAILED,
            standard_error=f"Source files {sources} are not recognized by any language.",
            exit_status=-1,
            produced_file=None,
        )

    lang = lang_type(context)
    make_info = lang.get_make_target_command(executable_stack_size_mib)

    command = _get_make() + [
        "--no-print-directory",
        "-C",
        directory,
        "-f",
        make_info.makefile,
    ]
    # Run all compilation first, then emit-log;
    # this way, we don't need to get our hands dirty setting them in Makefiles
    kwargs = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "time_limit_sec": compilation_time_limit_sec,
        "memory_limit_mib": compilation_memory_limit_mib,
        "env": make_info.extra_env
        | os.environ
        | {
            "SRCS": " ".join(sources),
            "TARGET_NAME": target,
        },
    }
    compile_process = Process(command, **kwargs)
    stdout, stderr = wait_for_outputs(compile_process)

    emit_log_process = Process(command + ["emit-log"], **kwargs)
    _, emitted_log = wait_for_outputs(emit_log_process)
    stderr += emitted_log

    verdict: CompilationOutcome
    if compile_process.is_timedout:
        verdict = CompilationOutcome.TIMEDOUT
    elif compile_process.status != 0:
        verdict = CompilationOutcome.FAILED
    else:
        verdict = CompilationOutcome.SUCCESS

    executable_file = os.path.join(
        directory, "build", target + lang.executable_extension
    )
    if not os.path.isfile(executable_file):
        executable_file = None
    return SingleCompilationResult(
        verdict=verdict,
        standard_output=stdout,
        standard_error=stderr,
        exit_status=compile_process.status,
        produced_file=executable_file,
    )


def make_clean(*, directory: str) -> None:
    # By default, Makefile is not called since we don't need to supply any environment variable for it to work.
    # TODO when custom Makefile is present, invoke it.
    if os.path.exists(os.path.join(directory, "build")):
        shutil.rmtree(os.path.join(directory, "build"))
