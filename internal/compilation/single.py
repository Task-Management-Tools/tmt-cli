import shutil
import os

from internal.context import TMTContext
from internal.outcomes import SingleCompilationResult

from .languages import languages
from .makefile import make_compile_target


def compile_single(
    *,
    context: TMTContext,
    directory: str,
    sources: list[str],
    source_rename: list[str | None] = [],
    headers: list[str] = [],
    executable_filename_base: str,
    executable_stack_size_mib: int,
) -> SingleCompilationResult:
    """
    Compiles a single executable from sources and headers in directory.

    All paths and directories should be absolute paths.

    Args:
        context:
            The current TMT Context.
        directory:
            The absolute path to the compilation directory. The directory is assumed to be cleared beforehand.
        sources:
            The source files to be compiled.
        source_rename:
            The i-th source file will be renamed to the i-th element of this list, if it exists and it is not None.
        headers:
            The header files to be supplied in the compilation process.
        executable_filename_base:
            The base name of the target executable.
        executable_stack_size_mib:
            The maximum size allowed for the target executable, in MiB.
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

    src_in_dir = []
    source_rename += [None] * max(0, len(sources) - len(source_rename))
    for src, src_rename in zip(sources, source_rename):
        basename = src_rename or os.path.basename(src)
        shutil.copy(src, os.path.join(directory, basename))
        src_in_dir.append(basename)

    for header in headers:
        shutil.copy(header, directory)

    return make_compile_target(
        context=context,
        directory=directory,
        sources=src_in_dir,
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
