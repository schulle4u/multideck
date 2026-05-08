"""
TTS Manager - Prism wrapper for text-to-speech and screen reader announcements.
"""

import threading
import time
import json
import subprocess
import sys
import importlib.util
from pathlib import Path

from utils.logger import get_logger

logger = get_logger('tts_manager')

if sys.platform.startswith('linux'):
    Context = None
    PrismError = Exception
    PRISM_AVAILABLE = importlib.util.find_spec("prism") is not None
else:
    try:
        from prism import Context, PrismError
        PRISM_AVAILABLE = True
    except ImportError:
        Context = None
        PrismError = Exception
        PRISM_AVAILABLE = False

if not PRISM_AVAILABLE:
    logger.warning("prismatoid not available - TTS features disabled")


class TTSManager:
    """
    Thread-safe, non-blocking wrapper around Prism.

    Each call to speak() launches a daemon thread that creates the configured
    Prism backend, speaks or outputs the text, and exits.  This keeps the
    calling thread, including the audio callback, completely unblocked.
    """

    def __init__(self):
        self.tts_enabled = False
        self._engine_name = ''   # Prism backend name; '' = best backend
        self._voice_name = ''    # human-readable voice name; '' = backend default
        self._rate = 0           # 1-100 % normalized Prism rate; 0 = backend default
        self._volume = -1        # 0-100 %; -1 = backend default
        self._lock = threading.RLock()
        self._backend_lock = threading.RLock()
        self._context = None
        self._active_backend = None
        self._active_process = None

    def configure(self, engine_name: str = '', voice_name: str = '',
                  rate: int = 0, volume: int = -1):
        """
        Store TTS parameters.  Takes effect on the next speak() call.

        Args:
            engine_name: Prism backend name (e.g. 'NVDA', 'OneCore', 'SAPI', '').
                         Empty string uses Prism's best backend.
            voice_name:  Human-readable voice name as returned by
                         get_available_voices(). Empty string uses the backend
                         default. Screen reader backends may not expose voices.
            rate:        Speech rate as integer percent 1-100.
                         0 = backend default; Prism treats 50% as neutral.
            volume:      Volume as integer percent 0-100. -1 = backend default.
        """
        with self._lock:
            self._engine_name = engine_name
            self._voice_name = voice_name
            self._rate = rate
            self._volume = volume

    def _get_context(self):
        """Return the lazily-created Prism context, or None on failure."""
        if self._use_worker_process():
            return None
        if not PRISM_AVAILABLE:
            return None
        with self._lock:
            if self._context is None:
                try:
                    self._context = Context()
                except Exception as e:
                    logger.error("Could not initialize Prism TTS context: %s", e)
                    return None
            return self._context

    def _use_worker_process(self) -> bool:
        """Keep Prism out of the wx/GTK process on Linux."""
        return sys.platform.startswith('linux')

    def _worker_script(self) -> str:
        return str(Path(__file__).with_name('prism_tts_worker.py'))

    def _worker_command(self, *args) -> list:
        if getattr(sys, 'frozen', False):
            worker_name = 'prism_tts_worker.exe' if sys.platform == 'win32' else 'prism_tts_worker'
            worker_path = Path(sys.executable).with_name(worker_name)
            return [str(worker_path), *args]
        return [sys.executable, self._worker_script(), *args]

    def _run_worker_json(self, *args, timeout: float = 5.0):
        try:
            result = subprocess.run(
                self._worker_command(*args),
                capture_output=True,
                text=True,
                timeout=timeout,
                check=True,
            )
            return json.loads(result.stdout or "[]")
        except Exception as e:
            logger.debug("Prism worker command failed: %s", e)
            return []

    def _speak_with_worker(self, text: str, engine_name: str, voice_name: str,
                           rate: int, volume: int):
        self.stop()
        config = {
            "text": text,
            "engine_name": engine_name,
            "voice_name": voice_name,
            "rate": rate,
            "volume": volume,
        }
        try:
            process = subprocess.Popen(
                self._worker_command(
                    "speak",
                    "--config",
                    json.dumps(config, ensure_ascii=False),
                ),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            with self._lock:
                self._active_process = process
        except Exception as e:
            logger.error("TTS worker speak error: %s", e)

    def _create_backend(self, engine_name: str = ''):
        """Create the requested Prism backend, or Prism's best backend."""
        context = self._get_context()
        if context is None:
            return None
        with self._lock:
            if engine_name:
                backend_id = context.id_of(engine_name)
                return context.create(backend_id)
            return context.create_best()

    def _backend_can_announce(self, backend) -> bool:
        """Return True if a Prism backend can produce user-facing output."""
        features = backend.features
        return features.supports_speak or features.supports_output

    def _backend_is_available(self, backend) -> bool:
        """Return True if a created Prism backend is usable for announcements."""
        return self._backend_can_announce(backend)

    def _find_voice_index(self, backend, voice_name: str):
        """Return the Prism voice index for voice_name, or None if unavailable."""
        features = backend.features
        if not voice_name or not (
            features.supports_count_voices and
            features.supports_get_voice_name and
            features.supports_set_voice
        ):
            return None
        try:
            backend.refresh_voices()
        except PrismError:
            pass
        for idx in range(backend.voices_count):
            if backend.get_voice_name(idx) == voice_name:
                return idx
        return None

    def _wait_for_backend_to_finish(self, backend, text: str):
        """
        Keep the Prism backend alive until playback/output finishes.

        Some TTS backends return from speak() once playback has merely started.
        Freeing the backend immediately can then cancel the announcement.
        """
        features = backend.features
        if features.supports_is_speaking:
            deadline = time.monotonic() + 60.0
            startup_deadline = time.monotonic() + 2.0
            observed_speaking = False
            while time.monotonic() < deadline:
                try:
                    with self._backend_lock:
                        speaking = backend.speaking
                        observed_speaking = observed_speaking or speaking
                        if not speaking and (observed_speaking or time.monotonic() >= startup_deadline):
                            return
                except PrismError:
                    return
                time.sleep(0.05)
            logger.warning("Timed out waiting for Prism backend '%s' to finish", backend.name)
            return

        # Screen reader backends often cannot report speaking state. Give them
        # a short lifetime buffer so asynchronous delivery can complete.
        time.sleep(min(10.0, max(1.0, len(text) * 0.08)))

    def speak(self, text: str):
        """
        Speak *text* asynchronously.  Returns immediately.
        Does nothing if tts_enabled is False or Prism is unavailable.
        """
        if not self.tts_enabled or not PRISM_AVAILABLE or not text:
            return

        with self._lock:
            engine_name = self._engine_name
            voice_name = self._voice_name
            rate = self._rate
            volume = self._volume

        if self._use_worker_process():
            self._speak_with_worker(text, engine_name, voice_name, rate, volume)
            return

        self.stop()

        def _do_speak():
            backend = None
            try:
                backend = self._create_backend(engine_name)
                if backend is None:
                    return
                features = backend.features

                if rate != 0 and features.supports_set_rate:
                    backend.rate = max(0.0, min(1.0, rate / 100.0))
                if volume >= 0 and features.supports_set_volume:
                    backend.volume = volume / 100.0
                if voice_name:
                    voice_idx = self._find_voice_index(backend, voice_name)
                    if voice_idx is None:
                        logger.warning("TTS voice not found: '%s'", voice_name)
                    else:
                        backend.voice = voice_idx

                with self._lock:
                    self._active_backend = backend

                if features.supports_braille and features.supports_output:
                    with self._backend_lock:
                        backend.output(text, interrupt=True)
                elif features.supports_speak:
                    with self._backend_lock:
                        backend.speak(text, interrupt=True)
                elif features.supports_output:
                    with self._backend_lock:
                        backend.output(text, interrupt=True)
                else:
                    logger.warning("Prism backend '%s' cannot speak or output text", backend.name)
                    return
                self._wait_for_backend_to_finish(backend, text)
            except Exception as e:
                logger.error("TTS speak error: %s", e)
            finally:
                with self._lock:
                    if self._active_backend is backend:
                        self._active_backend = None

        thread = threading.Thread(target=_do_speak, daemon=True)
        thread.start()

    def stop(self):
        """
        Best-effort stop of any ongoing speech.

        Some Prism backends, especially screen readers, may not support stop.
        """
        with self._lock:
            backend = self._active_backend
            process = self._active_process
            self._active_process = None
        if process is not None and process.poll() is None:
            try:
                process.terminate()
            except Exception as e:
                logger.warning("TTS worker stop error: %s", e)
        if backend is None:
            return
        try:
            with self._backend_lock:
                if backend.features.supports_stop:
                    backend.stop()
        except Exception as e:
            logger.warning("TTS stop error: %s", e)

    def get_available_engines(self) -> list:
        """
        Return Prism backend choices.

        Returns:
            List of (display_label, backend_name) tuples.
            backend_name '' means 'use Prism's best backend'.
        """
        if self._use_worker_process():
            if PRISM_AVAILABLE:
                return [("Prism best backend", '')]
            return []

        engines = []
        context = self._get_context()
        if context is None:
            return engines
        try:
            backend = self._create_backend('')
            if backend is not None and self._backend_is_available(backend):
                engines.append(("Prism best backend", ''))
        except Exception as e:
            logger.debug("Prism best backend is not available: %s", e)
        try:
            for idx in range(context.backends_count):
                backend_id = context.id_of(idx)
                name = context.name_of(backend_id)
                try:
                    backend = context.create(backend_id)
                    if self._backend_is_available(backend):
                        engines.append((name, name))
                    else:
                        logger.debug("Skipping unavailable Prism backend '%s'", name)
                except Exception as e:
                    logger.debug("Skipping unavailable Prism backend '%s': %s", name, e)
        except Exception as e:
            logger.debug("Could not retrieve Prism backends: %s", e)
        return engines

    def get_available_voices(self, engine_name: str = '') -> list:
        """
        Return available voices for *engine_name*.

        Args:
            engine_name: Prism backend name, or '' for Prism's best backend.

        Returns:
            List of (display_name, voice_index) tuples, or [] on failure.
        """
        if not PRISM_AVAILABLE:
            return []
        if self._use_worker_process():
            return []
        try:
            backend = self._create_backend(engine_name)
            if backend is None or not self._backend_is_available(backend):
                return []
            features = backend.features
            if not (
                features.supports_count_voices and
                features.supports_get_voice_name
            ):
                return []
            try:
                backend.refresh_voices()
            except PrismError:
                pass
            result = []
            for idx in range(backend.voices_count):
                result.append((backend.get_voice_name(idx), str(idx)))
            return result
        except Exception as e:
            logger.debug("Could not retrieve TTS voices for engine '%s': %s", engine_name, e)
            return []

    def shutdown(self):
        """Release resources.  Call when the application closes."""
        self.stop()
        with self._lock:
            self._active_backend = None
            self._context = None
            self._active_process = None
