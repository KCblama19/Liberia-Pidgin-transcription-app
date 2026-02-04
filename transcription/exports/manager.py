# transcriptions/exports/manager.py

from .txt import TxtExporter
from .pdf import PdfExporter
from .docx import DocxExporter
from .srt import SrtExporter

class ExportManager:

    EXPORTERS = {
        "txt": TxtExporter,
        "pdf": PdfExporter,
        "docx": DocxExporter,
        "srt": SrtExporter,
    }

    @classmethod
    def get_exporter(cls, format):
        exporter_class = cls.EXPORTERS.get(format)

        if not exporter_class:
            raise ValueError("Unsupported export format")

        return exporter_class()