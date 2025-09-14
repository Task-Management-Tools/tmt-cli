import subprocess
import os

from internal.context import TMTContext
from internal.outcome import CompilationOutcome, SingleCompilationResult
from internal.runner import Process, wait_for_outputs

from .languages import languages


def compile_single(
    *,
    context: TMTContext,
    directory: str,
    sources: list[str],
    executable_filename_base: str,
    executable_stack_size_mib: int,
) -> SingleCompilationResult:
    compilation_time_limit_sec = context.config.trusted_step_time_limit_sec
    compilation_memory_limit_mib = context.config.trusted_step_memory_limit_mib

    compile_process: Process | None = None
    allout, allerr = "", ""

    produced_file = None
    for lang_type in languages:
        lang = lang_type(context)
        if all(
            [
                any([src.endswith(ext) for ext in lang.source_extensions])
                for src in sources
            ]
        ):
            compilation_commands = lang.get_compile_single_commands(
                source_filenames=sources,
                executable_filename_base=executable_filename_base,
                executable_stack_mib=executable_stack_size_mib,
            )
            try:
                for command in compilation_commands:
                    compile_process = Process(
                        command,
                        preexec_fn=lambda: os.chdir(directory),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        time_limit_sec=compilation_time_limit_sec,
                        memory_limit_mib=compilation_memory_limit_mib,
                    )

                stdout, stderr = wait_for_outputs(compile_process)
                allout += stdout
                allerr += stderr

                produced_file = executable_filename_base + (
                    lang.executable_extension or ""
                )
            finally:
                if compile_process is not None:
                    compile_process.safe_kill()

            break

    if compile_process is None:
        return SingleCompilationResult(
            verdict=CompilationOutcome.FAILED,
            standard_error=f"Source files {sources} are not recognized by any language.",
            exit_status=-1,
            produced_file=produced_file,
        )

    verdict: CompilationOutcome
    if compile_process.is_timedout:
        verdict = CompilationOutcome.TIMEDOUT
    elif compile_process.status != 0:
        verdict = CompilationOutcome.FAILED
    else:
        verdict = CompilationOutcome.SUCCESS

    return SingleCompilationResult(
        verdict=verdict,
        standard_output=allout,
        standard_error=allerr,
        exit_status=produced_file,
    )


def get_run_single_command(
    *,
    context: TMTContext,
    directory: str,
    executable_filename_base: str,
    executable_stack_size_mib: int,
) -> list[str] | None:
    exe_base = os.path.join(directory, executable_filename_base)
    if os.path.exists(exe_base) and os.path.isfile(exe_base):
        return [exe_base]

    for lang_type in languages:
        lang = lang_type(context)
        if lang.executable_extension is None:
            continue

        exe_file = exe_base + lang.executable_extension
        if os.path.exists(exe_file) and os.path.isfile(exe_file):
            return lang.get_execution_command(exe_base, executable_stack_size_mib)
    return None

def get_all_executable_ext(
    *,
    context: TMTContext
) -> list[str] | None:
    return list(set([lang_type(context).executable_extension for lang_type in languages]))