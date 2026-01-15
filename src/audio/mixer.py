"""
Mixer - Manages multiple decks and operating modes
"""

import numpy as np
import threading
import time
from typing import List, Optional, Callable

from audio.deck import Deck
from audio.audio_engine import AudioEngine
from config.defaults import MODE_MIXER, MODE_SOLO, MODE_AUTOMATIC, DECK_STATE_PLAYING


class Mixer:
    """
    Manages multiple audio decks and mixing modes.
    Supports three operating modes: Mixer, Solo, and Automatic.
    """

    def __init__(self, audio_engine: AudioEngine, num_decks: int = 10, recorder=None):
        """
        Initialize mixer.

        Args:
            audio_engine: AudioEngine instance
            num_decks: Number of decks (2, 4, 6, 8, or 10)
            recorder: Optional Recorder instance for master output recording
        """
        self.audio_engine = audio_engine
        self.num_decks = num_decks
        self.recorder = recorder

        # Create decks
        self.decks: List[Deck] = []
        for i in range(num_decks):
            deck = Deck(i + 1, audio_engine.sample_rate)
            self.decks.append(deck)

        # Mixer settings
        self.master_volume = 0.8
        self.mode = MODE_MIXER
        self.active_deck_index = 0  # For Solo and Automatic modes

        # Automatic mode settings
        self.auto_switch_interval = 10  # seconds
        self.auto_switch_enabled = False
        self._auto_thread: Optional[threading.Thread] = None
        self._auto_stop_event = threading.Event()

        # Crossfade settings
        self.crossfade_enabled = True
        self.crossfade_duration = 2.0  # seconds

        # Crossfade state
        self._crossfade_active = False
        self._crossfade_from_deck = 0
        self._crossfade_to_deck = 0
        self._crossfade_samples_total = 0
        self._crossfade_samples_done = 0

        # Audio processing
        self._lock = threading.Lock()
        self._loaded_audio_cache = {}  # deck_id -> audio_data

        # Underflow warning rate limiting
        self._last_underflow_time = 0
        self._underflow_count = 0

        # Callbacks
        self.on_mode_change: Optional[Callable] = None
        self.on_active_deck_change: Optional[Callable] = None

        # Start audio stream
        self._start_playback()

    def _start_playback(self):
        """Start audio output stream with callback"""
        self.audio_engine.start_stream(self._audio_callback)

    def _audio_callback(self, outdata, frames, time_info, status):
        """
        Audio callback for sounddevice.
        Called by audio thread to fill output buffer.
        """
        if status:
            # Rate-limit underflow warnings (max once per second)
            current_time = time.time()
            if current_time - self._last_underflow_time >= 1.0:
                if self._underflow_count > 0:
                    print(f"Audio callback status: {status} (occurred {self._underflow_count + 1}x)")
                else:
                    print(f"Audio callback status: {status}")
                self._last_underflow_time = current_time
                self._underflow_count = 0
            else:
                self._underflow_count += 1

        try:
            # Generate audio for current mode
            audio_data = self._generate_audio(frames)

            # Apply master volume
            audio_data *= self.master_volume

            # Record to file if recording is active
            if self.recorder and self.recorder.is_recording:
                try:
                    self.recorder.write_frames(audio_data)
                except Exception as rec_error:
                    print(f"Error writing to recorder: {rec_error}")

            # Copy to output buffer
            outdata[:] = audio_data

        except Exception as e:
            print(f"Error in audio callback: {e}")
            outdata.fill(0)

    def _generate_audio(self, frames: int) -> np.ndarray:
        """
        Generate audio based on current operating mode.

        Args:
            frames: Number of frames to generate

        Returns:
            Audio data (frames, 2)
        """
        if self.mode == MODE_MIXER:
            return self._generate_mixer_mode(frames)
        elif self.mode == MODE_SOLO:
            return self._generate_solo_mode(frames)
        elif self.mode == MODE_AUTOMATIC:
            return self._generate_automatic_mode(frames)
        else:
            return self.audio_engine.create_silence(frames)

    def _generate_mixer_mode(self, frames: int) -> np.ndarray:
        """Generate audio for Mixer mode (all decks mix together)"""
        audio_streams = []

        for deck in self.decks:
            if deck.is_playing:
                audio = self._get_deck_audio(deck, frames)
                if audio is not None:
                    audio_streams.append(audio)

        if audio_streams:
            return self.audio_engine.mix_audio(audio_streams)
        else:
            return self.audio_engine.create_silence(frames)

    def _generate_solo_mode(self, frames: int) -> np.ndarray:
        """Generate audio for Solo mode (only active deck plays)"""
        if 0 <= self.active_deck_index < len(self.decks):
            deck = self.decks[self.active_deck_index]
            if deck.is_playing:
                audio = self._get_deck_audio(deck, frames)
                if audio is not None:
                    return audio

        return self.audio_engine.create_silence(frames)

    def _generate_automatic_mode(self, frames: int) -> np.ndarray:
        """Generate audio for Automatic mode (solo with auto-switching and crossfade)"""
        # If crossfade is active, mix both decks with fading volumes
        if self._crossfade_active:
            return self._generate_crossfade_audio(frames)

        # Otherwise, same as solo mode
        return self._generate_solo_mode(frames)

    def _generate_crossfade_audio(self, frames: int) -> np.ndarray:
        """Generate audio during crossfade transition"""
        # Calculate fade progress for this frame block
        fade_start = self._crossfade_samples_done / self._crossfade_samples_total
        self._crossfade_samples_done += frames
        fade_end = min(1.0, self._crossfade_samples_done / self._crossfade_samples_total)

        # Get audio from both decks
        from_deck = self.decks[self._crossfade_from_deck] if 0 <= self._crossfade_from_deck < len(self.decks) else None
        to_deck = self.decks[self._crossfade_to_deck] if 0 <= self._crossfade_to_deck < len(self.decks) else None

        from_audio = None
        to_audio = None

        if from_deck and from_deck.is_playing:
            from_audio = self._get_deck_audio(from_deck, frames)
        if to_deck and to_deck.is_playing:
            to_audio = self._get_deck_audio(to_deck, frames)

        # Create output buffer
        output = self.audio_engine.create_silence(frames)

        # Apply crossfade with linear interpolation across the frame block
        fade_curve = np.linspace(fade_start, fade_end, frames).reshape(-1, 1)

        if from_audio is not None:
            # Fade out: volume goes from (1 - fade_start) to (1 - fade_end)
            from_volume = 1.0 - fade_curve
            output += from_audio * from_volume

        if to_audio is not None:
            # Fade in: volume goes from fade_start to fade_end
            to_volume = fade_curve
            output += to_audio * to_volume

        # Check if crossfade is complete
        if self._crossfade_samples_done >= self._crossfade_samples_total:
            self._finish_crossfade()

        # Apply soft clipping to prevent distortion
        output = np.tanh(output)

        return output.astype(np.float32)

    def _start_crossfade(self, from_deck_index: int, to_deck_index: int):
        """
        Start a crossfade transition between two decks.

        Args:
            from_deck_index: Index of deck to fade out
            to_deck_index: Index of deck to fade in
        """
        self._crossfade_from_deck = from_deck_index
        self._crossfade_to_deck = to_deck_index
        self._crossfade_samples_total = int(self.crossfade_duration * self.audio_engine.sample_rate)
        self._crossfade_samples_done = 0
        self._crossfade_active = True

    def _finish_crossfade(self):
        """Complete the crossfade transition"""
        self._crossfade_active = False
        # Update active deck to the target
        self.active_deck_index = self._crossfade_to_deck

        if self.on_active_deck_change:
            self.on_active_deck_change(self._crossfade_from_deck, self._crossfade_to_deck)

    def _get_deck_audio(self, deck: Deck, frames: int) -> Optional[np.ndarray]:
        """
        Get audio from a deck for the current frame.

        Args:
            deck: Deck instance
            frames: Number of frames needed

        Returns:
            Audio data or None
        """
        try:
            # Handle streaming audio
            if deck.is_stream and deck.stream_handler:
                # Get audio from stream handler
                chunk = deck.stream_handler.get_audio_data(frames)
                if chunk is None:
                    # No data available, return silence
                    return self.audio_engine.create_silence(frames)

                # Apply volume and balance
                left_vol, right_vol = deck.get_left_right_volumes()
                chunk = self.audio_engine.apply_volume_and_balance(chunk, left_vol, right_vol)
                return chunk

            # Check if audio is cached (do NOT load in audio callback to prevent underflows)
            if deck.deck_id not in self._loaded_audio_cache:
                # Audio not preloaded - return silence to prevent underflow
                # Audio should be loaded via ensure_deck_loaded() before playback
                return self.audio_engine.create_silence(frames)

            audio_data = self._loaded_audio_cache.get(deck.deck_id)
            if audio_data is None:
                return None

            # Get audio chunk at current position
            start = deck.position
            end = start + frames

            # Handle end of file
            if start >= len(audio_data):
                if deck.loop:
                    deck.position = 0
                    start = 0
                    end = frames
                else:
                    deck.stop()
                    if deck.on_playback_end:
                        deck.on_playback_end(deck.deck_id)
                    return None

            # Extract chunk
            if end > len(audio_data):
                if deck.loop:
                    # Loop back to beginning
                    chunk1 = audio_data[start:]
                    remaining = end - len(audio_data)
                    chunk2 = audio_data[:remaining]
                    chunk = np.vstack([chunk1, chunk2])
                    deck.position = remaining
                else:
                    # Pad with silence
                    chunk = audio_data[start:]
                    padding = np.zeros((end - len(audio_data), 2), dtype=np.float32)
                    chunk = np.vstack([chunk, padding])
                    deck.position = len(audio_data)
            else:
                chunk = audio_data[start:end]
                deck.position = end

            # Apply volume and balance
            left_vol, right_vol = deck.get_left_right_volumes()
            chunk = self.audio_engine.apply_volume_and_balance(chunk, left_vol, right_vol)

            return chunk

        except Exception as e:
            print(f"Error getting deck audio: {e}")
            return None

    def set_mode(self, mode: str):
        """
        Set operating mode.

        Args:
            mode: MODE_MIXER, MODE_SOLO, or MODE_AUTOMATIC
        """
        if mode == self.mode:
            return

        old_mode = self.mode
        self.mode = mode

        # Handle automatic mode
        if mode == MODE_AUTOMATIC:
            self._start_automatic_switching()
        else:
            self._stop_automatic_switching()

        if self.on_mode_change:
            self.on_mode_change(old_mode, mode)

    def set_active_deck(self, deck_index: int):
        """
        Set active deck for Solo/Automatic modes.

        Args:
            deck_index: Deck index (0-based)
        """
        if 0 <= deck_index < len(self.decks):
            old_index = self.active_deck_index
            self.active_deck_index = deck_index

            if old_index != deck_index and self.on_active_deck_change:
                self.on_active_deck_change(old_index, deck_index)

    def next_deck(self, use_crossfade: bool = None):
        """
        Switch to next deck (Solo/Automatic mode).

        Args:
            use_crossfade: Whether to use crossfade (None = auto based on mode and settings)
        """
        next_index = (self.active_deck_index + 1) % len(self.decks)

        # Determine if crossfade should be used
        if use_crossfade is None:
            use_crossfade = self.mode == MODE_AUTOMATIC and self.crossfade_enabled

        if use_crossfade and not self._crossfade_active:
            self._start_crossfade(self.active_deck_index, next_index)
        else:
            self.set_active_deck(next_index)

    def previous_deck(self, use_crossfade: bool = None):
        """
        Switch to previous deck (Solo/Automatic mode).

        Args:
            use_crossfade: Whether to use crossfade (None = auto based on mode and settings)
        """
        prev_index = (self.active_deck_index - 1) % len(self.decks)

        # Determine if crossfade should be used
        if use_crossfade is None:
            use_crossfade = self.mode == MODE_AUTOMATIC and self.crossfade_enabled

        if use_crossfade and not self._crossfade_active:
            self._start_crossfade(self.active_deck_index, prev_index)
        else:
            self.set_active_deck(prev_index)

    def set_master_volume(self, volume: float):
        """
        Set master volume.

        Args:
            volume: Volume level (0.0 to 1.0)
        """
        self.master_volume = max(0.0, min(1.0, volume))

    def get_deck(self, deck_index: int) -> Optional[Deck]:
        """
        Get deck by index.

        Args:
            deck_index: Deck index (0-based)

        Returns:
            Deck instance or None
        """
        if 0 <= deck_index < len(self.decks):
            return self.decks[deck_index]
        return None

    def get_deck_by_id(self, deck_id: int) -> Optional[Deck]:
        """
        Get deck by ID.

        Args:
            deck_id: Deck ID (1-based)

        Returns:
            Deck instance or None
        """
        return self.get_deck(deck_id - 1)

    def clear_deck_cache(self, deck_id: int):
        """Clear cached audio data for a deck"""
        if deck_id in self._loaded_audio_cache:
            del self._loaded_audio_cache[deck_id]

    def ensure_deck_loaded(self, deck: Deck) -> bool:
        """
        Ensure audio data is loaded for a deck before playback.
        Call this before play() to prevent underflows.

        Args:
            deck: Deck instance to preload

        Returns:
            True if audio is ready, False otherwise
        """
        if deck.is_stream:
            # Streams are handled differently, just check if handler exists
            return deck.stream_handler is not None

        if deck.deck_id in self._loaded_audio_cache:
            return True

        if deck.file_path:
            result = self.audio_engine.load_audio_file(deck.file_path)
            if result:
                audio_data, sample_rate, channels = result
                deck.audio_data = audio_data
                deck.sample_rate = sample_rate
                deck.channels = channels
                self._loaded_audio_cache[deck.deck_id] = audio_data
                return True

        return False

    def preload_all_decks(self):
        """Preload audio for all decks that have files loaded"""
        for deck in self.decks:
            if deck.file_path and not deck.is_stream:
                self.ensure_deck_loaded(deck)

    def play_all(self):
        """Start playback on all loaded decks"""
        for deck in self.decks:
            if deck.file_path:  # Only play decks that have content loaded
                self.ensure_deck_loaded(deck)  # Preload to prevent underflow
                deck.play()

    def pause_all(self):
        """Pause playback on all decks"""
        for deck in self.decks:
            if deck.is_playing:
                deck.pause()

    def stop_all(self):
        """Stop playback on all decks and reset positions"""
        for deck in self.decks:
            deck.stop()

    def toggle_play_pause_all(self):
        """
        Toggle play/pause for all decks.
        If any deck is playing, pause all. Otherwise, play all loaded decks.
        """
        any_playing = any(deck.is_playing for deck in self.decks)
        if any_playing:
            self.pause_all()
        else:
            self.play_all()

    def is_any_playing(self) -> bool:
        """Check if any deck is currently playing"""
        return any(deck.is_playing for deck in self.decks)

    def _start_automatic_switching(self):
        """Start automatic deck switching"""
        if self._auto_thread is None or not self._auto_thread.is_alive():
            self._auto_stop_event.clear()
            self._auto_thread = threading.Thread(target=self._automatic_switch_loop, daemon=True)
            self._auto_thread.start()

    def _stop_automatic_switching(self):
        """Stop automatic deck switching"""
        if self._auto_thread is not None:
            self._auto_stop_event.set()
            self._auto_thread.join(timeout=1.0)
            self._auto_thread = None

    def _automatic_switch_loop(self):
        """Automatic switching thread loop"""
        while not self._auto_stop_event.is_set():
            # Calculate wait time: if crossfade enabled, start it early so it completes on time
            wait_time = self.auto_switch_interval
            if self.crossfade_enabled:
                wait_time = max(0.5, self.auto_switch_interval - self.crossfade_duration)

            # Wait for the interval (check periodically to allow stopping)
            elapsed = 0.0
            while elapsed < wait_time and not self._auto_stop_event.is_set():
                sleep_chunk = min(0.5, wait_time - elapsed)
                time.sleep(sleep_chunk)
                elapsed += sleep_chunk

            if not self._auto_stop_event.is_set():
                self.next_deck()  # Will use crossfade automatically in automatic mode

    def to_dict(self) -> dict:
        """Export mixer configuration"""
        return {
            'mode': self.mode,
            'master_volume': self.master_volume,
            'auto_switch_interval': self.auto_switch_interval,
            'crossfade_enabled': self.crossfade_enabled,
            'crossfade_duration': self.crossfade_duration,
        }

    def from_dict(self, data: dict):
        """Load mixer configuration"""
        self.mode = data.get('mode', MODE_MIXER)
        self.master_volume = float(data.get('master_volume', 0.8))
        self.auto_switch_interval = int(data.get('auto_switch_interval', 10))
        self.crossfade_enabled = bool(data.get('crossfade_enabled', True))
        self.crossfade_duration = float(data.get('crossfade_duration', 2.0))

    def cleanup(self):
        """Cleanup resources"""
        self._stop_automatic_switching()
        self.audio_engine.stop_stream()
        self._loaded_audio_cache.clear()

    def __del__(self):
        """Cleanup on deletion"""
        self.cleanup()
