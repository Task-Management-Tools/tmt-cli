import shutil
import os

from internal.context import TMTContext
from internal.outcome import SingleCompilationResult

from .languages import languages
from .makefile import make_compile_targets


def compile_single(
    *,
    context: TMTContext,
    directory: str,
    sources: list[str],
    headers: list[str] = [],
    executable_filename_base: str,
    executable_stack_size_mib: int,
) -> SingleCompilationResult:
    """
    Compiles a single executable from sources and headers in directory.

    All paths and directories should be absolute paths.
    """
    # They are internal errors; the caller should resolve them into absolute path.
    if not os.path.isabs(directory):
        raise ValueError(f"compile single: {directory} is not an absolute path.")
    for source in sources:
        if not os.path.isabs(source):
            raise ValueError(f"compile single: {source} is not an absolute path.")
    for header in headers:
        if not os.path.isabs(header):
            raise ValueError(f"compile single: {header} is not an absolute path.")

    context.path.empty_directory(directory)
    # Copy in if it is not already in
    for i in range(len(sources)):
        if not os.path.samefile(os.path.dirname(sources[i]), directory):
            shutil.copy(sources[i], directory)
        sources[i] = os.path.basename(sources[i])
    for i in range(len(headers)):
        if not os.path.samefile(os.path.dirname(headers[i]), directory):
            shutil.copy(headers[i], directory)

    return make_compile_targets(
        context=context,
        directory=directory,
        sources=sources,
        target=executable_filename_base,
        executable_stack_size_mib=executable_stack_size_mib,
    )


def get_run_single_command(
    *,
    context: TMTContext,
    directory: str,
    executable_filename_base: str,
    executable_stack_size_mib: int,
) -> list[str] | None:
    exe_base = os.path.join(directory, executable_filename_base)

    for lang_type in languages:
        lang = lang_type(context)
        
        exe_file = exe_base + lang.executable_extension
        if os.path.exists(exe_file) and os.path.isfile(exe_file):
            return lang.get_execution_command(exe_base, executable_stack_size_mib)
    return None


def get_all_executable_ext(*, context: TMTContext) -> list[str | None]:
    return list(
        set([lang_type(context).executable_extension for lang_type in languages])
    )
