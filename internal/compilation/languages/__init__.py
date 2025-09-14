from typing import Type

from .base import Language
from .cpp import LanguageCpp
from .python import LanguagePython3

languages: list[Type[Language]] = [LanguageCpp, LanguagePython3]

__all__ = ["languages"]
