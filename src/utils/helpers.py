"""
Helper functions and utilities
"""

import os
from pathlib import Path
from datetime import datetime
from typing import Optional


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


def format_time_old(seconds: float) -> str:
    """
    Format time in seconds to HH:MM:SS. (TODO: needs review, probably to be removed)

    Args:
        seconds: Time in seconds

    Returns:
        Formatted time string
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}"


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


def format_file_size(bytes_size: int) -> str:
    """
    Format file size in bytes to human-readable format.

    Args:
        bytes_size: Size in bytes

    Returns:
        Formatted size string
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} PB"


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


def validate_url(url: str) -> bool:
    """
    Validate if string is a valid URL.

    Args:
        url: URL string to validate

    Returns:
        True if valid URL
    """
    return url.startswith(('http://', 'https://'))


def get_file_extension(filepath: str) -> str:
    """
    Get file extension (lowercase, without dot).

    Args:
        filepath: File path

    Returns:
        File extension
    """
    return Path(filepath).suffix.lower().lstrip('.')


def ensure_directory(directory: str) -> bool:
    """
    Ensure directory exists, create if not.

    Args:
        directory: Directory path

    Returns:
        True if directory exists or was created
    """
    try:
        Path(directory).mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        print(f"Error creating directory: {e}")
        return False


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


def truncate_string(text: str, max_length: int, suffix: str = '...') -> str:
    """
    Truncate string to maximum length.

    Args:
        text: Original text
        max_length: Maximum length
        suffix: Suffix to add when truncated

    Returns:
        Truncated string
    """
    if len(text) <= max_length:
        return text

    return text[:max_length - len(suffix)] + suffix


def parse_volume_percent(value: str) -> Optional[float]:
    """
    Parse volume percentage string to float (0.0-1.0).

    Args:
        value: Volume string (e.g., "75%", "0.75", "75")

    Returns:
        Volume as float or None if invalid
    """
    try:
        # Remove % symbol if present
        value = value.strip().rstrip('%')
        volume = float(value)

        # Convert from percentage if > 1
        if volume > 1.0:
            volume /= 100.0

        # Clamp to valid range
        return max(0.0, min(1.0, volume))
    except Exception:
        return None


def format_volume_percent(volume: float) -> str:
    """
    Format volume float to percentage string.

    Args:
        volume: Volume (0.0-1.0)

    Returns:
        Formatted percentage string
    """
    return f"{int(volume * 100)}%"
