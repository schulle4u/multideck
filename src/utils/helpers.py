"""
Helper functions and utilities
"""

import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional

from utils.logger import get_logger

def check_ffmpeg() -> bool:
    """Check if FFmpeg is available"""
    try:
        result = subprocess.run(
            ['ffmpeg', '-version'],
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False
    except OSError as exc:
        get_logger('helpers').warning('Could not start FFmpeg: %s', exc)
        return False


def format_time(seconds: float) -> str:
    """Format seconds as M:SS or H:MM:SS"""
    if seconds < 0:
        seconds = 0
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes}:{secs:02d}"


def parse_time(time_str: str) -> float:
    """
    Parse time string to seconds.

    Supports formats:
    - SS (seconds only)
    - M:SS or MM:SS (minutes:seconds)
    - H:MM:SS (hours:minutes:seconds)

    Returns:
        Seconds as float, or None if parsing failed
    """
    try:
        time_str = time_str.strip()

        # Handle negative times
        negative = time_str.startswith('-')
        if negative:
            time_str = time_str[1:]

        parts = time_str.split(':')

        if len(parts) == 1:
            # Just seconds
            seconds = float(parts[0])
        elif len(parts) == 2:
            # M:SS
            minutes = int(parts[0])
            seconds = float(parts[1])
            seconds = minutes * 60 + seconds
        elif len(parts) == 3:
            # H:MM:SS
            hours = int(parts[0])
            minutes = int(parts[1])
            secs = float(parts[2])
            seconds = hours * 3600 + minutes * 60 + secs
        else:
            return None

        return -seconds if negative else seconds

    except (ValueError, IndexError):
        return None


def generate_recording_filename(format_ext: str = 'wav', prefix: str = 'recording') -> str:
    """
    Generate filename for recording.

    Args:
        format_ext: File extension (without dot)
        prefix: Filename prefix

    Returns:
        Generated filename
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f"{prefix}_{timestamp}.{format_ext}"


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename by removing invalid characters.

    Args:
        filename: Original filename

    Returns:
        Sanitized filename
    """
    # Invalid characters for Windows filenames
    invalid_chars = '<>:"/\\|?*'

    for char in invalid_chars:
        filename = filename.replace(char, '_')

    return filename


