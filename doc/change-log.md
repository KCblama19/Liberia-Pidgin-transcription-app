# Celery Transcription Lifecycle Change Briefing

## Purpose

This change set fixes duplicate transcription execution, unsafe page-triggered
restarts, unreliable cross-process cancellation, stale result writes, and temporary
audio-file cleanup.

## Change summary

| Location | Change | Why |
|---|---|---|
| [transcription/views.py](../transcription/views.py) | Removed task submission from processing-page GET requests. | Refreshing a page, opening the dashboard, or polling status must not enqueue or restart work. |
| [transcription/views.py](../transcription/views.py) | Added explicit POST-only retry for `ERROR` and `CANCELLED` records. | Retries are deliberate actions, not side effects of rendering a page. `DONE` and active records cannot be retried through this path. |
| [transcription/views.py](../transcription/views.py) | Added `_submit_processing_task()` with `transaction.on_commit()`. | Tasks are published only after the database row exists; broker failures are recorded as `ERROR` instead of silently appearing active. |
| [transcription/views.py](../transcription/views.py) | Corrected upload task ID capture to use `transcription.pk`. | The previous code read `transaction.pk`, which is the transaction manager rather than the saved model ID. |
| [transcription/views.py](../transcription/views.py) | Cancellation now updates `CANCELLED` and `cancel_requested` synchronously. | Cancellation works even when a `--pool=solo` worker is busy and cannot execute a second cancellation task. |
| [transcription/models.py](../transcription/models.py) | Added `cancel_requested = BooleanField(default=False)`. | Provides shared cancellation state visible to both Django and Celery processes. |
| [transcription/migrations/0012_transcription_cancel_requested.py](../transcription/migrations/0012_transcription_cancel_requested.py) | Added the schema migration for `cancel_requested`. | Makes the cancellation protocol persistent and deployable through normal Django migrations. |
| [transcription/services/cancel.py](../transcription/services/cancel.py) | Replaced process-local `threading.Event` as the authority with database reads/writes. | Django and worker processes do not share Python memory; database state survives worker boundaries and restarts. |
| [transcription/services/cancel.py](../transcription/services/cancel.py) | Added `TranscriptionCancelled` and `is_cancel_requested()`. | Gives the pipeline an explicit, non-error control flow for cooperative cancellation. |
| [transcription/services/process_transcription.py](../transcription/services/process_transcription.py) | Added atomic `_claim_transcription()`. | Only `UPLOADED`/`PENDING` records can be claimed, preventing stale or duplicate queued tasks from rerunning completed/cancelled work. |
| [transcription/services/process_transcription.py](../transcription/services/process_transcription.py) | Changed progress and final writes to conditional queryset updates. | A stale worker cannot overwrite a newer cancellation or terminal status. |
| [transcription/services/process_transcription.py](../transcription/services/process_transcription.py) | Added cancellation checks before work, between chunks, and before finalization. | Prevents later chunks and `DONE` finalization from being accepted after cancellation. |
| [transcription/services/process_transcription.py](../transcription/services/process_transcription.py) | Bounded chunk submission instead of submitting every chunk immediately. | Prevents queued executor work from starting unnecessary later chunks before cancellation is observed. |
| [transcription/services/process_transcription.py](../transcription/services/process_transcription.py) | Added explicit handling for `TranscriptionCancelled`. | Cancellation exits cleanly without being converted into `ERROR` or retried. |
| [transcription/tasks.py](../transcription/tasks.py) | Removed broad `autoretry_for=(Exception,)`. | Permanent input/state failures and cancellation must not automatically create more expensive duplicate runs. |
| [transcription/tasks.py](../transcription/tasks.py) | Failure updates now require `PROCESSING` and `cancel_requested=False`. | A failure from an obsolete worker cannot replace a newer cancellation. |
| [transcription/tasks.py](../transcription/tasks.py) | Made `cancel_transcription_task` a no-op compatibility handler. | Existing Redis cancellation messages can be acknowledged without cancelling a later explicit retry. |
| [transcription/services/audio_chunker.py](../transcription/services/audio_chunker.py) | Added `cleanup_chunks()`. | Removes generated chunk directories and normalized WAV files after success, failure, or cancellation. |
| [transcriber_project/test_settings.py](../transcriber_project/test_settings.py) | Added in-memory SQLite test settings and eager Celery settings. | Allows ordinary unit tests to run without PostgreSQL, Redis, or a live worker. |
| [transcription/tests/test_task_lifecycle.py](../transcription/tests/test_task_lifecycle.py) | Added lifecycle tests for upload, GET idempotence, read-only polling, duplicate tasks, cancellation, retries, broker failure, and success. | Locks in the intended queue and status behavior without downloading or running Whisper. |
| [doc/architecture.md](../doc/architecture.md) | Updated architecture documentation. | Records database-backed cancellation, atomic claiming, explicit retry, and no-op legacy cancellation handling. |
| [doc/workflow.md](../doc/workflow.md) | Updated operational workflow documentation. | Explains the new upload, retry, cancellation, stale-message, and recovery behavior. |

## Resulting lifecycle

```text
Upload transaction commits
        |
        v
One processing task is published
        |
        v
Task atomically claims UPLOADED/PENDING
        |
        v
PROCESSING -> partial progress writes -> DONE
        |
        +--> database cancellation request
                  |
                  v
              CANCELLED
```

GET requests are read-only. Retry is an explicit POST. Cancellation is a database
operation and does not depend on a separate task being scheduled or executed.

## Validation

Passed:

```text
python manage.py check --settings=transcriber_project.test_settings
python manage.py makemigrations --check --dry-run --settings=transcriber_project.test_settings
python manage.py test transcription.tests.test_task_lifecycle --settings=transcriber_project.test_settings
python -m compileall -q transcription transcriber_project
git diff --check
```

The lifecycle test suite passes with 11 tests. The full transcription suite still has
two unrelated pre-existing Kolokwa normalizer failures involving `"I now know"` and
`"da one"`.

## Deployment note

Run the new migration before using the updated code:

```powershell
.\venv_windows_py311\Scripts\python.exe manage.py migrate
```

No Redis queue purge, database deletion, uploaded-file deletion, or destructive worker
operation was performed.
