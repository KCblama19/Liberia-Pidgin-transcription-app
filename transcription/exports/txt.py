from .base import BaseExporter
from .utils import format_hhmmss

class TxtExporter(BaseExporter):

    def export(self, segments, options):
        lines = []

        for segment in segments:
            line = ""
            if options.get("include_timestamps"):
                start = format_hhmmss(segment["start"])
                end = format_hhmmss(segment["end"])
                line += f"[{start} - {end}] "
            if options.get("include_speakers"):
                line += f"{segment['speaker']}: "
            line += segment["english"]
            lines.append(line)

        return "\n".join(lines).encode("utf-8")
