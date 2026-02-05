import json

from django.core.paginator import Paginator
from django.shortcuts import render, redirect, get_object_or_404
import mimetypes
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from .models import Transcription
from .forms import TranscriptionUploadForm
from .tasks import process_transcription_task, cancel_transcription_task
from .services.llm_normalizer import llm_normalize_to_standard_english
from .exports.manager import ExportManager


def upload_audio(request):
    if request.method == "POST":
        form = TranscriptionUploadForm(request.POST, request.FILES)
        if form.is_valid():
            transcription = form.save(commit=False)
            transcription.status = "UPLOADED"
            transcription.progress = 0
            transcription.save()
            return redirect("transcription:transcription_processing", transcription.id)
    else:
        form = TranscriptionUploadForm()

    return render(request, "transcription/upload.html", {"form": form})


def transcription_processing(request, pk):
    transcription = get_object_or_404(Transcription, pk=pk)

    # Start the Celery task only if not already processing
    if transcription.status in ["UPLOADED", "PENDING", "ERROR", "CANCELLED"]:
        transcription.progress = 0
        transcription.error_message = ""
        transcription.status = "PROCESSING"
        transcription.save(update_fields=["status", "progress", "error_message"])
        process_transcription_task.delay(transcription.id)

    processing_list = list(
        Transcription.objects.filter(status__in=["UPLOADED", "PENDING", "PROCESSING"])
        .order_by("-uploaded_at")
    )
    if transcription not in processing_list:
        processing_list.insert(0, transcription)

    stats = {
        "active": len(processing_list),
        "done": Transcription.objects.filter(status="DONE").count(),
        "error": Transcription.objects.filter(status="ERROR").count(),
        "cancelled": Transcription.objects.filter(status="CANCELLED").count(),
    }

    return render(
        request,
        "transcription/processing.html",
        {
            "transcription": transcription,
            "processing_list": processing_list,
            "is_multi": len(processing_list) > 1,
            "stats": stats,
        },
    )


def processing_dashboard(request):
    processing_list = list(
        Transcription.objects.filter(status__in=["UPLOADED", "PENDING", "PROCESSING"])
        .order_by("-uploaded_at")
    )
    stats = {
        "active": len(processing_list),
        "done": Transcription.objects.filter(status="DONE").count(),
        "error": Transcription.objects.filter(status="ERROR").count(),
        "cancelled": Transcription.objects.filter(status="CANCELLED").count(),
    }
    return render(
        request,
        "transcription/processing.html",
        {
            "processing_list": processing_list,
            "is_multi": len(processing_list) > 1,
            "stats": stats,
        },
    )


def transcription_status(request, pk):
    transcription = get_object_or_404(Transcription, pk=pk)
    # Return real status and redirect URL
    return JsonResponse({
        "status": transcription.status.lower(),
        "redirect_url": f"/transcription/{transcription.id}",
        "progress": transcription.progress or 0,
        "file_name": os.path.basename(transcription.audio_file.name) if transcription.audio_file else f"transcript_{transcription.id}",
        "error_message": transcription.error_message or "",
        "current_stage": transcription.current_stage or "",
        "uploaded_at": transcription.uploaded_at.isoformat() if transcription.uploaded_at else "",
    })


@require_POST
def translate_transcription(request, pk):
    transcription = get_object_or_404(Transcription, pk=pk)

    segments = transcription.structured_segments or []
    updated = []
    for seg in segments:
        source_text = seg.get("english") or seg.get("original") or ""
        normalized = llm_normalize_to_standard_english(source_text)
        seg["english"] = normalized
        updated.append(seg)

    transcription.structured_segments = updated
    transcription.save(update_fields=["structured_segments"])

    return JsonResponse({"ok": True})


def list_transcriptions(request):
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "all").strip()
    sort = request.GET.get("sort", "newest").strip()

    transcriptions = Transcription.objects.all()

    if q:
        transcriptions = transcriptions.filter(audio_file__icontains=q)

    if status and status.lower() != "all":
        transcriptions = transcriptions.filter(status=status.upper())

    if sort == "oldest":
        transcriptions = transcriptions.order_by("uploaded_at")
    elif sort == "status":
        transcriptions = transcriptions.order_by("status", "-uploaded_at")
    else:
        transcriptions = transcriptions.order_by("-uploaded_at")

    try:
        page_size = int(request.GET.get("page_size", 10))
    except ValueError:
        page_size = 10
    page_size = max(5, min(page_size, 100))

    paginator = Paginator(transcriptions, page_size)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "transcription/list.html",
        {
            "transcriptions": page_obj,
            "page_obj": page_obj,
            "q": q,
            "status_filter": status,
            "sort": sort,
            "page_size": page_size,
        },
    )


@require_POST
def delete_transcription(request, pk):
    transcription = get_object_or_404(Transcription, pk=pk)
    transcription.audio_file.delete(save=False)
    transcription.delete()
    return redirect("transcription:list_transcriptions")


@require_POST
def delete_transcriptions_bulk(request):
    ids = request.POST.getlist("selected_ids")
    if ids:
        for transcription in Transcription.objects.filter(id__in=ids):
            transcription.audio_file.delete(save=False)
            transcription.delete()
    return redirect("transcription:list_transcriptions")


