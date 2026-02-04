from .base import BaseExporter
from .utils import format_hhmmss

class SrtExporter(BaseExporter):

    def export(self, segments, options):
        lines = []
        index = 1

        for segment in segments:
            lines.append(str(index))

            # Format timestamps for SRT
            start = format_hhmmss(segment["start"])
            end = format_hhmmss(segment["end"])
            lines.append(f"{start} --> {end}")

            # Include speaker optionally
            text = segment["english"]
            if options.get("include_speakers"):
                text = f"{segment['speaker']}: {text}"

            lines.append(text)
            lines.append("")
            index += 1

        return "\n".join(lines).encode("utf-8")
