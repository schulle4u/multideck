"""
TTS Manager - pyttsx3 wrapper for text-to-speech announcements
"""

import sys
import threading

from utils.logger import get_logger

logger = get_logger('tts_manager')

try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False
    logger.warning("pyttsx3 not available - TTS features disabled")


class TTSManager:
    """
    Thread-safe, non-blocking wrapper around pyttsx3.

    Each call to speak() launches a daemon thread that creates a fresh engine
    instance, speaks the text, and exits.  This sidesteps pyttsx3's awkward
    cross-thread behaviour while keeping the calling thread (including the
    audio callback) completely unblocked.
    """

    def __init__(self):
        self.tts_enabled = False
        self._engine_name = ''   # pyttsx3 driver name; '' = platform default
        self._voice_name = ''    # human-readable voice name; '' = engine default
        self._rate = 0           # words per minute; 0 = engine default
        self._volume = -1        # 0-100 %; -1 = engine default

    def configure(self, engine_name: str = '', voice_name: str = '',
                  rate: int = 0, volume: int = -1):
        """
        Store TTS parameters.  Takes effect on the next speak() call.

        Args:
            engine_name: pyttsx3 driver name ('sapi5', 'nsss', 'espeak', '').
                         Empty string uses the platform default.
            voice_name:  Human-readable voice name as returned by get_available_voices()
                         (e.g. ``'Microsoft Hedda Desktop'``).
                         Empty string uses the engine default.
            rate:        Speech rate in words per minute.  0 = engine default.
            volume:      Volume as integer percent 0-100.  -1 = engine default.
        """
        self._engine_name = engine_name
        self._voice_name = voice_name
        self._rate = rate
        self._volume = volume

    def speak(self, text: str):
        """
        Speak *text* asynchronously.  Returns immediately.
        Does nothing if tts_enabled is False or pyttsx3 is unavailable.
        """
        if not self.tts_enabled or not PYTTSX3_AVAILABLE or not text:
            return

        engine_name = self._engine_name
        voice_name = self._voice_name
        rate = self._rate
        volume = self._volume

        def _do_speak():
            try:
                driver = engine_name if engine_name else None
                engine = pyttsx3.init(driverName=driver)
                if rate > 0:
                    engine.setProperty('rate', rate)
                if volume >= 0:
                    engine.setProperty('volume', volume / 100.0)
                if voice_name:
                    voices = engine.getProperty('voices') or []
                    for v in voices:
                        if v.name == voice_name:
                            engine.setProperty('voice', v.id)
                            break
                    else:
                        logger.warning("TTS voice not found: '%s'", voice_name)
                engine.say(text)
                engine.runAndWait()
            except Exception as e:
                logger.error("TTS speak error: %s", e)

        thread = threading.Thread(target=_do_speak, daemon=True)
        thread.start()

    def stop(self):
        """
        Best-effort stop of any ongoing speech.

        pyttsx3 does not provide reliable cross-platform interruption, so this
        is a no-op.  Deck-name announcements are short enough that overlap is
        not a practical concern.
        """

    def get_available_engines(self) -> list:
        """
        Return platform-appropriate TTS engine choices.

        Returns:
            List of (display_label, driver_name) tuples.
            driver_name '' means 'use platform default'.
        """
        engines = [("Platform default", '')]
        if sys.platform == 'win32':
            engines.append(('SAPI5', 'sapi5'))
        elif sys.platform == 'darwin':
            engines.append(('NSSpeechSynthesizer', 'nsss'))
            engines.append(('eSpeak', 'espeak'))
        else:
            engines.append(('eSpeak', 'espeak'))
        return engines

    def get_available_voices(self, engine_name: str = '') -> list:
        """
        Return available voices for *engine_name*.

        Args:
            engine_name: pyttsx3 driver name, or '' for platform default.

        Returns:
            List of (display_name, voice_id) tuples, or [] on failure.
        """
        if not PYTTSX3_AVAILABLE:
            return []
        try:
            driver = engine_name if engine_name else None
            engine = pyttsx3.init(driverName=driver)
            voices = engine.getProperty('voices') or []
            result = [(v.name, v.id) for v in voices]
            engine.runAndWait()
            engine.stop()
            return result
        except Exception as e:
            logger.warning("Could not retrieve TTS voices for engine '%s': %s", engine_name, e)
            return []

    def shutdown(self):
        """Release resources.  Call when the application closes."""
        # No persistent engine to clean up in this implementation.
