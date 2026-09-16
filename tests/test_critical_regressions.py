import configparser
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np
import soundfile as sf


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from audio.audio_engine import AudioEngine
from audio.deck import Deck
from audio.mixer import Mixer
from audio.recorder import Recorder
from config.config_manager import ConfigManager, ProjectManager
from config.defaults import DEFAULT_CONFIG


class CriticalRegressionTests(unittest.TestCase):
    def test_remember_last_project_is_disabled_by_default(self):
        self.assertFalse(DEFAULT_CONFIG["General"]["remember_last_project"])
        self.assertEqual(DEFAULT_CONFIG["General"]["last_project_file"], "")

    def test_project_path_is_only_remembered_when_enabled(self):
        manager = ConfigManager.__new__(ConfigManager)
        manager.config = configparser.ConfigParser()
        manager.config.add_section("General")
        manager.config.set("General", "remember_last_project", "False")
        manager.save = mock.Mock()

        project_path = Path("remember-me.mdap")
        self.assertFalse(manager.remember_project_file(str(project_path)))
        self.assertEqual(manager.get_last_project_file(), "")
        manager.save.assert_not_called()

        manager.set("General", "remember_last_project", True)
        self.assertTrue(manager.remember_project_file(str(project_path)))
        self.assertEqual(
            manager.get_last_project_file(),
            str(project_path.resolve()),
        )
        manager.save.assert_called_once_with()

    def test_replacing_input_with_file_clears_old_source_state(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            audio_path = Path(directory) / "replacement.wav"
            audio_path.touch()
            stopped = []
            handler = SimpleNamespace(stop=lambda: stopped.append(True))
            deck = Deck(1)
            deck.stream_handler = handler
            deck.is_stream = True
            deck.is_soundcard_input = True
            deck.soundcard_device_id = 7
            deck.soundcard_device_name = "old input"

            self.assertTrue(deck.load_file(str(audio_path)))
            self.assertEqual(stopped, [True])
            self.assertIsNone(deck.stream_handler)
            self.assertFalse(deck.is_stream)
            self.assertFalse(deck.is_soundcard_input)
            self.assertNotIn("source_type", deck.to_dict())
            self.assertEqual(deck.to_dict()["file"], str(audio_path))

    def test_stale_async_audio_result_is_rejected(self):
        mixer = SimpleNamespace(
            _loaded_audio_cache={},
            _loaded_audio_cache_generations={},
        )
        deck = Deck(1)

        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            first_path = Path(directory) / "first.wav"
            second_path = Path(directory) / "second.wav"
            first_path.touch()
            second_path.touch()
            deck.load_file(str(first_path))
            stale_generation = deck.source_generation
            deck.load_file(str(second_path))
            result = (np.zeros((8, 2), dtype=np.float32), 48000, 2)

            accepted = Mixer.cache_deck_audio_if_current(
                mixer,
                deck, stale_generation, str(first_path), result
            )
            self.assertFalse(accepted)
            self.assertNotIn(deck.deck_id, mixer._loaded_audio_cache)

            accepted = Mixer.cache_deck_audio_if_current(
                mixer,
                deck, deck.source_generation, str(second_path), result
            )
            self.assertTrue(accepted)
            self.assertIs(mixer._loaded_audio_cache[deck.deck_id], result[0])

    def test_failed_project_save_preserves_existing_file(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            project_path = Path(directory) / "project.mdap"
            project_path.write_text("original project", encoding="utf-8")

            with mock.patch.object(
                configparser.ConfigParser,
                "write",
                side_effect=OSError("simulated write failure"),
            ):
                with self.assertRaisesRegex(Exception, "simulated write failure"):
                    ProjectManager.save_project(str(project_path), {"decks": []})

            self.assertEqual(
                project_path.read_text(encoding="utf-8"),
                "original project",
            )
            self.assertEqual(list(Path(directory).glob("*.tmp")), [])

    def test_24_bit_wav_has_correct_frame_count(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            output_path = Path(directory) / "recording.wav"
            recorder = Recorder(
                sample_rate=48000,
                channels=2,
                bit_depth=24,
                format="wav",
                pre_roll_seconds=0,
            )
            self.assertTrue(recorder.start_recording(output_file=str(output_path)))
            recorder.write_frames(np.full((10, 2), 0.5, dtype=np.float32))
            self.assertTrue(recorder.stop_recording())

            with wave.open(str(output_path), "rb") as recording:
                self.assertEqual(recording.getsampwidth(), 3)
                self.assertEqual(recording.getnchannels(), 2)
                self.assertEqual(recording.getnframes(), 10)

    def test_multichannel_file_is_downmixed_to_stereo(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            audio_path = Path(directory) / "surround.wav"
            source = np.zeros((32, 6), dtype=np.float32)
            source[:, 2] = 0.5  # centre channel must reach both outputs
            sf.write(str(audio_path), source, 48000, subtype="FLOAT")

            engine = AudioEngine(buffer_size=16, sample_rate=48000, device="null")
            data, sample_rate, channels = engine.load_audio_file(str(audio_path))

            self.assertEqual(sample_rate, 48000)
            self.assertEqual(channels, 2)
            self.assertEqual(data.shape, (32, 2))
            self.assertTrue(np.all(data[:, 0] > 0))
            np.testing.assert_allclose(data[:, 0], data[:, 1])


if __name__ == "__main__":
    unittest.main()
