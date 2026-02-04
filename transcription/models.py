from django.db import models

class Transcription(models.Model):
    audio_file = models.FileField(upload_to="audio/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    raw_transcript = models.TextField(blank=True)
    normalized_english = models.TextField(blank=True)
    structured_segments = models.JSONField(default=list)

    status = models.CharField(
        max_length=20,
        choices=[
            ("UPLOADED", "UPLOADED"),
            ("PROCESSING", "PROCESSING"),
            ("DONE", "DONE"),
            ("CANCELLED", "CANCELLED"),
            ("ERROR", "ERROR"),
        ],
        default="UPLOADED"
    )

    progress = models.IntegerField(default=0)
    current_stage = models.CharField(
        max_length=50,
        default="FILE_RECEIVED"
    )
    error_message = models.TextField(blank=True)

    def __str__(self):
        return f"Transcription {self.id}"
