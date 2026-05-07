"""
Audio Effects - Real-time effect chain using pedalboard (Spotify)
"""

import json
import gc
import os
import platform
import numpy as np
import sys
import threading
from typing import Optional

from utils.logger import get_logger

logger = get_logger('effects')

PLUGIN_BUNDLE_EXTENSIONS = ('.vst3', '.component')
PLUGIN_FILE_EXTENSIONS = PLUGIN_BUNDLE_EXTENSIONS

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
        self.gain = None

        # VST plugin slots: list of {'path': str, 'plugin': obj, 'enabled': bool, 'name': str}
        self.vst_slots = []

        # Enable flags
        self.reverb_enabled = False
        self.delay_enabled = False
        self.eq_enabled = False
        self.chorus_enabled = False
        self.compressor_enabled = False
        self.limiter_enabled = False
        self.gain_enabled = False

        if _check_pedalboard():
            self._initialize_effects()

    def _initialize_effects(self):
        """Create all effect objects with default parameters."""
        from pedalboard import (
            Reverb, Delay, Chorus, Compressor, Limiter,
            LowShelfFilter, PeakFilter, HighShelfFilter,
            Gain
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

        self.gain = Gain(
            gain_db=0.0,
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
        if self.gain_enabled and self.gain is not None:
            active.append(self.gain)
        for slot in self.vst_slots:
            if slot['enabled'] and slot['plugin'] is not None:
                if self._plugin_is_instrument(slot['plugin']):
                    logger.warning(f"Skipping instrument plugin in effect chain: {slot['name']}")
                    continue
                active.append(slot['plugin'])

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

    def set_gain_param(self, **kwargs):
        with self._lock:
            if self.gain is None:
                return
            for key, val in kwargs.items():
                if hasattr(self.gain, key):
                    setattr(self.gain, key, val)

    # --- VST plugin management ---

    @staticmethod
    def _normalize_plugin_path(path: str) -> str:
        """Return an absolute plugin path suitable for pedalboard."""
        return os.path.abspath(os.path.expanduser(path or ''))

    @staticmethod
    def _plugin_display_name(path: str, plugin=None, plugin_name: Optional[str] = None) -> str:
        """Build a stable display name for files and bundle directories."""
        if plugin_name:
            return plugin_name
        if plugin is not None:
            name = getattr(plugin, 'name', None)
            if name:
                return name
        return os.path.splitext(os.path.basename(path.rstrip(os.sep)))[0]

    @staticmethod
    def _vst3_arch_dir_preferences() -> list:
        """Return likely VST3 Contents architecture directories for this host."""
        machine = platform.machine().lower()
        is_64_bit = sys.maxsize > 2 ** 32
        if sys.platform == 'win32':
            if machine in ('arm64', 'aarch64'):
                return ['arm64-win', 'x86_64-win']
            return ['x86_64-win', 'x64-win'] if is_64_bit else ['i386-win', 'x86-win']
        if sys.platform == 'darwin':
            return ['MacOS']
        if machine in ('arm64', 'aarch64'):
            return ['aarch64-linux', 'arm64-linux', 'x86_64-linux']
        return ['x86_64-linux'] if is_64_bit else ['i386-linux', 'x86-linux']

    @staticmethod
    def _find_vst3_bundle_binaries(bundle_path: str) -> list:
        """Find loadable binaries inside a VST3 bundle directory."""
        contents_path = os.path.join(bundle_path, 'Contents')
        if not os.path.isdir(contents_path):
            return []

        search_dirs = []
        for dirname in EffectChain._vst3_arch_dir_preferences():
            candidate = os.path.join(contents_path, dirname)
            if os.path.isdir(candidate):
                search_dirs.append(candidate)

        for entry in sorted(os.scandir(contents_path), key=lambda item: item.name.lower()):
            if entry.is_dir() and entry.name != 'Resources' and entry.path not in search_dirs:
                search_dirs.append(entry.path)

        binaries = []
        for search_dir in search_dirs:
            try:
                direct_files = [
                    os.path.join(search_dir, name)
                    for name in sorted(os.listdir(search_dir))
                    if name.lower().endswith('.vst3')
                    and os.path.isfile(os.path.join(search_dir, name))
                ]
                binaries.extend(direct_files)
                if direct_files:
                    continue
                for root, _dirs, files in os.walk(search_dir):
                    for name in sorted(files):
                        if name.lower().endswith('.vst3'):
                            binaries.append(os.path.join(root, name))
            except OSError as e:
                logger.debug(f"Could not inspect VST3 bundle directory {search_dir!r}: {e}")

        seen = set()
        unique = []
        for binary in binaries:
            normalized = os.path.normcase(os.path.abspath(binary))
            if normalized not in seen:
                seen.add(normalized)
                unique.append(binary)
        return unique

    @staticmethod
    def _resolve_plugin_load_path(path: str) -> str:
        """Resolve bundle roots to the plugin binary path pedalboard can scan."""
        normalized = EffectChain._normalize_plugin_path(path)
        ext = os.path.splitext(normalized.rstrip(os.sep))[1].lower()
        if os.path.isdir(normalized) and ext == '.vst3':
            binaries = EffectChain._find_vst3_bundle_binaries(normalized)
            if binaries:
                return binaries[0]
        return normalized

    @staticmethod
    def _plugin_is_instrument(plugin) -> bool:
        """Return True when a pedalboard external plugin is an instrument."""
        try:
            is_instrument = getattr(plugin, 'is_instrument', False)
            if callable(is_instrument):
                is_instrument = is_instrument()
            return bool(is_instrument)
        except Exception as e:
            logger.debug(f"Could not determine whether plugin is an instrument: {e}")
            return False

    @staticmethod
    def is_supported_plugin_path(path: str) -> bool:
        """Return True for supported VST3/AU plugin files or bundle directories."""
        if not path:
            return False
        normalized = EffectChain._normalize_plugin_path(path)
        if not os.path.exists(normalized):
            return False
        ext = os.path.splitext(normalized.rstrip(os.sep))[1].lower()
        if os.path.isdir(normalized):
            return ext in PLUGIN_BUNDLE_EXTENSIONS
        return ext in PLUGIN_FILE_EXTENSIONS

    @staticmethod
    def get_plugin_names(path: str) -> list:
        """Return plugin names exposed by a VST3 bundle/file when pedalboard can list them."""
        if not _check_pedalboard():
            return []
        normalized = EffectChain._normalize_plugin_path(path)
        ext = os.path.splitext(normalized.rstrip(os.sep))[1].lower()
        if ext != '.vst3' or not os.path.exists(normalized):
            return []
        load_path = EffectChain._resolve_plugin_load_path(normalized)
        try:
            from pedalboard import VST3Plugin
            return list(VST3Plugin.get_plugin_names_for_file(load_path))
        except Exception as e:
            logger.debug(f"Could not enumerate plugins in {normalized!r}: {e}")
            return []

    def add_vst(self, path: str, plugin_name: Optional[str] = None):
        """Load and append a VST3/AU plugin to the chain.

        Returns an error string on failure, or None on success.
        """
        if not _check_pedalboard():
            return "pedalboard not available"
        path = self._normalize_plugin_path(path)
        if not os.path.exists(path):
            return f"Plugin path not found: {path}"
        if not self.is_supported_plugin_path(path):
            return "Unsupported plugin path. Choose a .vst3/.component file or bundle."
        load_path = self._resolve_plugin_load_path(path)
        path_ext = os.path.splitext(path.rstrip(os.sep))[1].lower()
        if sys.platform == 'win32' and os.path.isdir(path) and path_ext == '.vst3' and load_path == path:
            return f"No loadable plugin binary found in bundle: {path}"
        try:
            from pedalboard import load_plugin
            plugin = load_plugin(load_path, plugin_name=plugin_name)
            name = self._plugin_display_name(path, plugin, plugin_name)
            if self._plugin_is_instrument(plugin):
                del plugin
                gc.collect()
                return f"Instrument plugins are not supported in effect chains: {name}"
            slot = {
                'path': path,
                'load_path': load_path,
                'plugin_name': plugin_name,
                'plugin': plugin,
                'enabled': True,
                'name': name,
            }
            with self._lock:
                self.vst_slots.append(slot)
                try:
                    self._rebuild_board()
                except Exception:
                    self.vst_slots.remove(slot)
                    raise
            return None
        except Exception as e:
            gc.collect()
            logger.error(f"Failed to load VST plugin {path}: {e}")
            return str(e)

    def remove_vst(self, index: int):
        """Remove a VST slot by index."""
        with self._lock:
            if 0 <= index < len(self.vst_slots):
                self.vst_slots.pop(index)
                self._rebuild_board()

    def move_vst(self, index: int, direction: int):
        """Swap a VST slot with its neighbour. direction: -1 = up, +1 = down."""
        with self._lock:
            new_idx = index + direction
            if 0 <= index < len(self.vst_slots) and 0 <= new_idx < len(self.vst_slots):
                self.vst_slots[index], self.vst_slots[new_idx] = (
                    self.vst_slots[new_idx], self.vst_slots[index])
                self._rebuild_board()

    def enable_vst(self, index: int, enabled: bool):
        """Enable or disable a VST slot without removing it."""
        with self._lock:
            if 0 <= index < len(self.vst_slots):
                self.vst_slots[index]['enabled'] = enabled
                self._rebuild_board()

    def set_vst_param(self, index: int, param_name: str, value):
        """Set a parameter on a VST plugin by its attribute name."""
        with self._lock:
            if 0 <= index < len(self.vst_slots):
                plugin = self.vst_slots[index]['plugin']
                try:
                    setattr(plugin, param_name, value)
                except Exception as e:
                    logger.error(f"VST param error [{index}].{param_name}={value}: {e}")

    def get_vst_parameters(self, index: int) -> dict:
        """Return the parameters dict of a loaded VST plugin.

        Keys are Python-identifier-safe parameter names; values are
        pedalboard ParameterValue objects (read-only attributes:
        .value, .min_value, .max_value, .name, .label, .is_discrete,
        .valid_values).
        Returns an empty dict when the index is invalid or on error.
        """
        if 0 <= index < len(self.vst_slots):
            plugin = self.vst_slots[index]['plugin']
            try:
                return dict(plugin.parameters)
            except Exception as e:
                logger.error(f"Could not read VST parameters [{index}]: {e}")
        return {}

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
            'gain_enabled': self.gain_enabled,
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

        if self.gain is not None:
            d.update({
                'gain_gain_db': self.gain.gain_db,
            })

        d['vst_count'] = len(self.vst_slots)
        for i, slot in enumerate(self.vst_slots):
            d[f'vst_{i}_path'] = slot['path']
            d[f'vst_{i}_plugin_name'] = slot.get('plugin_name') or ''
            d[f'vst_{i}_enabled'] = slot['enabled']
            d[f'vst_{i}_name'] = slot['name']
            params = {}
            try:
                plugin = slot['plugin']
                for name, param in plugin.parameters.items():
                    try:
                        # pedalboard exposes parameter values as attributes on the
                        # plugin object itself (plugin.param_name), not on the
                        # _AudioProcessorParameter metadata object.
                        raw = getattr(plugin, name)
                        # Normalize to JSON-serializable Python primitives.
                        # pedalboard / numpy may return float64, bool_, int32, etc.
                        if isinstance(raw, bool):
                            params[name] = bool(raw)
                        elif isinstance(raw, float) or (
                                hasattr(raw, '__float__') and not isinstance(raw, str)):
                            params[name] = float(raw)
                        elif isinstance(raw, int) or (
                                hasattr(raw, '__index__') and not isinstance(raw, bool)):
                            params[name] = int(raw)
                        else:
                            params[name] = str(raw)
                    except Exception as e:
                        logger.debug(f"Skipping VST param {name!r} in slot {i}: {e}")
            except Exception as e:
                logger.warning(f"Could not iterate parameters for VST slot {i}: {e}")
            d[f'vst_{i}_params'] = json.dumps(params)

        return d

    def from_dict(self, data: dict):
        """Load effect chain settings from flat dict."""
        with self._lock:
            # Drop any VST plugins from the previous project/session so that
            # they don't accumulate across loads.  Clearing the list and
            # rebuilding before the new VSTs are appended below is sufficient;
            # Python will garbage-collect the plugin objects and pedalboard
            # releases the native VST3 resources in their destructors.
            self.vst_slots = []

            self.enabled = _parse_bool(data.get('enabled', False))

            self.reverb_enabled = _parse_bool(data.get('reverb_enabled', False))
            self.delay_enabled = _parse_bool(data.get('delay_enabled', False))
            self.eq_enabled = _parse_bool(data.get('eq_enabled', False))
            self.chorus_enabled = _parse_bool(data.get('chorus_enabled', False))
            self.compressor_enabled = _parse_bool(data.get('compressor_enabled', False))
            self.limiter_enabled = _parse_bool(data.get('limiter_enabled', False))
            self.gain_enabled = _parse_bool(data.get('gain_enabled', False))

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

            if self.gain is not None:
                self.gain.gain_db = float(data.get('gain_gain_db', 0.0))

            self._rebuild_board()

        vst_count = int(data.get('vst_count', 0))
        for i in range(vst_count):
            path = data.get(f'vst_{i}_path', '')
            if not path or not os.path.exists(path):
                logger.warning(f"VST plugin path not found, skipping: {path!r}")
                continue
            plugin_name = data.get(f'vst_{i}_plugin_name', '') or None
            error = self.add_vst(path, plugin_name=plugin_name)
            if error:
                logger.error(f"Could not restore VST plugin {path!r}: {error}")
                continue
            enabled = _parse_bool(data.get(f'vst_{i}_enabled', True))
            self.vst_slots[-1]['enabled'] = enabled
            try:
                saved_params = json.loads(data.get(f'vst_{i}_params', '{}'))
                plugin = self.vst_slots[-1]['plugin']
                for param_name, value in saved_params.items():
                    try:
                        setattr(plugin, param_name, value)
                    except Exception as e:
                        logger.debug(f"Could not restore VST param {param_name!r}: {e}")
            except Exception as e:
                logger.warning(f"Could not restore VST params for slot {i}: {e}")
        self._rebuild_board()


def _parse_bool(value) -> bool:
    """Parse a boolean from various representations (bool, str, int)."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ('true', '1', 'yes')
    return bool(value)
