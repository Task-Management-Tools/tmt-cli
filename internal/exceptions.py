class TMTMissingFileError(Exception):
    def __init__(self, filetype: str, filename: str, among_str: str | None = None):
        if among_str is None:
            msg = f'Cannot find (or cannot read) {filetype} file "{filename}"'
        else:
            msg = f'Cannot find (or cannot read) {filetype} file "{filename}" among {among_str}'
        super().__init__(msg)


class TMTInvalidConfigError(Exception):
    pass
