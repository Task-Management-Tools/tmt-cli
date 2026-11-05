from .c_family import CFamilyLanguage


class LanguageCpp(CFamilyLanguage):
    @property
    def id(self):
        return "cpp"

    @property
    def name(self):
        return "C++"

    @property
    def source_extensions(self):
        return [".cpp", ".cc"]

    @property
    def flag_environment_variable(self):
        return "CXXFLAGS"
