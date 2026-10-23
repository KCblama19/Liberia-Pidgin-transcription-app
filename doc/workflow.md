# Transcriber Project Workflow

## 1. Workflow overview

The project workflow has four user-facing phases:

```text
Upload audio
    -> Queue background processing
    -> Monitor progress / retry / cancel
    -> Review and edit transcript
    -> Export or delete result
```

The browser provides the interaction layer, Django persists state, and Celery performs
the expensive audio and speech work outside the web request.

## 2. Environment preparation

Before starting the application, provide:

1. Python 3.11 or newer.
2. A virtual environment.
3. Dependencies from `requirements.txt` (or `requirements_windows.txt` on Windows).
4. PostgreSQL configured through the environment variables consumed by
   `transcriber_project/settings.py`.
5. Redis on `localhost:6379` unless `CELERY_BROKER_URL` is changed.
6. `ffmpeg` and `ffprobe` available on `PATH`.
7. A real `DJANGO_SECRET_KEY` outside development.
8. A downloaded local Faster-Whisper model matching the configured
   `systran/faster-whisper-medium` and `local_files_only=True` behavior.

Typical setup:

```bash
python -m venv venv
# activate the environment
pip install -r requirements.txt
python manage.py migrate
```

On Windows, use:

```powershell
python -m venv venv
# activate the environment
pip install -r requirements_windows.txt
python manage.py migrate
```

## 3. Start the services

Run the Django web process:

```bash
python manage.py runserver
```

In a separate terminal, run the Celery worker:

```bash
celery -A transcriber_project worker --concurrency=3 --pool=prefork -l info
```

The web process accepts requests and publishes task messages. The worker must be
running for uploaded audio to progress beyond its initial state.

## 4. Upload workflow

1. Open `/`.
2. Select or drag an MP3, WAV, M4A, AAC, or MPEG audio file into the upload area.
3. The browser validates the queue presentation, shows file information and an optional
   preview, and submits the multipart form.
4. Django validates `TranscriptionUploadForm`, which currently contains the
   `audio_file` field.
5. Within a database transaction, Django creates a `Transcription` with:
   - `status=UPLOADED`;
   - `progress=0`;
   - the uploaded file saved under `media/audio/`.
6. `transaction.on_commit()` publishes `process_transcription_task` only after the
   record is committed, preventing a worker from receiving an ID whose database row is
   not yet durable.
7. The browser redirects to the processing page for the new record.

The upload UI can present a queue and multiple selected files, but each backend form
submission creates one `Transcription` record. Sequential client-side upload behavior
should therefore be treated as multiple single-file submissions.

## 5. Background processing workflow

### Task dispatch

`process_transcription_task` receives a transcription ID and `fast_mode` flag. It calls
the service layer and re-raises exceptions after recording `ERROR`, allowing Celery's
configured retry policy to run.

Opening a processing URL never starts a task. A task can be submitted by the upload
commit hook or by an explicit retry POST for an `ERROR`/`CANCELLED` record.

### Audio preparation

The worker:

1. Loads the record.
2. Checks its cancellation event.
3. Marks it `PROCESSING`.
4. Converts the source to 16 kHz mono PCM WAV with FFmpeg.
5. Uses FFprobe to determine duration.
6. Keeps short files as one chunk.
7. Splits longer files into 600-second chunks with a two-second overlap.

Old chunk directories for the same normalized input are removed before new chunks are
created.

### Recognition and segment construction

For every chunk:

1. The lazily initialized Faster-Whisper model recognizes English speech.
2. Segments shorter than two characters are ignored.
3. Chunk-relative times are shifted by the chunk's absolute start.
4. Speaker labels are inferred from leading `P<number>` tags when present.
5. Question/answer type is inferred using punctuation and interrogative words.
6. Conservative Kolokwa normalization creates the `english` value.

The worker can submit chunk jobs through a thread pool. The current constant limits
this to one active transcription chunk, so completion order is currently simple but
the code still preserves each chunk index and sorts final results by timestamps.

### Incremental persistence

After each completed chunk, the worker:

1. Adds the structured segments.
2. Removes likely duplicates caused by the two-second overlap.
3. Saves the partial JSON segment list.
4. Saves percentage progress.

This makes partial results visible and reduces lost work if a later chunk fails.

### Completion

After all chunks:

1. Cancellation is checked again.
2. Segments are sorted by `(start, end)`.
3. Deduplication runs one final time.
4. `structured_segments` is saved.
5. `progress=100` and `status=DONE` are saved.

On an exception, the worker logs the traceback, stores the message in
`error_message`, marks the record `ERROR`, and re-raises it for Celery retry handling.

## 6. Processing dashboard workflow

The processing dashboard lists records in `UPLOADED`, `PENDING`, or `PROCESSING`.
It also displays counts for active, completed, error, and cancelled records.

The browser polls `/transcription/<id>/status/` and uses the response to update:

- status badge;
- progress bar and percentage;
- current stage text;
- error text;
- elapsed time and estimated completion information;
- retry, cancel, and view-transcript controls.

When a record reaches `DONE`, the user can open the review page. When it reaches
`ERROR`, the user can retry. When it is cancelled, the user can restart it through the
processing flow.

