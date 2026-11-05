from .base import Language
from .c import LanguageC
from .cpp import LanguageCpp
from .java import LanguageJava
from .kotlin import LanguageKotlin
from .python import LanguagePython3

languages: list[type[Language]] = [
    LanguageC,
    LanguageCpp,
    LanguageJava,
    LanguageKotlin,
    LanguagePython3,
]

__all__ = ["languages"]
