"""
Stream Handler - Internet streaming support with auto-reconnect

Uses FFmpeg subprocess for decoding (no compilation required, works with Python 3.13+)
"""

import threading
import time
import subprocess
import numpy as np
from typing import Optional, Callable


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


class StreamHandler:
    """
    Handles HTTP/HTTPS audio streaming with automatic reconnection.
    Uses FFmpeg subprocess to decode stream directly to PCM.
    Supports Icecast and Shoutcast streams.
    """

    def __init__(self, url: str, sample_rate: int = 44100):
        """
        Initialize stream handler.

        Args:
            url: Stream URL
            sample_rate: Target sample rate
        """
        self.url = url
        self.sample_rate = sample_rate

        # Stream state
        self.is_connected = False
        self.is_running = False

        # Reconnect settings
        self.auto_reconnect = True
        self.reconnect_wait = 5  # seconds
        self.max_reconnect_attempts = 5
        self.connection_timeout = 10

        # Buffer for decoded PCM samples
        self.decoded_buffer = []
        self.buffer_lock = threading.Lock()

        # Metadata
        self.stream_title = ""
        self.stream_genre = ""
        self.stream_bitrate = ""

        # FFmpeg process
        self._ffmpeg_process: Optional[subprocess.Popen] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Callbacks
        self.on_connected: Optional[Callable] = None
        self.on_disconnected: Optional[Callable] = None
        self.on_metadata_update: Optional[Callable] = None
        self.on_error: Optional[Callable] = None

    def start(self) -> bool:
        """
        Start streaming.

        Returns:
            True if started successfully
        """
        if not FFMPEG_AVAILABLE:
            if self.on_error:
                self.on_error("FFmpeg not found. Please install FFmpeg.")
            return False

        if self.is_running:
            return True

        self.is_running = True
        self._stop_event.clear()

        self._reader_thread = threading.Thread(target=self._stream_loop, daemon=True)
        self._reader_thread.start()

        return True

    def stop(self):
        """Stop streaming"""
        self.is_running = False
        self._stop_event.set()

        # Terminate FFmpeg process
        if self._ffmpeg_process:
            try:
                self._ffmpeg_process.terminate()
                self._ffmpeg_process.wait(timeout=2.0)
            except Exception:
                try:
                    self._ffmpeg_process.kill()
                except Exception:
                    pass
            self._ffmpeg_process = None

        if self._reader_thread:
            self._reader_thread.join(timeout=2.0)
            self._reader_thread = None

        self.is_connected = False

    def _stream_loop(self):
        """Main streaming loop with reconnect logic"""
        reconnect_attempts = 0

        while self.is_running and not self._stop_event.is_set():
            try:
                if not self.is_connected:
                    if not self._start_ffmpeg():
                        reconnect_attempts += 1

                        if reconnect_attempts >= self.max_reconnect_attempts:
                            if self.on_error:
                                self.on_error("Max reconnect attempts reached")
                            break

                        if self.auto_reconnect:
                            time.sleep(self.reconnect_wait)
                            continue
                        else:
                            break

                    reconnect_attempts = 0

                # Read PCM data from FFmpeg
                self._read_ffmpeg_output()

            except Exception as e:
                print(f"Stream error: {e}")
                self.is_connected = False

                if self._ffmpeg_process:
                    try:
                        self._ffmpeg_process.terminate()
                    except Exception:
                        pass
                    self._ffmpeg_process = None

                if self.on_disconnected:
                    self.on_disconnected()

                if self.auto_reconnect and not self._stop_event.is_set():
                    time.sleep(self.reconnect_wait)
                else:
                    break

        self.is_connected = False

    def _start_ffmpeg(self) -> bool:
        """
        Start FFmpeg process to decode stream.

        Returns:
            True if started successfully
        """
        try:
            # FFmpeg command to decode stream to raw PCM
            # -reconnect flags for auto-reconnection
            # Output: 16-bit signed little-endian PCM, stereo, target sample rate
            cmd = [
                'ffmpeg',
                '-reconnect', '1',
                '-reconnect_streamed', '1',
                '-reconnect_delay_max', '5',
                '-i', self.url,
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

            self._ffmpeg_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=creationflags
            )

            self.is_connected = True

            if self.on_connected:
                self.on_connected()

            return True

        except Exception as e:
            print(f"Failed to start FFmpeg: {e}")
            if self.on_error:
                self.on_error(f"Failed to start stream: {e}")
            return False

    def _read_ffmpeg_output(self):
        """Read PCM data from FFmpeg stdout"""
        if not self._ffmpeg_process or not self._ffmpeg_process.stdout:
            return

        # Read chunks of PCM data
        # 4096 samples * 2 channels * 2 bytes = 16384 bytes per chunk
        chunk_size = 16384

        try:
            while self.is_running and not self._stop_event.is_set():
                data = self._ffmpeg_process.stdout.read(chunk_size)

                if not data:
                    # Stream ended or error
                    self.is_connected = False
                    break

                # Convert bytes to numpy array
                # s16le = signed 16-bit little-endian
                samples = np.frombuffer(data, dtype=np.int16).astype(np.float32)

                # Normalize to -1.0 to 1.0
                samples = samples / 32768.0

                # Reshape to (samples, channels)
                samples = samples.reshape(-1, 2)

                # Add to buffer
                with self.buffer_lock:
                    self.decoded_buffer.append(samples)

                    # Limit buffer size (keep ~10 seconds of audio)
                    max_samples = self.sample_rate * 10
                    total_samples = sum(len(chunk) for chunk in self.decoded_buffer)
                    while total_samples > max_samples and len(self.decoded_buffer) > 1:
                        removed = self.decoded_buffer.pop(0)
                        total_samples -= len(removed)

        except Exception as e:
            if self.is_running:
                print(f"Error reading FFmpeg output: {e}")
                self.is_connected = False

    def get_audio_data(self, num_samples: int) -> Optional[np.ndarray]:
        """
        Get audio data from buffer.

        Args:
            num_samples: Number of samples to retrieve

        Returns:
            Audio data as numpy array (num_samples, 2) or None
        """
        if not FFMPEG_AVAILABLE:
            print("Warning: FFmpeg not available, stream playback disabled")
            return None

        try:
            with self.buffer_lock:
                if not self.decoded_buffer:
                    # No data available, return silence
                    return np.zeros((num_samples, 2), dtype=np.float32)

                # Collect samples from decoded buffer
                result_samples = []
                samples_collected = 0

                while samples_collected < num_samples and self.decoded_buffer:
                    chunk = self.decoded_buffer[0]
                    samples_needed = num_samples - samples_collected

                    if len(chunk) <= samples_needed:
                        result_samples.append(chunk)
                        samples_collected += len(chunk)
                        self.decoded_buffer.pop(0)
                    else:
                        result_samples.append(chunk[:samples_needed])
                        self.decoded_buffer[0] = chunk[samples_needed:]
                        samples_collected += samples_needed

                if result_samples:
                    result = np.vstack(result_samples)

                    # Pad with silence if needed
                    if len(result) < num_samples:
                        padding = np.zeros((num_samples - len(result), 2), dtype=np.float32)
                        result = np.vstack([result, padding])

                    return result[:num_samples]
                else:
                    return np.zeros((num_samples, 2), dtype=np.float32)

        except Exception as e:
            print(f"Error getting stream audio data: {e}")
            return np.zeros((num_samples, 2), dtype=np.float32)

    def has_data(self) -> bool:
        """Check if buffer has data"""
        with self.buffer_lock:
            return len(self.decoded_buffer) > 0

    def clear_buffer(self):
        """Clear audio buffer"""
        with self.buffer_lock:
            self.decoded_buffer.clear()

    def set_reconnect_settings(self, auto_reconnect: bool = True,
                               reconnect_wait: int = 5,
                               max_attempts: int = 5):
        """
        Configure reconnect behavior.

        Args:
            auto_reconnect: Enable automatic reconnection
            reconnect_wait: Wait time between reconnect attempts (seconds)
            max_attempts: Maximum number of reconnect attempts
        """
        self.auto_reconnect = auto_reconnect
        self.reconnect_wait = reconnect_wait
        self.max_reconnect_attempts = max_attempts

    def get_status(self) -> dict:
        """
        Get stream status.

        Returns:
            Status dictionary
        """
        with self.buffer_lock:
            buffer_samples = sum(len(chunk) for chunk in self.decoded_buffer)

        return {
            'url': self.url,
            'connected': self.is_connected,
            'running': self.is_running,
            'title': self.stream_title,
            'genre': self.stream_genre,
            'bitrate': self.stream_bitrate,
            'buffer_samples': buffer_samples,
            'buffer_seconds': buffer_samples / self.sample_rate if self.sample_rate > 0 else 0,
        }

    def __del__(self):
        """Cleanup on deletion"""
        self.stop()
