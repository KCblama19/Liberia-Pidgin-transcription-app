from django import template
import os

register = template.Library()

@register.filter
def time_format(value):
    """Convert seconds to MM:SS format"""
    if value is None:
        return ""
    minutes = int(value // 60)
    seconds = int(value % 60)
    return f"{minutes:02d}:{seconds:02d}"


@register.filter
def basename(value):
    """Return the base filename without any path."""
    if not value:
        return ""
    return os.path.basename(str(value))