def transcription_detail(request, pk):
    transcription = get_object_or_404(Transcription, pk=pk)
    audio_exists = bool(transcription.audio_file and os.path.exists(transcription.audio_file.path))

    if request.method == "POST":
        segments = transcription.structured_segments or []
        for i, seg in enumerate(segments):
            seg["text"] = request.POST.get(f"text_{i}", seg.get("text"))
        transcription.structured_segments = segments
        transcription.save(update_fields=["structured_segments"])
        return redirect("transcription:transcription_detail", pk=pk)

    return render(
        request,
        "transcription/detail.html",
        {
            "transcription": transcription,
            "audio_exists": audio_exists,
        },
    )


def transcription_audio(request, pk):
    transcription = get_object_or_404(Transcription, pk=pk)
    if not transcription.audio_file or not os.path.exists(transcription.audio_file.path):
        return HttpResponse(status=404)

    file_path = transcription.audio_file.path
    file_size = os.path.getsize(file_path)
    range_header = request.headers.get("Range", "").strip()

    def file_iter(start, length, chunk_size=8192):
        with open(file_path, "rb") as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                read_size = min(chunk_size, remaining)
                data = f.read(read_size)
                if not data:
                    break
                remaining -= len(data)
                yield data

    content_type, _ = mimetypes.guess_type(file_path)
    if content_type is None:
        content_type = "application/octet-stream"

    if range_header.startswith("bytes="):
        try:
            range_value = range_header.replace("bytes=", "")
            start_str, end_str = range_value.split("-", 1)
            start = int(start_str) if start_str else 0
            end = int(end_str) if end_str else file_size - 1
        except Exception:
            return HttpResponse(status=416)

        if start >= file_size:
            return HttpResponse(status=416)

        end = min(end, file_size - 1)
        length = end - start + 1
        response = StreamingHttpResponse(
            file_iter(start, length),
            status=206,
            content_type=content_type,
        )
        response["Content-Range"] = f"bytes {start}-{end}/{file_size}"
        response["Accept-Ranges"] = "bytes"
        response["Content-Length"] = str(length)
        response["Cache-Control"] = "private, max-age=3600"
        return response

    response = StreamingHttpResponse(
        file_iter(0, file_size),
        content_type=content_type,
    )
    response["Accept-Ranges"] = "bytes"
    response["Content-Length"] = str(file_size)
    response["Cache-Control"] = "private, max-age=3600"
    return response


@csrf_exempt
def save_segment(request, pk):
    """
    AJAX endpoint to save a single segment edit in real time.
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=400)

    transcription = get_object_or_404(Transcription, pk=pk)

    try:
        data = json.loads(request.body)
        try:
            index = int(data["index"])
        except (TypeError, ValueError):
            return JsonResponse({"error": "Invalid index"}, status=400)
        field = data["field"]  # 'original' or 'english'
        value = data["value"]

        segments = transcription.structured_segments or []
        if 0 <= index < len(segments) and field in ("original", "english"):
            segments[index][field] = value
            transcription.structured_segments = segments
            transcription.save(update_fields=["structured_segments"])
            return JsonResponse({"ok": True})
        else:
            return JsonResponse({"error": "Invalid index/field"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


import os
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from .models import Transcription
from .exports.manager import ExportManager

def export_transcript(request, transcript_id):
    """
    Export a transcription in one of the supported formats:
    TXT, PDF, DOCX, SRT.

    The exported filename is derived from the uploaded audio file
    to make it meaningful for the user.

    Query parameters:
        - format: 'txt', 'pdf', 'docx', 'srt'. Default: 'txt'
        - timestamps: '1' to include timestamps
        - speakers: '1' to include speaker info
    """
    # Get requested format (default to txt)
    fmt = request.GET.get("format", "txt").lower()

    # Determine export options
    options = {
        "include_timestamps": request.GET.get("timestamps") == "1",
        "include_speakers": request.GET.get("speakers") == "1",
    }

    # Fetch the transcription object
    transcription = get_object_or_404(Transcription, id=transcript_id)

    # Get appropriate exporter from ExportManager
    exporter = ExportManager.get_exporter(fmt)

    # Generate file content (bytes)
    file_bytes = exporter.export(transcription.structured_segments, options)

    # Determine a meaningful filename
    if transcription.audio_file:
        # Take the original audio filename without extension
        base_name = os.path.splitext(os.path.basename(transcription.audio_file.name))[0]
    else:
        # Fallback if no audio file
        base_name = f"transcript_{transcription.id}"

    # Sanitize filename (replace unsafe chars with underscore)
    safe_name = "".join(c if c.isalnum() or c in ('-', '_') else "_" for c in base_name)

    # Prepare HTTP response for file download
    response = HttpResponse(file_bytes, content_type="application/octet-stream")
    response["Content-Disposition"] = f'attachment; filename="{safe_name}.{fmt}"'

    return response



@require_POST
def cancel_transcription(request, pk):
    transcription = get_object_or_404(Transcription, pk=pk)
    transcription.status = "CANCELLED"
    transcription.save(update_fields=["status"])
    cancel_transcription_task.delay(pk)
    return JsonResponse({"ok": True})
