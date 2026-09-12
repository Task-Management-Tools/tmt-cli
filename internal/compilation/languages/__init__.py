from typing import Type

from .base import Language
from .cpp import LanguageCpp
from .java import LanguageJava
from .python import LanguagePython3

languages: list[Type[Language]] = [
    LanguageCpp,
    LanguageJava,
    LanguagePython3,
]

__all__ = ["languages"]
