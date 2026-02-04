# Transcriber Project

## Overview
Web app for uploading audio and generating structured transcripts with a review UI.

## Requirements
- Python 3.11+
- Redis (for Celery broker)
- ffmpeg + ffprobe on PATH

## Setup
1. Create and activate a virtual environment.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set environment variables:
   ```bash
   # Windows (PowerShell)
   $env:DJANGO_SECRET_KEY="replace-with-your-secret"
   ```

## Run Django
```bash
python manage.py migrate
python manage.py runserver
```

## Run Celery
```bash
celery -A transcriber_project worker --concurrency=3 --pool=prefork -l info
```

## Notes
- Uploaded files are stored in `media/` (ignored by git).
- SQLite database is stored in `db.sqlite3` (ignored by git).

## Production Checklist
1. Set a strong `DJANGO_SECRET_KEY` in environment variables.
2. Set `DEBUG=False`.
3. Configure `ALLOWED_HOSTS`.
4. Use a production database (PostgreSQL recommended).
5. Configure Redis for Celery in production.
6. Ensure `ffmpeg` is installed on the server.
