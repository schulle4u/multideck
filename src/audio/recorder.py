"""
Recorder - Master output recording functionality
Supports WAV, MP3, OGG, and FLAC formats via FFmpeg
"""

import wave
import subprocess
import threading
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable

from utils.helpers import generate_recording_filename


def _check_ffmpeg() -> bool:
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


FFMPEG_AVAILABLE = _check_ffmpeg()


class Recorder:
    """
    Records master audio output to audio files.
    Supports WAV (native), MP3, OGG, and FLAC (via FFmpeg).
    """

    # Supported formats and their FFmpeg codec settings
    FORMATS = {
        'wav': {'extension': '.wav', 'codec': None, 'native': True},
        'mp3': {'extension': '.mp3', 'codec': 'libmp3lame', 'native': False},
        'ogg': {'extension': '.ogg', 'codec': 'libvorbis', 'native': False},
        'flac': {'extension': '.flac', 'codec': 'flac', 'native': False},
    }

    def __init__(self, sample_rate: int = 44100, channels: int = 2,
                 bit_depth: int = 16, format: str = 'wav', bitrate: int = 192):
        """
        Initialize recorder.

        Args:
            sample_rate: Sample rate in Hz
            channels: Number of channels (1=mono, 2=stereo)
            bit_depth: Bit depth (16, 24, or 32)
            format: Output format ('wav', 'mp3', 'ogg', 'flac')
            bitrate: Bitrate in kbps for compressed formats (64-320)
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.bit_depth = bit_depth
        self.format = format if format in self.FORMATS else 'wav'
        self.bitrate = max(64, min(320, bitrate))  # Clamp to valid range

        # Recording state
        self.is_recording = False
        self.output_file: Optional[str] = None
        self.wave_file: Optional[wave.Wave_write] = None
        self._ffmpeg_process: Optional[subprocess.Popen] = None

        # Statistics
        self.recording_start_time: Optional[datetime] = None
        self.frames_recorded = 0

        # Threading
        self._lock = threading.Lock()

        # Callbacks
        self.on_recording_started: Optional[Callable] = None
        self.on_recording_stopped: Optional[Callable] = None
        self.on_error: Optional[Callable] = None

    def set_format(self, format: str):
        """
        Set recording format.

        Args:
            format: Output format ('wav', 'mp3', 'ogg', 'flac')
        """
        if not self.is_recording:
            self.format = format if format in self.FORMATS else 'wav'

    def set_bitrate(self, bitrate: int):
        """
        Set bitrate for compressed formats.

        Args:
            bitrate: Bitrate in kbps (64-320)
        """
        if not self.is_recording:
            self.bitrate = max(64, min(320, bitrate))

    def get_available_formats(self) -> list:
        """
        Get list of available recording formats.

        Returns:
            List of available format names
        """
        formats = ['wav']  # WAV is always available
        if FFMPEG_AVAILABLE:
            formats.extend(['mp3', 'ogg', 'flac'])
        return formats

    def start_recording(self, output_file: Optional[str] = None,
                       output_directory: Optional[str] = None) -> bool:
        """
        Start recording.

        Args:
            output_file: Output file path (optional, will generate if not provided)
            output_directory: Output directory (optional, uses current dir if not provided)

        Returns:
            True if recording started successfully
        """
        if self.is_recording:
            return False

        # Check if format requires FFmpeg
        format_info = self.FORMATS.get(self.format, self.FORMATS['wav'])
        if not format_info['native'] and not FFMPEG_AVAILABLE:
            print(f"FFmpeg not available, falling back to WAV format")
            self.format = 'wav'
            format_info = self.FORMATS['wav']

        try:
            with self._lock:
                # Generate filename if not provided
                extension = format_info['extension'].lstrip('.')
                if not output_file:
                    filename = generate_recording_filename(extension, 'recording')
                    if output_directory:
                        output_file = str(Path(output_directory) / filename)
                    else:
                        output_file = filename
                else:
                    # Ensure correct extension
                    output_path = Path(output_file)
                    if output_path.suffix.lower() != format_info['extension']:
                        output_file = str(output_path.with_suffix(format_info['extension']))

                # Ensure parent directory exists
                output_path = Path(output_file)
                output_path.parent.mkdir(parents=True, exist_ok=True)

                self.output_file = str(output_file)

                if format_info['native']:
                    # Use native WAV writing
                    self._start_wav_recording()
                else:
                    # Use FFmpeg for encoding
                    self._start_ffmpeg_recording(format_info)

                self.is_recording = True
                self.recording_start_time = datetime.now()
                self.frames_recorded = 0

                if self.on_recording_started:
                    self.on_recording_started(self.output_file)

                return True

        except Exception as e:
            print(f"Error starting recording: {e}")
            if self.on_error:
                self.on_error(f"Failed to start recording: {e}")
            return False

    def _start_wav_recording(self):
        """Start native WAV recording"""
        self.wave_file = wave.open(self.output_file, 'wb')
        self.wave_file.setnchannels(self.channels)
        self.wave_file.setsampwidth(self.bit_depth // 8)
        self.wave_file.setframerate(self.sample_rate)

    def _start_ffmpeg_recording(self, format_info: dict):
        """Start FFmpeg-based recording"""
        codec = format_info['codec']

        # Build FFmpeg command
        cmd = [
            'ffmpeg',
            '-y',  # Overwrite output
            '-f', 's16le',  # Input format: signed 16-bit little-endian
            '-ar', str(self.sample_rate),  # Sample rate
            '-ac', str(self.channels),  # Channels
            '-i', 'pipe:0',  # Read from stdin
            '-acodec', codec,
        ]

        # Add format-specific options with bitrate
        if codec == 'libmp3lame':
            cmd.extend(['-b:a', f'{self.bitrate}k'])
        elif codec == 'libvorbis':
            cmd.extend(['-b:a', f'{self.bitrate}k'])
        elif codec == 'flac':
            cmd.extend(['-compression_level', '5'])  # FLAC is lossless, no bitrate

        cmd.append(self.output_file)

        # Start FFmpeg process
        creationflags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
        self._ffmpeg_process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags
        )

    def stop_recording(self) -> bool:
        """
        Stop recording.

        Returns:
            True if recording stopped successfully
        """
        if not self.is_recording:
            return False

        try:
            with self._lock:
                if self.wave_file:
                    self.wave_file.close()
                    self.wave_file = None

                if self._ffmpeg_process:
                    try:
                        self._ffmpeg_process.stdin.close()
                        self._ffmpeg_process.wait(timeout=10)
                    except Exception as e:
                        print(f"Error closing FFmpeg: {e}")
                        self._ffmpeg_process.kill()
                    self._ffmpeg_process = None

                self.is_recording = False
                output_file = self.output_file
                self.output_file = None

                if self.on_recording_stopped:
                    self.on_recording_stopped(output_file, self.frames_recorded)

                return True

        except Exception as e:
            print(f"Error stopping recording: {e}")
            if self.on_error:
                self.on_error(f"Failed to stop recording: {e}")
            return False

    def write_frames(self, audio_data: np.ndarray):
        """
        Write audio frames to recording.

        Args:
            audio_data: Audio data (samples, channels) as numpy array
        """
        if not self.is_recording:
            return

        try:
            with self._lock:
                # Convert float32 to int16 for both WAV and FFmpeg
                audio_int = (audio_data * 32767).astype(np.int16)
                audio_int = np.clip(audio_int, -32768, 32767)
                audio_bytes = audio_int.tobytes()

                if self.wave_file:
                    # Native WAV recording
                    if self.bit_depth == 16:
                        self.wave_file.writeframes(audio_bytes)
                    elif self.bit_depth == 24:
                        audio_int32 = (audio_data * 8388607).astype(np.int32)
                        audio_int32 = np.clip(audio_int32, -8388608, 8388607)
                        self.wave_file.writeframes(audio_int32.tobytes())
                    elif self.bit_depth == 32:
                        audio_int32 = (audio_data * 2147483647).astype(np.int32)
                        audio_int32 = np.clip(audio_int32, -2147483648, 2147483647)
                        self.wave_file.writeframes(audio_int32.tobytes())

                elif self._ffmpeg_process and self._ffmpeg_process.stdin:
                    # FFmpeg recording - always use 16-bit for FFmpeg input
                    try:
                        self._ffmpeg_process.stdin.write(audio_bytes)
                    except BrokenPipeError:
                        print("FFmpeg pipe broken, stopping recording")
                        self.is_recording = False

                self.frames_recorded += len(audio_data)

        except Exception as e:
            print(f"Error writing frames: {e}")
            if self.on_error:
                self.on_error(f"Error during recording: {e}")

    def get_recording_duration(self) -> float:
        """
        Get current recording duration in seconds.

        Returns:
            Duration in seconds
        """
        if not self.is_recording or not self.recording_start_time:
            return 0.0

        elapsed = datetime.now() - self.recording_start_time
        return elapsed.total_seconds()

    def get_recording_info(self) -> dict:
        """
        Get recording information.

        Returns:
            Dictionary with recording info
        """
        return {
            'is_recording': self.is_recording,
            'output_file': self.output_file,
            'format': self.format,
            'sample_rate': self.sample_rate,
            'channels': self.channels,
            'bit_depth': self.bit_depth,
            'bitrate': self.bitrate,
            'duration': self.get_recording_duration(),
            'frames_recorded': self.frames_recorded,
        }

    def format_duration(self) -> str:
        """
        Format recording duration as HH:MM:SS.

        Returns:
            Formatted duration string
        """
        duration = self.get_recording_duration()
        hours = int(duration // 3600)
        minutes = int((duration % 3600) // 60)
        seconds = int(duration % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def __del__(self):
        """Cleanup on deletion"""
        if self.is_recording:
            self.stop_recording()
