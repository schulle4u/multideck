"""
SoundCard Input Handler - Captures audio from a sound card input device (microphone, line-in)
for MultiDeck Audio Player.

Implements the same interface as StreamHandler so it can be used transparently
in the mixer's stream code path.
"""

import collections
import threading
from typing import Optional

import numpy as np

from utils.logger import get_logger

logger = get_logger('soundcard_input_handler')


class SoundCardInputHandler:
    """
    Captures audio from a sound card input device (microphone, line-in).

    Implements the same get_audio_data() interface as StreamHandler so the
    mixer can use it via the existing is_stream code path without changes.
    """

    def __init__(self, device_id: int, device_name: str,
                 target_sample_rate: int = 48000, buffer_size: int = 2048):
        """
        Initialize the handler.

        Args:
            device_id: sounddevice device index
            device_name: Human-readable device name (for display and project saving)
            target_sample_rate: Output sample rate to match the audio engine
            buffer_size: Block size used by the audio engine's output stream.
                         The input stream uses the same block size so both
                         callbacks tick at the same rate, avoiding timing drift.
        """
        self.device_id = device_id
        self.device_name = device_name
        self.target_sample_rate = target_sample_rate
        self.buffer_size = buffer_size

        # Ring buffer: list of (num_samples, 2) float32 arrays
        self._buffer: collections.deque = collections.deque()
        self._buffer_lock = threading.Lock()
        self._buffered_samples = 0
        # Keep 4 output frames buffered at most to bound latency
        self._max_buffer_samples = buffer_size * 4
        # Pre-fill exactly one output frame before reading.
        # This ensures the first get_audio_data() call always finds data.
        self._min_prefill_samples = buffer_size
        self._prefill_done = False

        self._stream = None
        self._input_channels = 2  # Will be detected on start()
        self.is_running = False
        self.is_connected = False

        # Callbacks (matching StreamHandler interface)
        self.on_error: Optional[callable] = None

    def start(self) -> bool:
        """
        Open the input stream and start capturing audio.

        Returns:
            True if successfully started, False otherwise
        """
        try:
            import sounddevice as sd

            # Query device capabilities
            device_info = sd.query_devices(self.device_id)
            max_input_channels = int(device_info.get('max_input_channels', 0))
            if max_input_channels < 1:
                logger.error(f"Device {self.device_id} has no input channels")
                return False

            self._input_channels = min(max_input_channels, 2)

            # Request target_sample_rate directly so PortAudio handles any necessary
            # resampling internally.  Doing it ourselves per-chunk causes phase
            # discontinuities at block boundaries (audible as distortion / "robot" artefacts).
            self._stream = sd.InputStream(
                device=self.device_id,
                channels=self._input_channels,
                samplerate=self.target_sample_rate,
                dtype='float32',
                callback=self._input_callback,
                blocksize=self.buffer_size,  # Match output stream block size
            )
            self._stream.start()
            self.is_running = True
            self.is_connected = True
            logger.info(f"Started soundcard input: {self.device_name} "
                        f"({self._input_channels}ch @ {self.target_sample_rate} Hz)")
            return True

        except Exception as e:
            logger.error(f"Failed to start soundcard input '{self.device_name}': {e}")
            self._stream = None
            if self.on_error:
                try:
                    self.on_error(str(e))
                except Exception:
                    pass
            return False

    def stop(self):
        """Stop capturing and close the input stream."""
        self.is_running = False
        self.is_connected = False
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as e:
                logger.warning(f"Error closing soundcard input stream: {e}")
            finally:
                self._stream = None
        with self._buffer_lock:
            self._buffer.clear()
            self._buffered_samples = 0
            self._prefill_done = False
        logger.info(f"Stopped soundcard input: {self.device_name}")

    def _input_callback(self, indata: np.ndarray, frames: int, time, status):
        """
        Called by sounddevice in its audio thread with captured samples.

        Args:
            indata: (frames, channels) float32 array of captured audio
            frames: Number of frames in this block
            time: sounddevice time info (unused)
            status: sounddevice status flags
        """
        if status:
            logger.debug(f"Soundcard input status: {status}")

        # Convert to stereo float32; PortAudio already delivered at target_sample_rate
        audio = indata.astype(np.float32, copy=False)
        if audio.ndim == 1 or audio.shape[1] == 1:
            # Mono → duplicate to stereo
            mono = audio.reshape(-1, 1)
            audio = np.hstack([mono, mono])

        with self._buffer_lock:
            self._buffer.append(audio)
            self._buffered_samples += len(audio)

            # Trim oldest chunks if buffer exceeds max size
            while self._buffered_samples > self._max_buffer_samples and self._buffer:
                removed = self._buffer.popleft()
                self._buffered_samples -= len(removed)

    def get_audio_data(self, num_samples: int) -> np.ndarray:
        """
        Retrieve num_samples of captured audio from the buffer.

        Returns silence if the buffer does not yet have enough data.
        This matches the StreamHandler interface expected by the mixer.

        Args:
            num_samples: Number of samples to return

        Returns:
            (num_samples, 2) float32 numpy array
        """
        result = np.zeros((num_samples, 2), dtype=np.float32)
        if not self.is_running:
            return result

        with self._buffer_lock:
            # Hold back audio until the buffer has a comfortable pre-fill.
            # Without this, the output callback races the input callback and
            # receives silence on every other read, causing audible distortion.
            if not self._prefill_done:
                if self._buffered_samples < self._min_prefill_samples:
                    return result
                self._prefill_done = True

            collected = 0
            while collected < num_samples and self._buffer:
                chunk = self._buffer[0]
                available = len(chunk)
                needed = num_samples - collected

                if available <= needed:
                    result[collected:collected + available] = chunk
                    collected += available
                    self._buffer.popleft()
                    self._buffered_samples -= available
                else:
                    # Take the front part of this chunk and put the rest back
                    result[collected:num_samples] = chunk[:needed]
                    self._buffer[0] = chunk[needed:]
                    self._buffered_samples -= needed
                    collected = num_samples

        return result

    def get_status(self) -> dict:
        """Return status information for diagnostics."""
        with self._buffer_lock:
            buffer_seconds = (self._buffered_samples / self.target_sample_rate
                              if self.target_sample_rate > 0 else 0.0)
        return {
            'device_id': self.device_id,
            'device_name': self.device_name,
            'is_running': self.is_running,
            'is_connected': self.is_connected,
            'buffer_seconds': buffer_seconds,
            'sample_rate': self.target_sample_rate,
        }

    @staticmethod
    def get_available_input_devices() -> list:
        """
        Query sounddevice for available audio input devices.

        Returns:
            List of dicts with keys: 'id', 'name', 'channels', 'hostapi_name'
            Empty list if sounddevice is unavailable.
        """
        try:
            import sounddevice as sd
            hostapis = sd.query_hostapis()
            devices = sd.query_devices()
            result = []
            for i, dev in enumerate(devices):
                if int(dev.get('max_input_channels', 0)) > 0:
                    hostapi_idx = dev.get('hostapi', 0)
                    try:
                        hostapi_name = hostapis[hostapi_idx]['name']
                    except (IndexError, KeyError, TypeError):
                        hostapi_name = ''
                    result.append({
                        'id': i,
                        'name': dev['name'],
                        'channels': int(dev['max_input_channels']),
                        'hostapi_name': hostapi_name,
                    })
            return result
        except Exception as e:
            logger.error(f"Failed to query input devices: {e}")
            return []