## 7. Cancel workflow

1. The user chooses Cancel for a processing item.
2. The browser sends a POST request to `/transcription/<id>/cancel/`.
3. Django immediately marks the record `CANCELLED` and sets the database-backed
   `cancel_requested` flag. It does not depend on a cancellation task running behind a
   long job on a solo worker.
4. The processing service checks that shared state before starting, between completed chunks,
   and immediately before finalization.
5. If set, pending futures are cancelled where possible and the record remains
   `CANCELLED`.

Cancellation is cooperative rather than forceful. An FFmpeg or Whisper call already
running may finish before the next cancellation checkpoint.
Older queued cancellation messages are acknowledged by a compatibility no-op and do
not mutate state; the database update from the request is authoritative.

## 8. Review workflow

1. Open `/transcription/<id>/`.
2. The detail page loads the persisted structured segments and checks whether the
   original media file exists.
3. The audio player requests `/transcription/<id>/audio/`; range requests support
   seeking and segment playback.
4. Each segment displays its timestamp, speaker, type, original text, and normalized
   English.
5. The reviewer may edit segment text.
6. The browser can autosave individual `original` or `english` changes through
   `/transcription/<id>/save_segment/`.
7. A regular POST edit submission is also supported by the detail view.
8. Saved changes update the JSON field in place; no separate segment table is used.

The original recognition text is retained so a reviewer can compare it with the
normalized version. The normalization path is deliberately conservative because
aggressive word-level substitutions can change meaning in context.

## 9. Optional translation workflow

The detail UI can request `/transcription/<id>/translate/`. Django iterates over the
segments, sends the current `english` or `original` text to
`llm_normalize_to_standard_english`, writes the returned value to `english`, and
returns `{ "ok": true }`.

This is an optional semantic-normalization path, not the default transcription path.
It requires the configured LLM URL, API key, and model, and can incur external service
costs. The README describes the feature as disabled by default.

## 10. Export workflow

From the review page, request `/export/<id>/` with:

- `format=txt`, `pdf`, `docx`, or `srt`;
- `timestamps=1` to include start/end times where supported;
- `speakers=1` to include speaker labels.

The export view:

1. Loads the `Transcription`.
2. Selects an exporter through `ExportManager`.
3. Passes `structured_segments` and the option flags to the exporter.
4. Generates output from each segment's `english` value.
5. Sanitizes the uploaded audio basename.
6. Returns an attachment download with the selected extension.

TXT and DOCX use line-oriented text. SRT always includes subtitle timestamps and
numbering. PDF writes each segment to a page canvas and starts a new page when the
vertical space is exhausted.

## 11. List, delete, and recovery workflows

### List and search

`/list/` supports:

- search by uploaded audio filename;
- status filtering;
- newest, oldest, or status ordering;
- pagination with a bounded page size between 5 and 100.

### Delete

Single and bulk deletion remove the stored audio file first, then delete the database
record. Deletion is a POST operation from the UI.

### Recovery

For an error:

1. Inspect the displayed error message and worker logs.
2. Confirm PostgreSQL, Redis, FFmpeg, FFprobe, and the local Whisper model are
   available.
3. Retry from the processing UI using the explicit POST retry action.
4. If the source file is missing, restore/re-upload it before retrying.

For a stuck job, verify the Celery worker and Redis broker, then inspect the persisted
record status. Cancellation state is stored in the database, so it remains visible
across web/worker processes and worker restarts.

## 12. Operational checklist

### Before processing

- PostgreSQL is reachable with the configured credentials.
- Redis is reachable at the broker URL.
- The Celery worker is running.
- FFmpeg and FFprobe resolve from the worker's `PATH`.
- The Faster-Whisper model is present locally.
- `MEDIA_ROOT` is writable and has sufficient free space.

### During processing

- Monitor Celery logs and `logs/app.log`.
- Confirm progress increases after chunk completions.
- Watch disk usage because normalized WAV and chunk files can be large.
- Avoid starting duplicate retries for the same active record; task claiming is
  conditional and only `UPLOADED`/`PENDING` records can be claimed.

### Before production deployment

- Set a strong secret key.
- Set `DEBUG=False`.
- Configure `ALLOWED_HOSTS`.
- Use a managed/production PostgreSQL database.
- Configure Redis availability and persistence as appropriate.
- Put media behind a deliberate storage and retention policy.
- Add authentication and authorization before exposing transcript IDs publicly.
- Add cleanup for generated normalized/chunk files.
- Validate upload size/type limits at the server boundary.
- Configure HTTPS and secure media access.

## 13. Testing and maintenance workflow

The repository contains tests under `transcription/tests`, including normalization
coverage. A focused development loop is:

```bash
python manage.py check
python manage.py test transcription
```

When changing the model:

```bash
python manage.py makemigrations
python manage.py migrate
```

When changing the pipeline, validate at least:

1. short audio that produces one chunk;
2. long audio that produces overlapping chunks;
3. cancellation between chunks;
4. an FFmpeg/FFprobe failure;
5. a worker retry;
6. reviewer edits and autosave;
7. all four export formats;
8. byte-range audio seeking.
