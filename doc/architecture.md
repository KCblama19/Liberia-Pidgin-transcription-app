# Transcriber Project Architecture

## 1. Purpose and scope

The Transcriber Project is a Django web application for turning interview audio into
reviewable, timestamped transcript segments. It is optimized for Liberian English and
Kolokwa/Pidgin interview material, while retaining the original transcription beside a
conservative normalized-English representation.

The application is currently a single Django project and application:

- `transcriber_project` contains runtime configuration, URL composition, WSGI/ASGI
  entry points, and Celery initialization.
- `transcription` contains the domain model, views, templates, browser assets, Celery
  tasks, processing services, and export adapters.
- PostgreSQL is the configured application database.
- Redis is the Celery broker.
- `media/` is the local file store for uploaded audio.
- FFmpeg/FFprobe are required operating-system executables.

This document describes the implementation as it exists in the repository, not a
proposed replacement architecture.

## 2. System context

```text
                           +----------------------+
                           |       Browser        |
                           | Upload / Processing  |
                           | Review / Export UI   |
                           +----------+-----------+
                                      |
                                      | HTTP, HTML, JSON, audio ranges
                                      v
+----------------+       +-----------+-----------+       +----------------+
| PostgreSQL     |<----->| Django web application |<----->| Local media/  |
| Transcription  |       | views, forms, templates|       | uploaded audio |
| records        |       +-----------+-----------+       +----------------+
+----------------+                   |
                                    | enqueue / status
                                    v
                           +--------+---------+
                           | Redis + Celery   |
                           | broker/results   |
                           +--------+---------+
                                    |
                                    v
                           +--------+---------+
                           | Celery worker    |
                           | processing task  |
                           +---+----------+---+
                               |          |
                               v          v
                         FFmpeg/FFprobe  Faster-Whisper
                               |
                               v
                     normalized/chunked WAV files
```

The worker writes progress and transcript data directly to PostgreSQL. The browser
does not perform speech recognition; it periodically reads the persisted status.

## 3. Runtime components

### Django web process

`transcriber_project/urls.py` exposes the admin and includes the transcription routes.
`settings.py` configures templates, static/media paths, logging, database access,
Celery, and the transcription profile. The application uses Django's CSRF middleware,
sessions, authentication middleware, and standard security middleware.

The web process is responsible for:

1. Validating and saving upload form data.
2. Creating and updating `Transcription` records.
3. Scheduling Celery tasks after database commits.
4. Rendering upload, processing, list, and detail pages.
5. Returning status JSON and range-capable audio responses.
6. Saving reviewer edits.
7. Generating TXT, SRT, DOCX, and PDF downloads.

### Celery worker

`transcriber_project/celery.py` creates the Celery application and autodiscovers
`transcription/tasks.py`. The processing task is bound, retries exceptions with
exponential backoff, and allows up to three retries. Its result backend is configured
through `django-celery-results`; Redis is the broker.

The worker calls the synchronous `process_transcription()` service. The service uses a
`ThreadPoolExecutor`, although the current `MAX_TRANSCRIBE_WORKERS` value is `1`.
Whisper's model is lazy-loaded once per worker process and protected by a lock.

### Database

The configured database is PostgreSQL, with schema changes represented by Django
migrations. The repository also contains local SQLite/recovery artifacts in the working
tree; those are not the configured production database contract.

### File and media storage

Uploaded files use Django's `FileField` with the `audio/` upload prefix. The default
local storage root is `MEDIA_ROOT`, normally the repository's `media/` directory.
Processing creates normalized WAV files and, for long inputs, a sibling chunks
directory. The current code does not provide a general cleanup job for generated
normalized/chunk files.

### External/local dependencies

- **FFmpeg** normalizes audio and creates chunks.
- **FFprobe** reads duration.
- **Faster-Whisper** loads the local
  `systran/faster-whisper-medium` model with CPU/int8 settings.
- **Redis** transports Celery messages.
- **PostgreSQL** stores application records and JSON transcript data.
- **python-docx** and **ReportLab** implement DOCX and PDF exports.

## 4. Domain model and state

The central model is `transcription.models.Transcription`.

| Field | Meaning |
|---|---|
| `audio_file` | Uploaded source audio, stored below `MEDIA_ROOT/audio/`. |
| `uploaded_at` | Creation timestamp. |
| `raw_transcript` | Reserved text field; the current pipeline primarily stores segments instead. |
| `normalized_english` | Reserved aggregate normalized text field; current processing stores normalized text per segment. |
| `structured_segments` | JSON list containing timestamps, speaker, type, original text, normalized English, and speaker color. |
| `status` | `UPLOADED`, `PROCESSING`, `DONE`, `CANCELLED`, or `ERROR`. |
| `progress` | Integer percentage persisted during chunk completion. |
| `current_stage` | Stage label exposed by the status endpoint; the current pipeline does not update it during processing. |
| `error_message` | Last processing error text. |
| `cancel_requested` | Database-backed cancellation request shared by web and worker processes. |

