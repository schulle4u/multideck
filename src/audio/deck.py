"""
Audio Deck - Individual deck logic for MultiDeck Audio Player
"""

import threading
from pathlib import Path
from typing import Optional, Callable

from config.defaults import (
    DECK_STATE_EMPTY, DECK_STATE_LOADED, DECK_STATE_PLAYING,
    DECK_STATE_PAUSED, DECK_STATE_ERROR
)
from utils.logger import get_logger

# Module logger
logger = get_logger('deck')

# Import StreamHandler with lazy loading to avoid circular imports
_StreamHandler = None
def _get_stream_handler_class():
    global _StreamHandler
    if _StreamHandler is None:
        from audio.stream_handler import StreamHandler
        _StreamHandler = StreamHandler
    return _StreamHandler


class Deck:
    """
    Represents a single audio deck with playback controls.
    """

    def __init__(self, deck_id: int, sample_rate: int = 44100):
        """
        Initialize a deck.

        Args:
            deck_id: Deck number (1-10)
            sample_rate: Sample rate for audio playback
        """
        self.deck_id = deck_id
        self.name = f"Deck {deck_id}"
        self.state = DECK_STATE_EMPTY
        self._target_sample_rate = sample_rate  # Target sample rate for deck

        # Audio properties
        self.file_path: Optional[str] = None
        self.is_stream = False
        self.audio_data = None
        self.sample_rate = None  # Actual sample rate of loaded audio
        self.channels = None
        self.stream_handler = None  # For HTTP/HTTPS streaming

        # Playback controls
        self.volume = 1.0  # 0.0 to 1.0
        self.balance = 0.0  # -1.0 (left) to 1.0 (right)
        self.mute = False
        self.loop = False

        # Playback state
        self.position = 0  # Current position in samples
        self.is_playing = False
        self.is_paused = False

        # Level metering (written by audio thread, read by GUI)
        self.rms_level = 0.0      # Linear RMS 0.0-1.0
        self.rms_level_db = -60.0  # RMS in dB

        # Threading - use RLock to allow recursive locking (e.g., unload() calling stop())
        self._lock = threading.RLock()
        self._play_thread: Optional[threading.Thread] = None

        # Effect chain (assigned by Mixer)
        self.effects = None

        # Callbacks
        self.on_state_change: Optional[Callable] = None
        self.on_playback_end: Optional[Callable] = None

    def load_file(self, file_path: str) -> bool:
        """
        Load an audio file into the deck.

        Args:
            file_path: Path to audio file or URL

        Returns:
            True if loaded successfully, False otherwise
        """
        try:
            with self._lock:
                # Check if it's a URL (stream)
                if file_path.startswith(('http://', 'https://')):
                    # Stop any existing stream
                    if self.stream_handler:
                        self.stream_handler.stop()
                        self.stream_handler = None

                    # Create and start stream handler
                    StreamHandler = _get_stream_handler_class()
                    self.stream_handler = StreamHandler(file_path, self._target_sample_rate)

                    # Set up stream handler callbacks
                    def on_stream_error(error_msg):
                        logger.error(f"Stream error on Deck {self.deck_id}: {error_msg}")
                        self._set_state(DECK_STATE_ERROR)

                    self.stream_handler.on_error = on_stream_error

                    # Start streaming
                    if self.stream_handler.start():
                        self.is_stream = True
                        self.file_path = file_path
                        self.sample_rate = self._target_sample_rate
                        self.channels = 2  # Streams are converted to stereo
                        self._set_state(DECK_STATE_LOADED)
                        return True
                    else:
                        logger.error(f"Failed to start stream on Deck {self.deck_id}")
                        self.stream_handler = None
                        self._set_state(DECK_STATE_ERROR)
                        return False

                # Load local file
                path = Path(file_path)
                if not path.exists():
                    raise FileNotFoundError(f"File not found: {file_path}")

                self.is_stream = False
                self.file_path = file_path

                # Audio loading will be handled by AudioEngine
                # For now, just mark as loaded
                self._set_state(DECK_STATE_LOADED)
                self.position = 0
                return True

        except Exception as e:
            logger.error(f"Error loading file in Deck {self.deck_id}: {e}")
            self._set_state(DECK_STATE_ERROR)
            return False

    def unload(self):
        """Unload audio from deck"""
        with self._lock:
            self.stop()

            # Stop stream handler if active
            if self.stream_handler:
                self.stream_handler.stop()
                self.stream_handler = None

            self.file_path = None
            self.audio_data = None
            self.sample_rate = None
            self.channels = None
            self.position = 0
            self.is_stream = False
            self._set_state(DECK_STATE_EMPTY)

    def play(self) -> bool:
        """
        Start playback.

        Returns:
            True if playback started, False otherwise
        """
        if self.state == DECK_STATE_EMPTY:
            return False

        with self._lock:
            if self.is_playing:
                return True

            self.is_playing = True
            self.is_paused = False
            self._set_state(DECK_STATE_PLAYING)
            return True

    def pause(self):
        """Pause playback"""
        with self._lock:
            if self.is_playing:
                self.is_playing = False
                self.is_paused = True
                self._set_state(DECK_STATE_PAUSED)

    def stop(self):
        """Stop playback and reset position"""
        with self._lock:
            self.is_playing = False
            self.is_paused = False
            self.position = 0
            if self.state not in [DECK_STATE_EMPTY, DECK_STATE_ERROR]:
                self._set_state(DECK_STATE_LOADED)

    def toggle_play_pause(self):
        """Toggle between play and pause"""
        if self.is_playing:
            self.pause()
        else:
            self.play()

    def set_volume(self, volume: float):
        """
        Set deck volume.

        Args:
            volume: Volume level (0.0 to 1.0)
        """
        self.volume = max(0.0, min(1.0, volume))

    def set_balance(self, balance: float):
        """
        Set stereo balance.

        Args:
            balance: Balance (-1.0 left to 1.0 right)
        """
        self.balance = max(-1.0, min(1.0, balance))

    def set_mute(self, mute: bool):
        """Set mute state"""
        self.mute = mute

    def toggle_mute(self):
        """Toggle mute state"""
        self.mute = not self.mute

    def set_loop(self, loop: bool):
        """Set loop state"""
        self.loop = loop

    def toggle_loop(self):
        """Toggle loop state"""
        self.loop = not self.loop

    def seek(self, position_seconds: float):
        """
        Seek to position in seconds.
        Only works for local files, not streams.

        Args:
            position_seconds: Target position in seconds
        """
        if self.is_stream or self.sample_rate is None:
            return

        with self._lock:
            position_samples = int(position_seconds * self.sample_rate)
            self.seek_samples(position_samples)

    def seek_samples(self, position_samples: int):
        """
        Seek to position in samples.
        Only works for local files, not streams.

        Args:
            position_samples: Target position in samples
        """
        if self.is_stream:
            return

        with self._lock:
            # Clamp to valid range
            if self.audio_data is not None:
                max_position = len(self.audio_data)
                self.position = max(0, min(position_samples, max_position))
            else:
                self.position = max(0, position_samples)

    def seek_relative(self, delta_seconds: float):
        """
        Seek relative to current position.
        Only works for local files, not streams.

        Args:
            delta_seconds: Seconds to seek (positive = forward, negative = backward)
        """
        if self.is_stream or self.sample_rate is None:
            return

        current_seconds = self.get_position_seconds()
        self.seek(current_seconds + delta_seconds)

    def get_position_seconds(self) -> float:
        """
        Get current playback position in seconds.

        Returns:
            Current position in seconds, or 0.0 if not available
        """
        if self.sample_rate is None or self.sample_rate == 0:
            return 0.0
        return self.position / self.sample_rate

    def get_duration_seconds(self) -> float:
        """
        Get total duration in seconds.

        Returns:
            Duration in seconds, or 0.0 if not available
        """
        if self.audio_data is None or self.sample_rate is None or self.sample_rate == 0:
            return 0.0
        return len(self.audio_data) / self.sample_rate

    def get_duration_samples(self) -> int:
        """
        Get total duration in samples.

        Returns:
            Duration in samples, or 0 if not available
        """
        if self.audio_data is None:
            return 0
        return len(self.audio_data)

    def can_seek(self) -> bool:
        """
        Check if seeking is supported for this deck.

        Returns:
            True if seeking is possible (local file loaded), False otherwise
        """
        return not self.is_stream and self.audio_data is not None

    def set_name(self, name: str):
        """Set custom deck name"""
        self.name = name

    def get_effective_volume(self) -> float:
        """
        Get effective volume considering mute state.

        Returns:
            Effective volume (0.0 if muted)
        """
        return 0.0 if self.mute else self.volume

    def get_left_right_volumes(self) -> tuple[float, float]:
        """
        Calculate left and right channel volumes based on balance.

        Returns:
            Tuple of (left_volume, right_volume)
        """
        effective_volume = self.get_effective_volume()

        if self.balance <= 0:
            # Balance to left
            left = effective_volume
            right = effective_volume * (1.0 + self.balance)
        else:
            # Balance to right
            left = effective_volume * (1.0 - self.balance)
            right = effective_volume

        return left, right

    def _set_state(self, new_state: str):
        """
        Set deck state and trigger callback.

        Args:
            new_state: New state value
        """
        old_state = self.state
        self.state = new_state

        if old_state != new_state and self.on_state_change:
            try:
                self.on_state_change(self.deck_id, old_state, new_state)
            except Exception as e:
                logger.error(f"Error in state change callback: {e}")

    def get_info(self) -> dict:
        """
        Get deck information.

        Returns:
            Dictionary with deck information
        """
        return {
            'id': self.deck_id,
            'name': self.name,
            'state': self.state,
            'file_path': self.file_path,
            'is_stream': self.is_stream,
            'volume': self.volume,
            'balance': self.balance,
            'mute': self.mute,
            'loop': self.loop,
            'is_playing': self.is_playing,
            'is_paused': self.is_paused,
            'position': self.position,
        }

    def to_dict(self) -> dict:
        """
        Export deck configuration for saving to project file.

        Returns:
            Dictionary with deck configuration
        """
        if self.state == DECK_STATE_EMPTY:
            return {}

        return {
            'name': self.name,
            'file': self.file_path or '',
            'volume': self.volume,
            'balance': self.balance,
            'mute': self.mute,
            'loop': self.loop,
        }

    def get_effects_dict(self) -> dict:
        """Export per-deck effects configuration for project saving."""
        if self.effects:
            return self.effects.to_dict()
        return {}

    def load_effects_dict(self, data: dict):
        """Load per-deck effects configuration from project data."""
        if self.effects and data:
            self.effects.from_dict(data)

    def from_dict(self, data: dict) -> bool:
        """
        Load deck configuration from dictionary.

        Args:
            data: Dictionary with deck configuration

        Returns:
            True if loaded successfully
        """
        try:
            if not data or 'file' not in data or not data['file']:
                return False

            self.name = data.get('name', f"Deck {self.deck_id}")
            self.volume = float(data.get('volume', 1.0))
            self.balance = float(data.get('balance', 0.0))
            self.mute = bool(data.get('mute', False))
            self.loop = bool(data.get('loop', False))

            return self.load_file(data['file'])
        except Exception as e:
            logger.error(f"Error loading deck from dict: {e}")
            return False

    def __repr__(self) -> str:
        return f"<Deck {self.deck_id}: {self.name} ({self.state})>"
