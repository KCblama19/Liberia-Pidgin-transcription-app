from .base import BaseExporter
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
from io import BytesIO
from .utils import format_hhmmss

class PdfExporter(BaseExporter):

    def export(self, segments, options):
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=LETTER)
        width, height = LETTER
        y = height - 40

        for segment in segments:
            text = ""
            if options.get("include_timestamps"):
                start = format_hhmmss(segment["start"])
                end = format_hhmmss(segment["end"])
                text += f"[{start} - {end}] "
            if options.get("include_speakers"):
                text += f"{segment['speaker']}: "
            text += segment["english"]

            # Draw text on PDF
            c.drawString(40, y, text)
            y -= 15

            # New page if space runs out
            if y < 40:
                c.showPage()
                y = height - 40

        c.save()
        buffer.seek(0)
        return buffer.read()