A typical structured segment has this shape:

```json
{
  "start": 12.4,
  "end": 17.8,
  "speaker": "UNKNOWN",
  "speaker_color": "bg-red-100 text-red-800",
  "type": "Answer",
  "original": "raw recognized text",
  "english": "Normalized recognized text"
}
```

`text` may also appear after review edits because the detail view's regular POST edit
path writes that key. The AJAX endpoint specifically edits `original` or `english`.

### State transitions

```text
UPLOADED/PENDING
       |
       v
   PROCESSING --------------------+
    |       |                     |
    |       +--> CANCELLED        |
    +----------> ERROR <----------+
    |
    +----------> DONE
```

An upload schedules processing after its transaction commits. The processing page is
read-only for GET requests. Explicit POST retry is allowed only for `ERROR` or
`CANCELLED` records. A worker claims only `UPLOADED`/`PENDING` records using a
transaction and conditional update. Cancellation is cooperative but database-backed:
the web process sets `cancel_requested` and `CANCELLED`, and the worker checks that
state between chunk results and at finalization.
The former queued cancellation task remains as a no-op compatibility handler so stale
messages cannot cancel a later explicit retry.

## 5. HTTP and presentation architecture

### Routes

The `transcription` URL module exposes:

- `/` — upload form and upload submission.
- `/list/` — searchable, sortable, paginated transcript list.
- `/transcription/processing/` — processing dashboard.
- `/transcription/<id>/processing/` — one transcript's processing page.
- `/transcription/<id>/status/` — status/progress JSON.
- `/transcription/<id>/` — transcript review page.
- `/transcription/<id>/audio/` — streamed audio, including byte ranges.
- `/transcription/<id>/save_segment/` — AJAX segment edit.
- `/transcription/<id>/cancel/` — cancellation request.
- `/transcription/<id>/delete/` and `/transcriptions/delete/` — single/bulk deletion.
- `/export/<id>/` — format-selectable export.
- `/<id>/translate/` — optional LLM normalization endpoint.

### Browser UI

Templates extend `transcription/base.html`, which provides navigation to upload,
processing, and interviews. The page-specific JavaScript handles:

- drag/drop and file selection, preview, queue presentation, and upload progress;
- polling status and updating progress/stage/status controls;
- retry/cancel dashboard actions;
- list selection helpers and bulk actions;
- audio playback, segment navigation, editing, autosave, and export controls.

The backend remains authoritative: browser state is refreshed from database-backed
status and segment data.

### Audio streaming

`transcription_audio` checks the stored file, detects its MIME type, and returns a
`StreamingHttpResponse`. `Range: bytes=start-end` requests receive `206 Partial
Content` and `Content-Range`, `Content-Length`, and `Accept-Ranges` headers. This enables
seeking in long recordings without loading the whole file into memory.

## 6. Transcription pipeline

The end-to-end worker pipeline is implemented in
`transcription/services/process_transcription.py`.

1. **Load and guard**  
   Fetch the record, obtain its cancellation event, and stop immediately if already
   cancelled.
2. **Mark processing**  
   Set `status=PROCESSING` and reset progress.
3. **Normalize audio**  
   FFmpeg converts the source to mono, 16 kHz, signed PCM WAV.
4. **Read duration and chunk**  
   FFprobe reads duration. Inputs up to 600 seconds use one normalized file. Longer
   inputs are split into 600-second chunks with a two-second overlap.
5. **Transcribe chunks**  
   Each chunk is passed to Faster-Whisper with English forced, temperature zero,
   previous-text conditioning disabled, and beam size `1` in fast mode or `5`
   otherwise. Very short recognized text is discarded.
6. **Classify raw segments**  
   Speaker tags such as `P1:` at the beginning of a segment are recognized. Text is
   classified as a question when it contains `?` or common interrogative words;
   otherwise it is an answer. Repeated unknown questions can be inferred as
   `INTERVIEWER`.
7. **Apply absolute timestamps**  
   Chunk-relative timestamps receive the chunk's original-audio start offset.
8. **Normalize language**  
   The regex normalization engine applies prioritized, conservative Kolokwa/Liberian
   English rules. It writes normalized text to `english` while preserving `original`.
9. **Deduplicate overlap**  
   Adjacent or nearly touching segments with at least 0.92 normalized-text similarity
   are treated as overlap duplicates. The earliest segment is retained and its end may
   be extended.
10. **Persist partial results**  
    Each completed chunk updates `structured_segments` and percentage progress, so
    completed work is visible if a later chunk fails.
11. **Finalize**  
    Segments are sorted by absolute start/end, deduplicated once more, and the record is
    marked `DONE` at 100 percent.

