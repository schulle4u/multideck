"""Exercise native recorder widgets without opening audio devices."""

from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest import mock

import wx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from audio.recorder import Recorder
from audio.recording_scheduler import RecordingSchedule, RecordingScheduler
from gui.dialogs.recorder import RecorderDialog, ScheduleDialog
from gui.main_frame import MainFrame
from utils.i18n import _


class RecorderDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = wx.App.Get() or wx.App(False)

    def setUp(self):
        self.parent = wx.Frame(None)
        self.parent.theme_manager = None
        self.parent.recorder = Recorder(pre_roll_seconds=0)
        self.deck = SimpleNamespace(deck_id=42, name='Test deck', state='empty')
        self.parent.mixer = SimpleNamespace(
            get_deck_by_id=lambda target: self.deck if target == 42 else None,
            deck_recorders={})
        self.parent.config_manager = SimpleNamespace(
            get=lambda section, key, default='': 'recordings' if key == 'output_directory' else default)
        self.parent._get_context_recorder = lambda target=None: MainFrame._get_context_recorder(self.parent, target)
        self.parent._stop_context_recording = mock.Mock()
        self.parent._mark_project_modified = mock.Mock()
        self.parent._is_missing_local_deck_file = lambda deck: False
        self.parent.recording_scheduler = RecordingScheduler(
            self.parent._get_context_recorder, mock.Mock(return_value=False), mock.Mock())
        self.parent.recording_scheduler.tick = mock.Mock()
        self.dialog = None

    def tearDown(self):
        if self.dialog:
            self.dialog.Close()
        self.parent.Destroy()
        self.app.ProcessPendingEvents()

    def test_native_categories_and_checkboxes_update_only_selected_context(self):
        self.parent.recording_scheduler.schedules = {
            None: [RecordingSchedule()], 42: [RecordingSchedule(enabled=False)]}
        self.dialog = RecorderDialog(self.parent, 42)
        self.assertIn('Test deck', self.dialog.GetTitle())
        self.assertEqual(self.dialog.book.GetPageCount(), 2)
        self.assertFalse(self.dialog.schedule_list.IsChecked(0))
        self.dialog._on_checked(SimpleNamespace(GetIndex=lambda: 0, IsChecked=lambda: True))
        self.assertTrue(self.parent.recording_scheduler.schedules[42][0].enabled)
        self.assertEqual(self.parent.recording_scheduler.schedules[None], [RecordingSchedule()])
        self.parent._mark_project_modified.assert_called_once()
        self.dialog._on_delete(None)
        self.assertEqual(self.parent.recording_scheduler.schedules[42], [])

    def test_pause_resume_and_stop_controls(self):
        recorder = self.parent.recorder
        self.dialog = RecorderDialog(self.parent)
        self.assertFalse(self.dialog.stop.IsEnabled())
        recorder.is_recording = True
        self.dialog._on_record(None)
        self.assertTrue(recorder.is_paused)
        self.assertEqual(self.dialog.record.GetLabel(), _('&Resume'))
        self.dialog._on_record(None)
        self.assertFalse(recorder.is_paused)
        self.assertEqual(self.dialog.record.GetLabel(), _('&Pause'))
        self.dialog._on_stop(None)
        self.parent._stop_context_recording.assert_called_once_with(None)
        recorder.is_recording = False

    def test_context_switch_replaces_dialog_and_close_keeps_schedules(self):
        self.parent.recording_scheduler.schedules[None] = [RecordingSchedule()]
        MainFrame._show_recorder_dialog(self.parent)
        master = self.parent._recorder_dialog
        MainFrame._show_recorder_dialog(self.parent, 42)
        self.dialog = self.parent._recorder_dialog
        self.assertEqual(self.dialog.deck_id, 42)
        self.assertIsNot(self.dialog, master)
        self.assertEqual(self.parent.recording_scheduler.schedules[None], [RecordingSchedule()])

    def test_schedule_editor_rejects_invalid_times_without_closing(self):
        with ScheduleDialog(self.parent) as dialog:
            dialog.start.SetValue('25:30')
            with mock.patch('gui.dialogs.recorder.wx.MessageBox') as message:
                dialog._on_ok(None)
            message.assert_called_once()
            self.assertEqual(dialog.schedule, RecordingSchedule())

    def test_schedule_inputs_immediately_follow_their_native_labels(self):
        with ScheduleDialog(self.parent) as dialog:
            controls = (dialog.name, dialog.start, dialog.end)
            labels = (_('&Name:'), _('&Start time (HH:MM):'), _('&End time (HH:MM):'))
            siblings = list(dialog.name.GetParent().GetChildren())
            for control, label in zip(controls, labels):
                with self.subTest(label=label):
                    preceding = siblings[siblings.index(control) - 1]
                    self.assertIsInstance(preceding, wx.StaticText)
                    self.assertEqual(preceding.GetLabel(), label)
                    self.assertEqual(control.GetName(), label.replace('&', ''))
            self.assertLess(siblings.index(dialog.name), siblings.index(dialog.start))
            self.assertLess(siblings.index(dialog.start), siblings.index(dialog.end))

    def test_schedule_name_can_be_edited_and_is_shown_in_list(self):
        schedule = RecordingSchedule(name='Beispiel')
        with ScheduleDialog(self.parent, schedule) as dialog:
            self.assertEqual(dialog.name.GetValue(), 'Beispiel')
            dialog.name.SetValue('Abendaufnahme')
            with mock.patch.object(dialog, 'EndModal') as end_modal:
                dialog._on_ok(None)
            end_modal.assert_called_once_with(wx.ID_OK)
            schedule = dialog.schedule
        self.parent.recording_scheduler.schedules[None] = [schedule]
        self.dialog = RecorderDialog(self.parent)
        self.assertEqual(self.dialog.schedule_list.GetItemText(0, 1), 'Abendaufnahme')
        self.dialog._on_checked(SimpleNamespace(GetIndex=lambda: 0, IsChecked=lambda: False))
        self.assertEqual(self.dialog.schedules[0].name, 'Abendaufnahme')

    def test_project_data_follows_deck_identity_after_reordering(self):
        decks = [SimpleNamespace(deck_id=42, to_dict=lambda: {}, get_effects_dict=lambda: {}),
                 SimpleNamespace(deck_id=99, to_dict=lambda: {}, get_effects_dict=lambda: {})]
        self.parent.mixer.decks = decks
        self.parent.mixer.to_dict = lambda: {}
        self.parent.mixer.get_master_effects_dict = lambda: {}
        schedules = [RecordingSchedule(weekdays=(1, 7))]
        self.parent.recording_scheduler.schedules[42] = schedules
        self.assertEqual(MainFrame._get_project_data(self.parent)['deck_schedules'], [schedules, []])
        decks.reverse()
        self.assertEqual(MainFrame._get_project_data(self.parent)['deck_schedules'], [[], schedules])


if __name__ == '__main__':
    unittest.main()
