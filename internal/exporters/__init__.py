from .base import BaseExporter, CommandExportSummary
from .domjudge_legacy import DOMJudgeLegacyExporter
from .cms_tps import CMSTPSExporter

exporters: dict[str, type[BaseExporter]] = {
    "domjudge-legacy": DOMJudgeLegacyExporter,
    "cms-tps": CMSTPSExporter,
}

__all__ = [
    "CommandExportSummary",
    "BaseExporter",
    "DOMJudgeLegacyExporter",
    "CMSTPSExporter",
    "exporters",
]
