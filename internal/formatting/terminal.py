from .plain import PlainFormatter


class TerminalFormatter(PlainFormatter):
    """
    Implements formatting behavior in the terminals.
    """

    def __init__(self):
        super().__init__()
        self.ANSI_RESET = self.AnsiSequence("\033[0m")
        self.ANSI_RED = self.AnsiSequence("\033[31m")
        self.ANSI_GREEN = self.AnsiSequence("\033[32m")
        self.ANSI_YELLOW = self.AnsiSequence("\033[33m")
        self.ANSI_BLUE = self.AnsiSequence("\033[34m")
        self.ANSI_PURPLE = self.AnsiSequence("\033[35m")
        self.ANSI_RED_BG = self.AnsiSequence("\033[41m")
        self.ANSI_GREY = self.AnsiSequence("\033[90m")
        self.ANSI_ORANGE = self.AnsiSequence("\033[38:5:172m")