Failures are logged through the `transcription` logger, stored in `error_message`, and
re-raised so Celery retry behavior remains active.

## 7. Normalization and optional semantic translation

The active path is deterministic:

```text
Whisper original text
        |
        v
NormalizerEngine
  prioritized regex rules
        |
        v
segment["english"]
```

`kolokwa_normalizer.py` contains the phrase rules, while `regex_normalizer.py` wraps
them in reusable prioritized rules and returns optional match metadata. The older
`translator.py` module is intentionally deprecated and unused.

The `llm_normalizer.py` path is optional and intended for semantic standard-English
normalization. The translate endpoint applies it segment by segment and updates
`english`. It depends on configured external LLM settings and is described in the
README as disabled by default.

## 8. Export architecture

`ExportManager` maps a requested format to a `BaseExporter` implementation:

| Format | Implementation | Output |
|---|---|---|
| `txt` | `TxtExporter` | UTF-8 plain text |
| `srt` | `SrtExporter` | Subtitle-style numbered entries |
| `docx` | `DocxExporter` | Word document bytes |
| `pdf` | `PdfExporter` | PDF bytes |

All exporters consume the structured segment list and options for timestamps and
speakers. They export `english`, not `original`. The view derives a sanitized download
filename from the uploaded audio name.

## 9. Observability and failure handling

Application logs are written to `logs/app.log` and `logs/errors.log`, with console
output enabled for the `transcription` logger. Chunk start, completion, failure,
progress, cancellation, and final completion are logged.

Failure boundaries are:

- FFprobe/FFmpeg errors become explicit runtime errors.
- Missing audio chunks raise `FileNotFoundError`.
- Processing failures persist `ERROR` and the exception text.
- Celery retries task exceptions up to three times.
- Invalid byte ranges return HTTP 416.
- Missing media returns HTTP 404.
- Unsupported export formats raise an explicit `ValueError`.

## 10. Configuration and deployment shape

Development startup is:

```text
PostgreSQL + Redis + FFmpeg/FFprobe
        |
        +-- python manage.py migrate
        +-- python manage.py runserver
        +-- celery -A transcriber_project worker --concurrency=3 --pool=prefork -l info
```

Each upload stores a selectable `model_profile`:

- `fast_cpu`: small Faster-Whisper model with CPU/int8 and a low beam size.
- `balanced_cpu`: medium model with CPU/int8, recommended for the project's
  i7-8650U/16 GB machine.
- `quality_cpu`: medium model with a larger beam size and more CPU threads.
- `quality_gpu`: large-v3-turbo with CUDA/float16 for supported NVIDIA systems.

Models are loaded lazily per worker with `local_files_only=True`, so stronger
machines must have the selected model installed locally. Uploads also receive
server-side extension, MIME, size, FFprobe, and duration validation. The
idempotency key prevents repeated submissions from creating duplicate records.
The selected profile, detected language, task identifiers, attempt count,
timestamps, processing stage, and heartbeat are persisted with each record.
Optional pyannote speaker diarization is enabled only through configuration and
requires its separate dependency and Hugging Face token.

The repository README recommends production settings that are stricter than the
development defaults: a strong secret, `DEBUG=False`, configured hosts, PostgreSQL,
Redis, and installed FFmpeg.

## 11. Architectural constraints and known implementation gaps

These are important when extending or operating the application:

1. **Model ownership is process-local.** Each Celery worker process lazily loads its own
   Whisper model; memory and CPU requirements therefore scale with worker processes.
2. **Cancellation is cooperative.** The database flag is shared across web and worker
   processes, but an already-running native FFmpeg or Whisper call may not be
   interruptible until it returns to a pipeline checkpoint.
3. **Progress is chunk-based.** There is no finer-grained progress within FFmpeg or an
   individual Whisper call.
4. **Transcript fields are partly transitional.** The pipeline primarily uses
   `structured_segments`; `raw_transcript` and `normalized_english` remain model fields
   but are not populated by the current pipeline.
5. **Authentication/authorization is not enforced on transcript routes.** The current
   UI is effectively single-user and routes identify records by integer ID.
6. **Retries are typed and bounded.** Only `RetryableTranscriptionError` is
   automatically retried. Other processing errors become `ERROR` and require
   an explicit user retry, avoiding duplicate expensive runs and preserving
   terminal cancellation.
7. **Local storage is assumed.** Media and generated processing files are not abstracted
   behind a cleanup or object-storage lifecycle in the current implementation.
8. **Schema and runtime configuration must agree.** The checked-in settings configure
   PostgreSQL even though local recovery/SQLite files may exist in a developer
   workspace.
9. **Temporary artifacts need scheduled cleanup.** The pipeline cleans normal
   artifacts in its `finally` path; `manage.py cleanup_transcription_temp
   --dry-run` finds stale normalized files and chunk directories left by crashes.
