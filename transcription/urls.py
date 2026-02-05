from django.urls import path
from .views import *

app_name = "transcription"

urlpatterns = [
    path("", upload_audio, name="upload_audio"),
    path("list/", list_transcriptions, name="list_transcriptions"),
    path("transcription/<int:pk>/", transcription_detail, name="transcription_detail"),
    path("transcription/<int:pk>/audio/", transcription_audio, name="transcription_audio"),
    path("export/<int:transcript_id>/", export_transcript, name="export_transcript"),
    path("processing/", processing_dashboard, name="processing_dashboard"),
    path("transcription/<int:pk>/processing/", transcription_processing, name="transcription_processing"),
    path("transcription/<int:pk>/status/", transcription_status, name="transcription_status"),
    path('transcription/<int:pk>/save_segment/', save_segment, name='save_segment'),
    path("transcription/<int:pk>/cancel/", cancel_transcription, name="cancel_transcription"),
    path("transcription/<int:pk>/delete/", delete_transcription, name="delete_transcription"),
    path("transcriptions/delete/", delete_transcriptions_bulk, name="delete_transcriptions_bulk"),
    path("<int:pk>/translate/", translate_transcription, name="translate_transcription"),
]
