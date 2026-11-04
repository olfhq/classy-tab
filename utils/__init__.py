from .text import parse_response_text


def seconds_to_hms(seconds):
    """Convert seconds to hours, minutes, and seconds."""
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d}"
