from .abc import Language
from .cpp import LanguageCpp
from .python import LanguagePython3

languages: list[Language] = [LanguageCpp, LanguagePython3]

__all__ = ["languages"]
