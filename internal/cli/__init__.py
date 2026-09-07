"""An `argparse` wrapper.

Combines `argparse` with decorator-based registration (`command`, `option`,
`argument`) and type-directed dependency injection (`App.provide`).
"""

from internal.cli.app import App
from internal.cli.decorators import argument, command, option

__all__ = ["App", "argument", "command", "option"]
