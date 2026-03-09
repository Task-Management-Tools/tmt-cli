import os
from typing import Type

from internal.context.context import TMTContext

from .languages.base import Language
from .languages import languages


def recognize_language(filenames: list[str], context: TMTContext) -> Type[Language] | None:
    """
    Returns the appropriate language type of the given filename, or None if no langauge matches.
    """
    for lang_type in languages:
        lang = lang_type(context)
        if all([os.path.splitext(src)[1] in lang.source_extensions for src in filenames]):
            return lang_type
    return None
