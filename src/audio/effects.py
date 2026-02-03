"""
Audio Effects - Real-time effect chain using pedalboard (Spotify)
"""

import numpy as np
import threading
from typing import Optional

from utils.logger import get_logger

logger = get_logger('effects')

# Lazy import pedalboard to allow graceful fallback
_pedalboard_available = None


def _check_pedalboard():
    global _pedalboard_available
    if _pedalboard_available is None:
        try:
            import pedalboard
            _pedalboard_available = True
        except ImportError:
            _pedalboard_available = False
            logger.warning("pedalboard not installed - audio effects unavailable")
    return _pedalboard_available


class EffectChain:
    """
    Manages a chain of audio effects using pedalboard.
    Thread-safe: parameters can be changed from the GUI thread
    while process() is called from the audio thread.
    """

    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.enabled = False
        self._lock = threading.RLock()
        self._board = None

        # Effect instances
        self.reverb = None
        self.delay = None
        self.eq_low = None
        self.eq_mid = None
        self.eq_high = None
        self.chorus = None
        self.compressor = None
        self.limiter = None

        # Enable flags
        self.reverb_enabled = False
        self.delay_enabled = False
        self.eq_enabled = False
        self.chorus_enabled = False
        self.compressor_enabled = False
        self.limiter_enabled = False

        if _check_pedalboard():
            self._initialize_effects()

    def _initialize_effects(self):
        """Create all effect objects with default parameters."""
        from pedalboard import (
            Reverb, Delay, Chorus, Compressor, Limiter,
            LowShelfFilter, PeakFilter, HighShelfFilter
        )

        self.reverb = Reverb(
            room_size=0.5,
            damping=0.5,
            wet_level=0.33,
            dry_level=0.7,
            width=1.0,
        )

        self.delay = Delay(
            delay_seconds=0.3,
            feedback=0.3,
            mix=0.3,
        )

        self.eq_low = LowShelfFilter(
            cutoff_frequency_hz=200.0,
            gain_db=0.0,
            q=0.707,
        )
        self.eq_mid = PeakFilter(
            cutoff_frequency_hz=1000.0,
            gain_db=0.0,
            q=1.0,
        )
        self.eq_high = HighShelfFilter(
            cutoff_frequency_hz=8000.0,
            gain_db=0.0,
            q=0.707,
        )

        self.chorus = Chorus(
            rate_hz=1.0,
            depth=0.25,
            centre_delay_ms=7.0,
            feedback=0.0,
            mix=0.5,
        )

        self.compressor = Compressor(
            threshold_db=-20.0,
            ratio=4.0,
            attack_ms=5.0,
            release_ms=50.0,
        )

        self.limiter = Limiter(
            threshold_db=-1.0,
            release_ms=50.0,
        )

        self._rebuild_board()

    def _rebuild_board(self):
        """Rebuild the pedalboard from currently enabled effects."""
        if not _check_pedalboard():
            return

        from pedalboard import Pedalboard

        active = []
        if self.eq_enabled and self.eq_low is not None:
            active.extend([self.eq_low, self.eq_mid, self.eq_high])
        if self.compressor_enabled and self.compressor is not None:
            active.append(self.compressor)
        if self.chorus_enabled and self.chorus is not None:
            active.append(self.chorus)
        if self.reverb_enabled and self.reverb is not None:
            active.append(self.reverb)
        if self.delay_enabled and self.delay is not None:
            active.append(self.delay)
        if self.limiter_enabled and self.limiter is not None:
            active.append(self.limiter)

        self._board = Pedalboard(active)

    def process(self, audio_data: np.ndarray) -> np.ndarray:
        """
        Process audio through the effect chain.
        Called from the audio callback thread.

        Args:
            audio_data: Stereo audio (frames, 2), float32

        Returns:
            Processed audio, same shape
        """
        if not self.enabled or self._board is None or len(self._board) == 0:
            return audio_data

        with self._lock:
            try:
                # pedalboard expects contiguous (channels, samples) float32
                transposed = np.ascontiguousarray(audio_data.T, dtype=np.float32)
                # reset=False preserves internal state (delay lines, reverb tails)
                # between callback invocations - essential for streaming
                processed = self._board(transposed, self.sample_rate, reset=False)
                return np.ascontiguousarray(processed.T, dtype=np.float32)
            except Exception as e:
                logger.error(f"Error processing effects: {e}")
                return audio_data

    def enable_effect(self, effect_name: str, enabled: bool):
        """Enable or disable a specific effect and rebuild the chain."""
        with self._lock:
            attr = f"{effect_name}_enabled"
            if hasattr(self, attr):
                setattr(self, attr, enabled)
                self._rebuild_board()

    # --- Parameter setters (thread-safe) ---

    def set_reverb_param(self, **kwargs):
        with self._lock:
            if self.reverb is None:
                return
            for key, val in kwargs.items():
                if hasattr(self.reverb, key):
                    setattr(self.reverb, key, val)

    def set_delay_param(self, **kwargs):
        with self._lock:
            if self.delay is None:
                return
            for key, val in kwargs.items():
                if hasattr(self.delay, key):
                    setattr(self.delay, key, val)

    def set_eq_param(self, band: str, **kwargs):
        """Set EQ parameter. band is 'low', 'mid', or 'high'."""
        with self._lock:
            obj = getattr(self, f"eq_{band}", None)
            if obj is None:
                return
            for key, val in kwargs.items():
                if hasattr(obj, key):
                    setattr(obj, key, val)

    def set_chorus_param(self, **kwargs):
        with self._lock:
            if self.chorus is None:
                return
            for key, val in kwargs.items():
                if hasattr(self.chorus, key):
                    setattr(self.chorus, key, val)

    def set_compressor_param(self, **kwargs):
        with self._lock:
            if self.compressor is None:
                return
            for key, val in kwargs.items():
                if hasattr(self.compressor, key):
                    setattr(self.compressor, key, val)

    def set_limiter_param(self, **kwargs):
        with self._lock:
            if self.limiter is None:
                return
            for key, val in kwargs.items():
                if hasattr(self.limiter, key):
                    setattr(self.limiter, key, val)

    # --- Serialization ---

    def to_dict(self) -> dict:
        """Export effect chain settings as flat dict for INI serialization."""
        d = {
            'enabled': self.enabled,
            'reverb_enabled': self.reverb_enabled,
            'delay_enabled': self.delay_enabled,
            'eq_enabled': self.eq_enabled,
            'chorus_enabled': self.chorus_enabled,
            'compressor_enabled': self.compressor_enabled,
            'limiter_enabled': self.limiter_enabled,
        }

        if self.reverb is not None:
            d.update({
                'reverb_room_size': self.reverb.room_size,
                'reverb_damping': self.reverb.damping,
                'reverb_wet_level': self.reverb.wet_level,
                'reverb_dry_level': self.reverb.dry_level,
                'reverb_width': self.reverb.width,
            })

        if self.delay is not None:
            d.update({
                'delay_seconds': self.delay.delay_seconds,
                'delay_feedback': self.delay.feedback,
                'delay_mix': self.delay.mix,
            })

        if self.eq_low is not None:
            d.update({
                'eq_low_gain_db': self.eq_low.gain_db,
                'eq_mid_gain_db': self.eq_mid.gain_db,
                'eq_high_gain_db': self.eq_high.gain_db,
            })

        if self.chorus is not None:
            d.update({
                'chorus_rate_hz': self.chorus.rate_hz,
                'chorus_depth': self.chorus.depth,
                'chorus_centre_delay_ms': self.chorus.centre_delay_ms,
                'chorus_feedback': self.chorus.feedback,
                'chorus_mix': self.chorus.mix,
            })

        if self.compressor is not None:
            d.update({
                'compressor_threshold_db': self.compressor.threshold_db,
                'compressor_ratio': self.compressor.ratio,
                'compressor_attack_ms': self.compressor.attack_ms,
                'compressor_release_ms': self.compressor.release_ms,
            })

        if self.limiter is not None:
            d.update({
                'limiter_threshold_db': self.limiter.threshold_db,
                'limiter_release_ms': self.limiter.release_ms,
            })

        return d

    def from_dict(self, data: dict):
        """Load effect chain settings from flat dict."""
        with self._lock:
            self.enabled = _parse_bool(data.get('enabled', False))

            self.reverb_enabled = _parse_bool(data.get('reverb_enabled', False))
            self.delay_enabled = _parse_bool(data.get('delay_enabled', False))
            self.eq_enabled = _parse_bool(data.get('eq_enabled', False))
            self.chorus_enabled = _parse_bool(data.get('chorus_enabled', False))
            self.compressor_enabled = _parse_bool(data.get('compressor_enabled', False))
            self.limiter_enabled = _parse_bool(data.get('limiter_enabled', False))

            if self.reverb is not None:
                self.reverb.room_size = float(data.get('reverb_room_size', 0.5))
                self.reverb.damping = float(data.get('reverb_damping', 0.5))
                self.reverb.wet_level = float(data.get('reverb_wet_level', 0.33))
                self.reverb.dry_level = float(data.get('reverb_dry_level', 0.7))
                self.reverb.width = float(data.get('reverb_width', 1.0))

            if self.delay is not None:
                self.delay.delay_seconds = float(data.get('delay_seconds', 0.3))
                self.delay.feedback = float(data.get('delay_feedback', 0.3))
                self.delay.mix = float(data.get('delay_mix', 0.3))

            if self.eq_low is not None:
                self.eq_low.gain_db = float(data.get('eq_low_gain_db', 0.0))
                self.eq_mid.gain_db = float(data.get('eq_mid_gain_db', 0.0))
                self.eq_high.gain_db = float(data.get('eq_high_gain_db', 0.0))

            if self.chorus is not None:
                self.chorus.rate_hz = float(data.get('chorus_rate_hz', 1.0))
                self.chorus.depth = float(data.get('chorus_depth', 0.25))
                self.chorus.centre_delay_ms = float(data.get('chorus_centre_delay_ms', 7.0))
                self.chorus.feedback = float(data.get('chorus_feedback', 0.0))
                self.chorus.mix = float(data.get('chorus_mix', 0.5))

            if self.compressor is not None:
                self.compressor.threshold_db = float(data.get('compressor_threshold_db', -20.0))
                self.compressor.ratio = float(data.get('compressor_ratio', 4.0))
                self.compressor.attack_ms = float(data.get('compressor_attack_ms', 5.0))
                self.compressor.release_ms = float(data.get('compressor_release_ms', 50.0))

            if self.limiter is not None:
                self.limiter.threshold_db = float(data.get('limiter_threshold_db', -1.0))
                self.limiter.release_ms = float(data.get('limiter_release_ms', 50.0))

            self._rebuild_board()


def _parse_bool(value) -> bool:
    """Parse a boolean from various representations (bool, str, int)."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ('true', '1', 'yes')
    return bool(value)
