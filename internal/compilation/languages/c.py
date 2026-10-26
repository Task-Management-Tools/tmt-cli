from .c_family import CFamilyLanguage


class LanguageC(CFamilyLanguage):
    @property
    def id(self):
        return "c"

    @property
    def name(self):
        return "C"

    @property
    def source_extensions(self):
        return [".c"]

    @property
    def flag_environment_variable(self):
        return "CFLAGS"
