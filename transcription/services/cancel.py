from threading import Event

_CANCEL_EVENTS = {}


def get_cancel_event(transcription_id: int) -> Event:
    if transcription_id not in _CANCEL_EVENTS:
        _CANCEL_EVENTS[transcription_id] = Event()
    return _CANCEL_EVENTS[transcription_id]


def cancel_transcription(transcription_id: int):
    get_cancel_event(transcription_id).set()
