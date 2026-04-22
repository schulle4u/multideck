#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MultiDeck Audio Player - Command Line Interface

Headless mode for running MultiDeck with a project file.
Designed for server environments, Raspberry Pi, or script integration.
"""

import sys
import os
import signal
import time
import argparse
from pathlib import Path

# Add src directory to Python path
src_dir = Path(__file__).parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from config.config_manager import ConfigManager, ProjectManager
from config.defaults import (
    APP_NAME, APP_VERSION, MODE_MIXER, MODE_SOLO, MODE_AUTOMATIC, MODE_MULTIROOM,
    SOURCE_TYPE_SOUNDCARD_INPUT
)
from audio.audio_engine import AudioEngine
from audio.icecast_streamer import IcecastStreamer
from audio.mixer import Mixer
from utils.logger import configure_logging, get_logger
from utils.tts_manager import TTSManager


class MultiDeckCLI:
    """Command-line interface for MultiDeck Audio Player"""

    def __init__(self, project_file: str, silent: bool = False, deck: int = None):
        """
        Initialize CLI.

        Args:
            project_file: Path to .mdap project file
            silent: If True, suppress status output
            deck: Deck number to select in solo mode (1-based)
        """
        self.project_file = project_file
        self.silent = silent
        self.initial_deck = deck
        self.running = False
        self.mixer = None
        self.audio_engine = None
        self.tts_manager = None
        self.streamer = None
        self.config_manager = None
        self.logger = get_logger('cli')

    def log(self, message: str):
        """Print message if not in silent mode"""
        if not self.silent:
            print(message)

    def setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown"""
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.log("\nShutdown signal received...")
        self.running = False

    def _on_deck_change(self, from_index: int, to_index: int):
        """Callback when active deck changes"""
        if self.silent:
            return

        to_deck = self.mixer.decks[to_index]
        if to_deck.file_path:
            print(f"-> Deck {to_index + 1} ({to_deck.name})")

    def _on_streaming_started(self, stream_url: str):
        """Log livestream start events."""
        message = "Livestream started"
        if stream_url:
            message = f"{message}: {stream_url}"
        self.log(message)
        self.logger.info(message)

    def _on_streaming_stopped(self, stream_url: str, frames: int):
        """Log livestream stop events."""
        message = "Livestream stopped"
        self.log(message)
        self.logger.info(message)

    def _on_streaming_error(self, message: str):
        """Log livestream errors."""
        self.logger.error(message)
        if not self.silent:
            print(f"[livestream] {message}", file=sys.stderr)

    def _get_streaming_config(self) -> dict:
        """Build livestream config dict from current settings."""
        config = self.config_manager
        return {
            'server': config.get('Streaming', 'server', ''),
            'port': config.getint('Streaming', 'port', 8000),
            'mountpoint': config.get('Streaming', 'mountpoint', '/stream'),
            'credentials': config.get('Streaming', 'credentials', ''),
            'codec': config.get('Streaming', 'codec', 'mp3'),
            'bitrate': config.getint('Streaming', 'bitrate', 192),
            'name': config.get('Streaming', 'name', 'MultiDeck Live'),
            'description': config.get('Streaming', 'description', ''),
            'genre': config.get('Streaming', 'genre', ''),
            'url': config.get('Streaming', 'url', ''),
            'public': config.getboolean('Streaming', 'public', False),
            'auto_reconnect': config.getboolean('Streaming', 'auto_reconnect', True),
            'reconnect_wait': config.getint('Streaming', 'reconnect_wait', 5),
            'queue_blocks': config.getint('Streaming', 'queue_blocks', 64),
            'writer_poll_ms': config.getint('Streaming', 'writer_poll_ms', 100),
            'ffmpeg_close_timeout': config.getfloat('Streaming', 'ffmpeg_close_timeout', 5.0),
            'ffmpeg_loglevel': config.get('Streaming', 'ffmpeg_loglevel', 'error'),
        }

    def load_project(self) -> bool:
        """
        Load project file and configure mixer.

        Returns:
            True if loaded successfully
        """
        try:
            project_data = ProjectManager.load_project(self.project_file)
            self.log(f"Loading project: {self.project_file}")

            # Parse mixer settings (apply mode AFTER loading decks)
            mixer_data = project_data.get('mixer', {})
            target_mode = mixer_data.get('mode', MODE_MIXER)

            # Apply mixer settings (except mode)
            if 'master_volume' in mixer_data:
                self.mixer.master_volume = float(mixer_data['master_volume'])

            if 'auto_switch_interval' in mixer_data:
                self.mixer.auto_switch_interval = int(mixer_data['auto_switch_interval'])

            if 'crossfade_enabled' in mixer_data:
                self.mixer.crossfade_enabled = mixer_data['crossfade_enabled'].lower() == 'true'

            if 'crossfade_duration' in mixer_data:
                self.mixer.crossfade_duration = float(mixer_data['crossfade_duration'])

            if 'level_switch_enabled' in mixer_data:
                self.mixer.level_switch_enabled = mixer_data['level_switch_enabled'].lower() == 'true' if isinstance(mixer_data['level_switch_enabled'], str) else bool(mixer_data['level_switch_enabled'])

            if 'level_threshold_db' in mixer_data:
                self.mixer.level_threshold_db = float(mixer_data['level_threshold_db'])

            if 'level_hysteresis_db' in mixer_data:
                self.mixer.level_hysteresis_db = float(mixer_data['level_hysteresis_db'])

            if 'level_hold_time' in mixer_data:
                self.mixer.level_hold_time = float(mixer_data['level_hold_time'])

            # Load deck configurations
            decks_data = project_data.get('decks', [])
            loaded_count = 0

            for i, deck_data in enumerate(decks_data):
                if i >= len(self.mixer.decks):
                    break

                deck = self.mixer.decks[i]
                if not deck_data:
                    continue

                if not deck.from_dict(deck_data):
                    if deck_data.get('source_type') == SOURCE_TYPE_SOUNDCARD_INPUT:
                        self.logger.warning(f"Failed to open soundcard input for Deck {i + 1}")
                    elif deck_data.get('file'):
                        self.logger.warning(f"Failed to load Deck {i + 1}: {deck_data.get('file')}")
                    continue

                if deck.file_path or deck.is_soundcard_input:
                    if self.mixer.ensure_deck_loaded(deck):
                        loaded_count += 1
                        if deck.is_soundcard_input:
                            source_label = f"[Input] {deck.soundcard_device_name}"
                        elif deck.is_stream:
                            source_label = deck.file_path
                        else:
                            source_label = Path(deck.file_path).name

                        intro_label = f" | Intro: {Path(deck.intro_file).name}" if deck.intro_file else ""
                        self.log(f"  Deck {i + 1} ({deck.name}): {source_label}{intro_label}")
                    else:
                        source_label = deck.soundcard_device_name if deck.is_soundcard_input else (deck.file_path or "")
                        self.logger.warning(f"Failed to preload Deck {i + 1}: {source_label}")
                elif deck.intro_file:
                    self.log(f"  Deck {i + 1} ({deck.name}): Intro {Path(deck.intro_file).name}")

            self.log(f"Loaded {loaded_count} deck(s)")

            # Load effects settings
            if 'master_effects' in project_data and project_data['master_effects']:
                self.mixer.load_master_effects_dict(project_data['master_effects'])
                if str(project_data['master_effects'].get('enabled', '')).lower() == 'true':
                    self.log("  Master effects enabled")

            deck_effects = project_data.get('deck_effects', [])
            effects_enabled = []
            for i, fx_data in enumerate(deck_effects):
                if i < len(self.mixer.decks) and fx_data:
                    self.mixer.decks[i].load_effects_dict(fx_data)
                    if str(fx_data.get('enabled', '')).lower() == 'true':
                        effects_enabled.append(i + 1)

            if effects_enabled:
                deck_list = ', '.join(str(d) for d in effects_enabled)
                self.log(f"  Deck effects enabled for deck(s): {deck_list}")

            # Now apply mode using set_mode() to start auto-switch thread if needed
            if target_mode != MODE_MIXER:
                self.mixer.set_mode(target_mode)

            return loaded_count > 0

        except Exception as e:
            self.logger.error(f"Failed to load project: {e}")
            print(f"Error: Failed to load project: {e}", file=sys.stderr)
            return False

    def print_status(self):
        """Print current status"""
        mode_names = {
            MODE_MIXER: "Mixer",
            MODE_SOLO: "Solo",
            MODE_AUTOMATIC: "Automatic",
            MODE_MULTIROOM: "Multiroom",
        }

        print("\n" + "=" * 50)
        print(f"{APP_NAME} v{APP_VERSION} - CLI Mode")
        print("=" * 50)
        print(f"Project: {Path(self.project_file).name}")
        print(f"Mode: {mode_names.get(self.mixer.mode, self.mixer.mode)}")
        print(f"Master Volume: {int(self.mixer.master_volume * 100)}%")
        if self.streamer:
            print(f"Livestream: {'On' if self.streamer.is_streaming else 'Off'}")

        if self.mixer.mode == MODE_AUTOMATIC:
            print(f"Auto-switch interval: {self.mixer.auto_switch_interval}s")
            print(f"Crossfade: {'On' if self.mixer.crossfade_enabled else 'Off'} ({self.mixer.crossfade_duration}s)")
            if self.mixer.level_switch_enabled:
                print(f"Level-based switching: On (threshold: {self.mixer.level_threshold_db} dB, "
                      f"hysteresis: {self.mixer.level_hysteresis_db} dB, hold: {self.mixer.level_hold_time}s)")
            else:
                print(f"Level-based switching: Off")

        print("-" * 50)
        print("Decks:")

        for i, deck in enumerate(self.mixer.decks):
            if deck.file_path:
                status = "Playing" if deck.is_playing else "Paused" if deck.is_paused else "Loaded"
                mute_str = " [MUTE]" if deck.mute else ""
                loop_str = " [LOOP]" if deck.loop else ""
                volume_str = f"{int(deck.volume * 100)}%"

                if deck.is_soundcard_input:
                    source = f"[Input] {deck.soundcard_device_name}"
                elif deck.is_stream:
                    source = deck.file_path
                else:
                    source = Path(deck.file_path).name

                active_marker = "* " if self.mixer.mode in [MODE_SOLO, MODE_AUTOMATIC] and i == self.mixer.active_deck_index else "  "
                intro_str = f" | Intro: {Path(deck.intro_file).name}" if deck.intro_file else ""

                print(f"  {i + 1} ({deck.name}): {active_marker}[{status}] {source} - Vol: {volume_str}{mute_str}{loop_str}{intro_str}")

        print("-" * 50)
        print("Press Ctrl+C to stop")
        print("=" * 50)

    def run(self) -> int:
        """
        Run the CLI.

        Returns:
            Exit code (0 = success, 1 = error)
        """
        # Validate project file
        project_path = Path(self.project_file)
        if not project_path.exists():
            print(f"Error: Project file not found: {self.project_file}", file=sys.stderr)
            return 1

        if project_path.suffix.lower() != '.mdap':
            print(f"Error: Invalid file format. Expected .mdap file.", file=sys.stderr)
            return 1

        # Load application configuration
        config = ConfigManager()
        self.config_manager = config

        # Initialize audio engine
        buffer_size = config.getint('Audio', 'buffer_size', 2048)
        sample_rate = config.getint('Audio', 'sample_rate', 48000)
        device = config.get('Audio', 'output_device', 'default')

        try:
            self.audio_engine = AudioEngine(
                buffer_size=buffer_size,
                sample_rate=sample_rate,
                device=device if device != 'default' else None
            )
        except Exception as e:
            print(f"Error: Failed to initialize audio engine: {e}", file=sys.stderr)
            return 1

        self.streamer = IcecastStreamer(sample_rate=sample_rate, channels=2, config=self._get_streaming_config())
        self.streamer.on_streaming_started = self._on_streaming_started
        self.streamer.on_streaming_stopped = self._on_streaming_stopped
        self.streamer.on_error = self._on_streaming_error

        # Initialize mixer
        num_decks = config.get_deck_count()
        self.mixer = Mixer(self.audio_engine, num_decks=num_decks, streamer=self.streamer)

        # Apply automation settings from config (project file may override these)
        self.mixer.auto_switch_interval = config.getint('Automation', 'switch_interval', 10)
        self.mixer.crossfade_enabled = config.getboolean('Automation', 'crossfade_enabled', True)
        self.mixer.crossfade_duration = config.getfloat('Automation', 'crossfade_duration', 2.0)
        self.mixer.level_switch_enabled = config.getboolean('Automation', 'level_switch_enabled', False)
        self.mixer.level_threshold_db = config.getfloat('Automation', 'level_threshold_db', -30.0)
        self.mixer.level_hysteresis_db = config.getfloat('Automation', 'level_hysteresis_db', 3.0)
        self.mixer.level_hold_time = config.getfloat('Automation', 'level_hold_time', 3.0)

        # Apply TTS settings from config
        self.tts_manager = TTSManager()
        self.tts_manager.tts_enabled = config.getboolean('TTS', 'tts_enabled', False)
        self.tts_manager.configure(
            engine_name=config.get('TTS', 'tts_engine', ''),
            voice_name=config.get('TTS', 'tts_voice', ''),
            rate=config.getint('TTS', 'tts_rate', 0),
            volume=config.getint('TTS', 'tts_volume', -1),
        )
        self.mixer.tts_manager = self.tts_manager

        # Set up deck change callback
        self.mixer.on_active_deck_change = self._on_deck_change

        # Load project
        if not self.load_project():
            print("Error: No decks were loaded from the project.", file=sys.stderr)
            self.cleanup()
            return 1

        # Apply --deck selection for solo mode
        if self.initial_deck is not None:
            deck_index = self.initial_deck - 1
            if 0 <= deck_index < len(self.mixer.decks):
                if self.mixer.mode not in [MODE_SOLO, MODE_AUTOMATIC]:
                    self.mixer.set_mode(MODE_SOLO)
                    self.log(f"Mode set to Solo (--deck specified)")
                self.mixer.set_active_deck(deck_index, trigger_switch_event=True)
            else:
                print(f"Error: Deck {self.initial_deck} does not exist (1-{len(self.mixer.decks)}).", file=sys.stderr)
                self.cleanup()
                return 1

        # Set up signal handlers
        self.setup_signal_handlers()

        # Start playback
        self.mixer.play_all()
        self.running = True

        if config.getboolean('Streaming', 'connect_at_startup', False):
            self.streamer.start_streaming()

        # Print initial status
        if not self.silent:
            self.print_status()

        self.logger.info(f"Playback started: {self.project_file}")

        # Main loop
        try:
            while self.running:
                time.sleep(0.5)

                # Check if any deck is still playing (for non-looping content)
                if not self.mixer.is_any_playing():
                    # Check if all decks have finished
                    all_finished = True
                    for deck in self.mixer.decks:
                        if deck.file_path and (deck.loop or deck.is_stream):
                            all_finished = False
                            break

                    if all_finished:
                        self.log("\nPlayback finished.")
                        break

        except KeyboardInterrupt:
            pass

        # Cleanup
        self.cleanup()
        self.log("Stopped.")
        self.logger.info("Playback stopped")

        return 0

    def cleanup(self):
        """Clean up resources"""
        if self.tts_manager:
            self.tts_manager.shutdown()
        if self.mixer:
            self.mixer.cleanup()
        if self.audio_engine:
            self.audio_engine.stop_stream()


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description=f"{APP_NAME} - Command Line Interface",
        prog="multideck-cli",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py project.mdap            Start playback with status display
  python cli.py -s project.mdap         Start playback in silent mode
  python cli.py -d 3 project.mdap       Play only deck 3 (solo mode)
  python cli.py -d 2 -s project.mdap    Play deck 2 silently

