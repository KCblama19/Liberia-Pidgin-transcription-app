from django.contrib import admin
from .models import *

# Register your models here.
class TranscriptionAdmin(admin.ModelAdmin):
    list_display = ['audio_file', 'uploaded_at', 'raw_transcript', 'normalized_english', 'structured_segments']

admin.site.register(Transcription, TranscriptionAdmin)