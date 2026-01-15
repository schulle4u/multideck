"""
Audio Engine - Core audio playback functionality using sounddevice

Uses FFmpeg subprocess for MP3 support (no compilation required, works with Python 3.13+)
"""

import numpy as np
import sounddevice as sd
import soundfile as sf
import subprocess
import threading
from pathlib import Path
from typing import Optional, List


# Check if FFmpeg is available
def _check_ffmpeg():
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


class AudioEngine:
    """
    Core audio engine for MultiDeck Audio Player.
    Handles audio file loading and playback using sounddevice.
    """

    def __init__(self, buffer_size: int = 2048, sample_rate: int = 44100, device: Optional[str] = None):
        """
        Initialize audio engine.

        Args:
            buffer_size: Audio buffer size in samples
            sample_rate: Target sample rate in Hz
            device: Audio output device (None for default)
        """
        self.buffer_size = buffer_size
        self.sample_rate = sample_rate

        # Convert device to appropriate type for sounddevice
        if device is None or device == 'default':
            self.device = None
        elif isinstance(device, str) and device.isdigit():
            # Numeric string - convert to integer index
            self.device = int(device)
        else:
            self.device = device

        self._stream: Optional[sd.OutputStream] = None
        self._lock = threading.Lock()
        self._running = False

    def get_available_devices(self) -> List[dict]:
        """
        Get list of available audio output devices.

        Returns:
            List of device dictionaries
        """
        try:
            devices = sd.query_devices()
            output_devices = []

            for idx, device in enumerate(devices):
                if device['max_output_channels'] > 0:
                    output_devices.append({
                        'index': idx,
                        'name': device['name'],
                        'channels': device['max_output_channels'],
                        'sample_rate': device['default_samplerate'],
                    })

            return output_devices
        except Exception as e:
            print(f"Error querying audio devices: {e}")
            return []

    def get_default_device(self) -> Optional[dict]:
        """
        Get default audio output device.

        Returns:
            Default device dictionary or None
        """
        try:
            device = sd.query_devices(kind='output')
            return {
                'index': sd.default.device[1],
                'name': device['name'],
                'channels': device['max_output_channels'],
                'sample_rate': device['default_samplerate'],
            }
        except Exception as e:
            print(f"Error getting default device: {e}")
            return None

    def load_audio_file(self, file_path: str) -> Optional[tuple]:
        """
        Load audio file and return audio data and metadata.

        Args:
            file_path: Path to audio file

        Returns:
            Tuple of (audio_data, sample_rate, channels) or None on error
        """
        try:
            path = Path(file_path)

            if not path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")

            # Try loading with soundfile first (WAV, FLAC, OGG)
            try:
                data, samplerate = sf.read(file_path, dtype='float32')

                # Ensure data is 2D (samples, channels)
                if data.ndim == 1:
                    data = data.reshape(-1, 1)

                channels = data.shape[1]

                # Convert to stereo if mono
                if channels == 1:
                    data = np.column_stack((data, data))
                    channels = 2

                # Resample if necessary
                if samplerate != self.sample_rate:
                    data = self._resample(data, samplerate, self.sample_rate)
                    samplerate = self.sample_rate

                return data, samplerate, channels

            except Exception as sf_error:
                # Try loading with FFmpeg for MP3 support
                if FFMPEG_AVAILABLE and path.suffix.lower() in ['.mp3', '.m4a', '.aac', '.wma']:
                    return self._load_with_ffmpeg(file_path)
                else:
                    raise sf_error

        except Exception as e:
            print(f"Error loading audio file {file_path}: {e}")
            return None

    def _load_with_ffmpeg(self, file_path: str) -> Optional[tuple]:
        """
        Load audio file using FFmpeg subprocess (for MP3 and other formats).

        Args:
            file_path: Path to audio file

        Returns:
            Tuple of (audio_data, sample_rate, channels) or None
        """
        try:
            # FFmpeg command to decode file to raw PCM
            cmd = [
                'ffmpeg',
                '-i', file_path,
                '-f', 's16le',           # 16-bit signed little-endian
                '-acodec', 'pcm_s16le',
                '-ac', '2',              # Stereo
                '-ar', str(self.sample_rate),
                '-loglevel', 'error',
                '-'                      # Output to stdout
            ]

            # Create process with hidden window on Windows
            creationflags = 0
            if hasattr(subprocess, 'CREATE_NO_WINDOW'):
                creationflags = subprocess.CREATE_NO_WINDOW

            result = subprocess.run(
                cmd,
                capture_output=True,
                creationflags=creationflags
            )

            if result.returncode != 0:
                error_msg = result.stderr.decode('utf-8', errors='ignore')
                raise Exception(f"FFmpeg error: {error_msg}")

            # Convert bytes to numpy array
            samples = np.frombuffer(result.stdout, dtype=np.int16).astype(np.float32)

            # Normalize to -1.0 to 1.0
            samples = samples / 32768.0

            # Reshape to (samples, channels)
            samples = samples.reshape(-1, 2)

            return samples, self.sample_rate, 2

        except Exception as e:
            print(f"Error loading with FFmpeg: {e}")
            return None

    def _resample(self, data: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
        """
        Simple resampling (linear interpolation).
        For production, consider using librosa or scipy for better quality.

        Args:
            data: Audio data
            orig_sr: Original sample rate
            target_sr: Target sample rate

        Returns:
            Resampled audio data
        """
        if orig_sr == target_sr:
            return data

        # Calculate new length
        ratio = target_sr / orig_sr
        new_length = int(len(data) * ratio)

        # Linear interpolation for each channel
        resampled = np.zeros((new_length, data.shape[1]), dtype=np.float32)

        for ch in range(data.shape[1]):
            old_indices = np.arange(len(data))
            new_indices = np.linspace(0, len(data) - 1, new_length)
            resampled[:, ch] = np.interp(new_indices, old_indices, data[:, ch])

        return resampled

    def apply_volume_and_balance(self, audio_data: np.ndarray,
                                 left_volume: float, right_volume: float) -> np.ndarray:
        """
        Apply volume and balance to stereo audio data.

        Args:
            audio_data: Stereo audio data (samples, 2)
            left_volume: Left channel volume (0.0 to 1.0)
            right_volume: Right channel volume (0.0 to 1.0)

        Returns:
            Modified audio data
        """
        if audio_data.shape[1] != 2:
            return audio_data

        output = audio_data.copy()
        output[:, 0] *= left_volume  # Left channel
        output[:, 1] *= right_volume  # Right channel

        return output

    def mix_audio(self, audio_streams: List[np.ndarray]) -> np.ndarray:
        """
        Mix multiple audio streams together.

        Args:
            audio_streams: List of audio data arrays (same shape)

        Returns:
            Mixed audio data
        """
        if not audio_streams:
            return np.zeros((self.buffer_size, 2), dtype=np.float32)

        # Sum all streams
        mixed = np.sum(audio_streams, axis=0)

        # Soft clipping to prevent distortion
        mixed = np.tanh(mixed)

        return mixed.astype(np.float32)

    def create_silence(self, num_samples: int, channels: int = 2) -> np.ndarray:
        """
        Create silence buffer.

        Args:
            num_samples: Number of samples
            channels: Number of channels

        Returns:
            Silent audio data
        """
        return np.zeros((num_samples, channels), dtype=np.float32)

    def start_stream(self, callback):
        """
        Start audio output stream.

        Args:
            callback: Audio callback function
        """
        try:
            with self._lock:
                if self._stream is not None:
                    self.stop_stream()

                self._stream = sd.OutputStream(
                    samplerate=self.sample_rate,
                    channels=2,
                    blocksize=self.buffer_size,
                    device=self.device,
                    callback=callback,
                    dtype='float32'
                )
                self._stream.start()
                self._running = True

        except Exception as e:
            print(f"Error starting audio stream: {e}")
            self._running = False

    def stop_stream(self):
        """Stop audio output stream"""
        try:
            with self._lock:
                if self._stream is not None:
                    self._stream.stop()
                    self._stream.close()
                    self._stream = None
                self._running = False

        except Exception as e:
            print(f"Error stopping audio stream: {e}")

    def is_running(self) -> bool:
        """Check if audio stream is running"""
        return self._running

    @staticmethod
    def get_audio_duration(file_path: str) -> Optional[float]:
        """
        Get duration of audio file in seconds.

        Args:
            file_path: Path to audio file

        Returns:
            Duration in seconds or None on error
        """
        try:
            info = sf.info(file_path)
            return info.duration
        except Exception:
            # Try with FFmpeg for MP3 and other formats
            if FFMPEG_AVAILABLE:
                try:
                    cmd = [
                        'ffprobe',
                        '-v', 'error',
                        '-show_entries', 'format=duration',
                        '-of', 'default=noprint_wrappers=1:nokey=1',
                        file_path
                    ]

                    creationflags = 0
                    if hasattr(subprocess, 'CREATE_NO_WINDOW'):
                        creationflags = subprocess.CREATE_NO_WINDOW

                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        creationflags=creationflags
                    )

                    if result.returncode == 0:
                        duration_str = result.stdout.decode('utf-8').strip()
                        return float(duration_str)
                except Exception:
                    pass
        return None

    def __del__(self):
        """Cleanup on deletion"""
        self.stop_stream()
