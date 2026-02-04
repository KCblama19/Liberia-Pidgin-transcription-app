from celery import shared_task
from django.db import transaction
from django.apps import apps
from .services.process_transcription import process_transcription
from .services.cancel import cancel_transcription


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def process_transcription_task(self, transcription_id, fast_mode=True):
    try:
        process_transcription(transcription_id, fast_mode)
    except Exception as exc:
        # Best-effort status update before retry/raise
        Transcription = apps.get_model("transcription", "Transcription")
        with transaction.atomic():
            Transcription.objects.filter(id=transcription_id).update(
                status="ERROR",
                error_message=str(exc),
            )
        raise


@shared_task(bind=True)
def cancel_transcription_task(self, transcription_id):
    cancel_transcription(transcription_id)

    Transcription = apps.get_model("transcription", "Transcription")
    Transcription.objects.filter(id=transcription_id).update(status="CANCELLED")
