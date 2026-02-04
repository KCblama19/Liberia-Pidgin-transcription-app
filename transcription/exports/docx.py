from .base import BaseExporter
from docx import Document
from io import BytesIO
from .utils import format_hhmmss

class DocxExporter(BaseExporter):

    def export(self, segments, options):
        doc = Document()

        for segment in segments:
            text = ""
            if options.get("include_timestamps"):
                start = format_hhmmss(segment["start"])
                end = format_hhmmss(segment["end"])
                text += f"[{start} - {end}] "
            if options.get("include_speakers"):
                text += f"{segment['speaker']}: "
            text += segment["english"]
            doc.add_paragraph(text)

        buffer = BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        return buffer.read()
