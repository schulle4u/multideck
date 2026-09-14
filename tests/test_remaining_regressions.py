import queue
import sys
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from audio.deck import Deck
from audio.effects import EffectChain
from audio.icecast_streamer import IcecastStreamer
from audio.recorder import Recorder
from gui.main_frame import MainFrame


class RemainingRegressionTests(unittest.TestCase):
    def test_effect_chain_notifies_only_for_persistent_changes(self):
        chain = EffectChain(48000)
        changes = []
        chain.on_change = changes.append

        chain.set_enabled(True)
        chain.set_enabled(True)
        chain.enable_effect("reverb", True)
        chain.set_reverb_param(room_size=0.75)

        self.assertEqual(changes, [chain, chain, chain])

        changes.clear()
        chain.from_dict({})
        self.assertEqual(changes, [])

    def test_vst_mutations_emit_effect_chain_changes(self):
        chain = EffectChain(48000)
        chain._rebuild_board = lambda: None
        first_plugin = SimpleNamespace(amount=0.25)
        second_plugin = SimpleNamespace(amount=0.5)
        chain.vst_slots = [
            {"plugin": first_plugin, "enabled": True, "name": "first"},
            {"plugin": second_plugin, "enabled": True, "name": "second"},
        ]
        changes = []
        chain.on_change = changes.append

        chain.enable_vst(0, False)
        chain.set_vst_param(0, "amount", 0.75)
        chain.move_vst(0, 1)
        chain.remove_vst(0)

        self.assertEqual(changes, [chain, chain, chain, chain])

    def test_menu_and_shortcut_mute_loop_changes_mark_project_dirty(self):
        deck = Deck(1)
        dirty_events = []
        frame = SimpleNamespace(
            _get_selected_deck=lambda: deck,
            _update_active_deck_controls=lambda: None,
            _update_deck_panel=lambda _deck_id: None,
            _mark_project_modified=lambda: dirty_events.append(True),
            mixer=SimpleNamespace(
                active_deck_index=0,
                get_deck=lambda _index: deck,
            ),
            tts_manager=SimpleNamespace(speak=lambda _message: None),
        )

        MainFrame._on_active_toggle_mute(frame)
        MainFrame._on_active_toggle_loop(frame)
        MainFrame._on_mute_active_deck(frame, None)
        MainFrame._on_loop_active_deck(frame, None)

        self.assertEqual(len(dirty_events), 4)

    def test_pre_roll_buffer_uses_recorder_lock(self):
        recorder = Recorder(sample_rate=10, pre_roll_seconds=1)
        finished = threading.Event()
        block = np.zeros((2, 2), dtype=np.float32)

        recorder._lock.acquire()
        try:
            worker = threading.Thread(
                target=lambda: (recorder.buffer_frames(block), finished.set())
            )
            worker.start()
            self.assertFalse(finished.wait(0.05))
        finally:
            recorder._lock.release()

        worker.join(timeout=1.0)
        self.assertTrue(finished.is_set())
        self.assertEqual(recorder._pre_roll_frames_count, 2)

    def test_livestream_audio_submission_never_waits_for_control_lock(self):
        streamer = IcecastStreamer(config={})
        streamer.is_streaming = True
        streamer._audio_queue = queue.Queue(maxsize=4)
        submitted = threading.Event()
        block = np.zeros((8, 2), dtype=np.float32)

        streamer._lock.acquire()
        try:
            worker = threading.Thread(
                target=lambda: (streamer.write_frames(block), submitted.set())
            )
            worker.start()
            self.assertTrue(submitted.wait(0.2))
        finally:
            streamer._lock.release()

        worker.join(timeout=1.0)
        self.assertFalse(streamer._audio_queue.empty())


if __name__ == "__main__":
    unittest.main()
