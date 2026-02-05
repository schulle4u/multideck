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
    APP_NAME, APP_VERSION, MODE_MIXER, MODE_SOLO, MODE_AUTOMATIC
)
from audio.audio_engine import AudioEngine
from audio.mixer import Mixer
from utils.logger import configure_logging, get_logger


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

            # Load deck configurations
            decks_data = project_data.get('decks', [])
            loaded_count = 0

            for i, deck_data in enumerate(decks_data):
                if i >= len(self.mixer.decks):
                    break

                deck = self.mixer.decks[i]

                if deck_data and 'file' in deck_data and deck_data['file']:
                    # Apply deck settings
                    if 'name' in deck_data:
                        deck.name = deck_data['name']
                    if 'volume' in deck_data:
                        deck.volume = float(deck_data['volume'])
                    if 'balance' in deck_data:
                        deck.balance = float(deck_data['balance'])
                    if 'mute' in deck_data:
                        deck.mute = deck_data['mute'] if isinstance(deck_data['mute'], bool) else deck_data['mute'].lower() == 'true'
                    if 'loop' in deck_data:
                        deck.loop = deck_data['loop'] if isinstance(deck_data['loop'], bool) else deck_data['loop'].lower() == 'true'

                    # Load audio file
                    file_path = deck_data['file']
                    if deck.load_file(file_path):
                        # Preload audio data
                        if self.mixer.ensure_deck_loaded(deck):
                            loaded_count += 1
                            self.log(f"  Deck {i + 1} ({deck.name}): {Path(file_path).name if not file_path.startswith('http') else file_path}")
                        else:
                            self.logger.warning(f"Failed to preload Deck {i + 1}: {file_path}")
                    else:
                        self.logger.warning(f"Failed to load Deck {i + 1}: {file_path}")

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
            MODE_AUTOMATIC: "Automatic"
        }

        print("\n" + "=" * 50)
        print(f"{APP_NAME} v{APP_VERSION} - CLI Mode")
        print("=" * 50)
        print(f"Project: {Path(self.project_file).name}")
        print(f"Mode: {mode_names.get(self.mixer.mode, self.mixer.mode)}")
        print(f"Master Volume: {int(self.mixer.master_volume * 100)}%")

        if self.mixer.mode == MODE_AUTOMATIC:
            print(f"Auto-switch interval: {self.mixer.auto_switch_interval}s")
            print(f"Crossfade: {'On' if self.mixer.crossfade_enabled else 'Off'} ({self.mixer.crossfade_duration}s)")

        print("-" * 50)
        print("Decks:")

        for i, deck in enumerate(self.mixer.decks):
            if deck.file_path:
                status = "Playing" if deck.is_playing else "Paused" if deck.is_paused else "Loaded"
                mute_str = " [MUTE]" if deck.mute else ""
                loop_str = " [LOOP]" if deck.loop else ""
                volume_str = f"{int(deck.volume * 100)}%"

                if deck.is_stream:
                    source = deck.file_path
                else:
                    source = Path(deck.file_path).name

                active_marker = "* " if self.mixer.mode in [MODE_SOLO, MODE_AUTOMATIC] and i == self.mixer.active_deck_index else "  "

                print(f"  {i + 1} ({deck.name}): {active_marker}[{status}] {source} - Vol: {volume_str}{mute_str}{loop_str}")

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

        # Initialize mixer
        num_decks = config.get_deck_count()
        self.mixer = Mixer(self.audio_engine, num_decks=num_decks)

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
                self.mixer.set_active_deck(deck_index)
            else:
                print(f"Error: Deck {self.initial_deck} does not exist (1-{len(self.mixer.decks)}).", file=sys.stderr)
                self.cleanup()
                return 1

        # Set up signal handlers
        self.setup_signal_handlers()

        # Start playback
        self.mixer.play_all()
        self.running = True

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
