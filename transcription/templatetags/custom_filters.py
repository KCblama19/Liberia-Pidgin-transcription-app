from django import template

register = template.Library()

@register.filter
def time_format(value):
    """Convert seconds to MM:SS format"""
    if value is None:
        return ""
    minutes = int(value // 60)
    seconds = int(value % 60)
    return f"{minutes:02d}:{seconds:02d}"