The CLI loads a .mdap project file and starts playback immediately.
Press Ctrl+C to stop playback.
"""
    )

    parser.add_argument(
        'project',
        help='Path to a .mdap project file'
    )

    parser.add_argument(
        '-s', '--silent',
        action='store_true',
        help='Silent mode - suppress status output (useful for scripts)'
    )

    parser.add_argument(
        '-d', '--deck',
        type=int,
        metavar='N',
        help='Select deck N for solo mode playback (1-10)'
    )

    parser.add_argument(
        '-v', '--version',
        action='version',
        version=f'{APP_NAME} v{APP_VERSION}'
    )

    return parser.parse_args()


def main():
    """Main entry point"""
    args = parse_arguments()

    # Configure logging for CLI mode
    config = ConfigManager()
    log_level = config.get('Logging', 'level', 'INFO')
    file_logging = config.getboolean('Logging', 'file_logging', True)
    # Enable console logging only if not in silent mode
    console_logging = not args.silent and config.getboolean('Logging', 'console_logging', False)

    configure_logging(
        level=log_level,
        file_logging=file_logging,
        console_logging=console_logging
    )

    # Create and run CLI
    cli = MultiDeckCLI(
        project_file=args.project,
        silent=args.silent,
        deck=args.deck
    )

    return cli.run()


if __name__ == '__main__':
    sys.exit(main())
