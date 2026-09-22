import queue
import sys
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np
import wx


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from audio.deck import Deck
from audio.effects import EffectChain
from audio.icecast_streamer import IcecastStreamer
from audio.mixer import Mixer
from audio.recorder import Recorder
from gui.main_frame import MainFrame


class RemainingRegressionTests(unittest.TestCase):
    @staticmethod
    def _make_mixer(deck_count=3):
        running = {"value": False}
        engine = SimpleNamespace(
            sample_rate=48000,
            buffer_size=512,
            device=None,
            start_stream=lambda callback: running.update(value=True),
            stop_stream=lambda: running.update(value=False),
            is_running=lambda: running["value"],
            is_null_output_device=lambda: False,
        )
        return Mixer(engine, num_decks=deck_count)

    def test_dynamic_decks_keep_identity_when_inserted_and_moved(self):
        mixer = self._make_mixer()
        original = mixer.decks[1]
        original.name = "Original"
        original_effects = original.effects

        inserted = mixer.create_deck(1)
        self.assertIs(mixer.decks[1], inserted)
        self.assertIs(mixer.get_deck_by_id(original.deck_id), original)

        self.assertTrue(mixer.move_deck(original.deck_id, 0))
        self.assertIs(mixer.decks[0], original)
        self.assertIs(original.effects, original_effects)

    def test_removing_active_deck_selects_a_neighbor_and_clears_cache(self):
        mixer = self._make_mixer()
        removed = mixer.decks[1]
        mixer.active_deck_index = 1
        mixer._loaded_audio_cache[removed.deck_id] = object()
        mixer._loaded_audio_cache_generations[removed.deck_id] = 1

        self.assertIs(mixer.remove_deck(removed.deck_id), removed)
        self.assertNotIn(removed, mixer.decks)
        self.assertEqual(mixer.active_deck_index, 1)
        self.assertNotIn(removed.deck_id, mixer._loaded_audio_cache)

    def test_empty_deck_serializes_its_persistent_settings(self):
        deck = Deck(7)
        deck.set_name("Speech")
        deck.set_volume(0.5)
        data = deck.to_dict()
        self.assertEqual(data["name"], "Speech")
        self.assertEqual(data["volume"], 0.5)

    def test_empty_dynamic_deck_list_is_safe(self):
        mixer = self._make_mixer(deck_count=0)
        self.assertFalse(mixer.next_deck())
        self.assertFalse(mixer.previous_deck())
        deck = mixer.create_deck()
        self.assertEqual(deck.name, "Deck 1")
        self.assertEqual(mixer.index_of_deck(deck.deck_id), 0)

    def test_programmatic_list_selection_does_not_change_active_deck(self):
        mixer = self._make_mixer()
        mixer.active_deck_index = 1
        frame = SimpleNamespace(
            _updating_deck_listbox=True,
            mixer=mixer,
            deck_listbox=SimpleNamespace(
                GetSelectedRow=lambda: (_ for _ in ()).throw(
                    AssertionError("selection must be ignored during a rebuild")
                )
            ),
        )

        MainFrame._on_deck_listbox_select(frame, None)
        self.assertEqual(mixer.active_deck_index, 1)

    def test_ctrl_space_toggles_selection_without_reaching_checkbox(self):
        actions = []
        deck_listbox = SimpleNamespace(
            GetFocusedRow=lambda: 1,
            IsSelected=lambda row: True,
            ClearSelection=lambda: actions.append(("clear", None)),
            SelectRow=lambda row: actions.append(("select", row)),
        )
        event = SimpleNamespace(
            GetKeyCode=lambda: wx.WXK_SPACE,
            ControlDown=lambda: True,
            AltDown=lambda: False,
            ShiftDown=lambda: False,
            Skip=lambda: actions.append(("skip", None)),
        )
        frame = SimpleNamespace(deck_listbox=deck_listbox)

        MainFrame._on_deck_listbox_key(frame, event)

        self.assertEqual(actions, [("clear", None)])

        actions.clear()
        deck_listbox.IsSelected = lambda row: False
        MainFrame._on_deck_listbox_key(frame, event)

        self.assertEqual(actions, [("select", 1)])

    def test_space_does_not_toggle_checkbox_for_unselected_focused_row(self):
        actions = []
        deck_listbox = SimpleNamespace(
            GetFocusedRow=lambda: 1,
            IsSelected=lambda row: False,
        )
        event = SimpleNamespace(
            GetKeyCode=lambda: wx.WXK_SPACE,
            ControlDown=lambda: False,
            AltDown=lambda: False,
            ShiftDown=lambda: False,
            Skip=lambda: actions.append("skip"),
        )
        frame = SimpleNamespace(deck_listbox=deck_listbox)

        MainFrame._on_deck_listbox_key(frame, event)
        self.assertEqual(actions, [])

        deck_listbox.IsSelected = lambda row: True
        MainFrame._on_deck_listbox_key(frame, event)
        self.assertEqual(actions, ["skip"])

    def test_move_handler_refreshes_selection_by_stable_deck_id(self):
        mixer = self._make_mixer()
        selected = mixer.decks[1]
        refreshed = []
        synced = []
        dirty = []
        frame = SimpleNamespace(
            mixer=mixer,
            _get_selected_deck=lambda: selected,
            _update_deck_listbox=lambda selected_deck_id=None: refreshed.append(selected_deck_id),
            _sync_listbox_selection=synced.append,
            _mark_project_modified=lambda: dirty.append(True),
        )

        MainFrame._on_move_selected_deck(frame, -1)

        self.assertIs(mixer.decks[0], selected)
        self.assertEqual(refreshed, [selected.deck_id])
        self.assertEqual(synced, [0])
        self.assertEqual(dirty, [True])

    def test_delayed_active_deck_ui_update_uses_stable_identity(self):
        mixer = self._make_mixer()
        target = mixer.decks[1]
        queued = []
        synced = []
        frame = SimpleNamespace(
            mixer=mixer,
            _update_active_deck_ui=lambda deck_id: MainFrame._update_active_deck_ui(frame, deck_id),
            _sync_listbox_selection=synced.append,
            SetStatusText=lambda message, field: None,
        )

        with mock.patch("gui.main_frame.wx.CallAfter", side_effect=lambda func, *args: queued.append((func, args))):
            MainFrame._on_active_deck_changed(frame, 0, 1)

        mixer.move_deck(target.deck_id, 0)
        func, args = queued.pop()
        func(*args)
        self.assertEqual(synced, [0])

    def test_open_project_remembers_only_after_successful_load(self):
        events = []
        config_manager = SimpleNamespace(
            remember_project_file=lambda path: events.append(("remember", path))
        )
        frame = SimpleNamespace(
            config_manager=config_manager,
            _reset_to_defaults=lambda: events.append(("reset", None)),
            _load_project_data=lambda data: events.append(("load", data)),
            _clear_project_modified=lambda: events.append(("clear", None)),
            SetStatusText=lambda message, field: None,
        )
        project_data = {"decks": []}

        with mock.patch(
            "gui.main_frame.ProjectManager.load_project",
            return_value=project_data,
        ):
            MainFrame._open_project_file(frame, "restored.mdap")

        self.assertEqual(events[0], ("reset", None))
        self.assertEqual(events[1], ("load", project_data))
        self.assertEqual(events[2], ("clear", None))
        self.assertEqual(events[3], ("remember", str(Path("restored.mdap").resolve())))

        events.clear()
        with mock.patch(
            "gui.main_frame.ProjectManager.load_project",
            side_effect=ValueError("invalid project"),
        ):
            with self.assertRaisesRegex(ValueError, "invalid project"):
                MainFrame._open_project_file(frame, "broken.mdap")
        self.assertEqual(events, [])

    def test_project_properties_mark_project_dirty_only_when_changed(self):
        initial = {
            "auto_switch_interval": 10,
            "crossfade_enabled": True,
            "crossfade_duration": 2.0,
            "level_switch_enabled": False,
            "level_threshold_db": -30.0,
            "level_hysteresis_db": 3.0,
            "level_hold_time": 3.0,
        }
        dirty_events = []
        frame = SimpleNamespace(
            mixer=SimpleNamespace(**initial),
            _mark_project_modified=lambda: dirty_events.append(True),
        )

        self.assertFalse(MainFrame._apply_project_properties(frame, dict(initial)))
        self.assertEqual(dirty_events, [])

        changed = dict(initial, auto_switch_interval=25, crossfade_enabled=False)
        self.assertTrue(MainFrame._apply_project_properties(frame, changed))
        self.assertEqual(frame.mixer.auto_switch_interval, 25)
        self.assertFalse(frame.mixer.crossfade_enabled)
        self.assertEqual(dirty_events, [True])

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
