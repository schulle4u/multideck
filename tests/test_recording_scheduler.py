import configparser
from dataclasses import replace
from datetime import datetime
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
import wave

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from audio.recorder import Recorder
from audio.recording_scheduler import (
    RecordingSchedule, RecordingScheduler, schedules_from_dict, schedules_to_dict,
)
from config.config_manager import ProjectManager


class RecordingScheduleTests(unittest.TestCase):
    def test_start_inclusive_end_exclusive_and_weekdays(self):
        schedule = RecordingSchedule(weekdays=(1,))
        self.assertFalse(schedule.is_active(datetime(2026, 11, 9, 19, 59, 59)))
        self.assertTrue(schedule.is_active(datetime(2026, 11, 9, 20)))
        self.assertFalse(schedule.is_active(datetime(2026, 11, 9, 22)))
        self.assertFalse(schedule.is_active(datetime(2026, 11, 10, 21)))
        self.assertFalse(replace(schedule, enabled=False).is_active(datetime(2026, 11, 9, 21)))

    def test_overnight_belongs_to_start_day_including_sunday(self):
        schedule = RecordingSchedule('23:00', '02:00', (7,))
        self.assertTrue(schedule.is_active(datetime(2026, 11, 8, 23)))
        self.assertTrue(schedule.is_active(datetime(2026, 11, 9, 1)))
        self.assertFalse(schedule.is_active(datetime(2026, 11, 9, 2)))
        self.assertFalse(schedule.is_active(datetime(2026, 11, 9, 23)))
        self.assertFalse(schedule.is_active(datetime(2026, 11, 8, 1)))

    def test_validation(self):
        for values in ({'start_time': '24:00'}, {'start_time': '2:00'},
                       {'end_time': '20:00'}, {'weekdays': ()}, {'weekdays': (0, 8)}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                RecordingSchedule(**values)

    def test_nonconsecutive_slots_and_inline_weekday_comment(self):
        data = {'slot3_enabled': 'True', 'slot3_start_time': '20:00',
                'slot3_end_time': '22:00', 'slot3_weekdays': '1,7 # Monday and Sunday'}
        self.assertEqual(schedules_from_dict(data), [RecordingSchedule(weekdays=(1, 7))])

    def test_project_roundtrip_including_empty_deck(self):
        schedules = [RecordingSchedule(name='Beispiel', start_playback=True),
                     RecordingSchedule('23:00', '01:00', (7,), False, name='Nachtaufnahme 100%')]
        data = {'decks': [{}, {}], 'master_schedules': schedules,
                'deck_schedules': [[], schedules]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'schedule.mdap'
            ProjectManager.save_project(str(path), data)
            config = configparser.ConfigParser(interpolation=None)
            config.read(path, encoding='utf-8')
            self.assertEqual(config['MasterSchedules']['slot1_start_time'], '20:00')
            self.assertEqual(config['MasterSchedules']['slot1_name'], 'Beispiel')
            self.assertEqual(config['Deck2Schedules']['slot2_name'], 'Nachtaufnahme 100%')
            self.assertEqual(config['Deck2Schedules']['slot2_enabled'], 'False')
            loaded = ProjectManager.load_project(str(path))
        self.assertEqual(loaded['master_schedules'], schedules)
        self.assertEqual(loaded['deck_schedules'], [[], schedules])
        self.assertEqual(schedules_from_dict(schedules_to_dict(schedules)), schedules)

    def test_old_project_has_no_schedules(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'old.mdap'
            path.write_text('[General]\ndeck_count = 1\n[Deck1]\n', encoding='utf-8')
            loaded = ProjectManager.load_project(str(path))
        self.assertEqual(loaded['master_schedules'], [])
        self.assertEqual(loaded['deck_schedules'], [[]])


class RecordingSchedulerTests(unittest.TestCase):
    def setUp(self):
        self.recorders = {}
        self.starts = []
        self.stops = []
        self.scheduler = RecordingScheduler(self.recorders.get, self.start, self.stop)
        self.scheduler.schedules[None] = [RecordingSchedule()]

    def start(self, target, start_playback):
        self.starts.append(target)
        self.recorders[target] = SimpleNamespace(is_recording=True)
        return True

    def stop(self, target):
        self.stops.append(target)
        self.recorders[target].is_recording = False

    def tick(self, hour, minute=0):
        self.scheduler.tick(datetime(2026, 11, 9, hour, minute))

    def test_overlaps_and_independent_contexts(self):
        self.scheduler.schedules[None].append(RecordingSchedule('21:00', '23:00'))
        self.scheduler.schedules[42] = [RecordingSchedule('20:30', '21:30')]
        self.tick(20)
        self.tick(20, 30)
        self.tick(21, 30)
        self.tick(22)
        self.assertCountEqual(self.starts, [None, 42])
        self.assertEqual(self.stops, [42])
        self.tick(23)
        self.assertEqual(self.stops, [42, None])

    def test_manual_recording_is_never_stopped(self):
        self.recorders[None] = SimpleNamespace(is_recording=True)
        self.tick(21)
        self.tick(22)
        self.assertEqual(self.starts, [])
        self.assertEqual(self.stops, [])

    def test_playback_requested_once_at_start_of_overlapping_windows(self):
        self.scheduler.schedules[None].append(RecordingSchedule(start_playback=True))
        self.scheduler._start = mock.Mock(side_effect=self.start)
        self.tick(20)
        self.tick(21)
        self.scheduler._start.assert_called_once_with(None, True)

    def test_manual_stop_suppresses_restart_until_next_window(self):
        self.tick(20)
        self.recorders[None].is_recording = False
        self.tick(21)
        self.assertEqual(self.starts, [None])
        self.tick(22)
        self.tick(20)
        self.assertEqual(self.starts, [None, None])

    def test_replacement_recording_is_not_stopped(self):
        self.tick(20)
        self.recorders[None] = SimpleNamespace(is_recording=True)
        self.tick(22)
        self.assertEqual(self.stops, [])

    def test_manual_restart_of_same_recorder_releases_ownership(self):
        self.tick(20)
        self.scheduler.release(None)
        self.tick(22)
        self.assertEqual(self.stops, [])

    def test_disabling_or_deleting_window_stops_owned_recording(self):
        self.tick(20)
        self.scheduler.schedules[None][0] = RecordingSchedule(enabled=False)
        self.tick(21)
        self.assertEqual(self.stops, [None])

    def test_failure_is_not_retried_every_second(self):
        self.scheduler._start = mock.Mock(return_value=False)
        self.tick(20)
        self.tick(21)
        self.scheduler._start.assert_called_once_with(None, False)
        self.tick(22)
        self.tick(20)
        self.assertEqual(self.scheduler._start.call_count, 2)

    def test_project_reset_stops_owned_recordings_and_clears_windows(self):
        self.tick(20)
        self.scheduler.reset()
        self.assertEqual(self.stops, [None])
        self.assertEqual(self.scheduler.schedules, {})
        self.tick(21)
        self.assertEqual(self.starts, [None])


class RecorderPauseTests(unittest.TestCase):
    def test_pause_omits_audio_and_resumes_same_file_without_pre_roll(self):
        recorder = Recorder(sample_rate=8000, pre_roll_seconds=1)
        block = np.ones((80, 2), dtype=np.float32) * 0.25
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / 'pause.wav')
            self.assertTrue(recorder.start_recording(output_file=path))
            recorder.write_frames(block)
            recorder.pause_recording()
            recorder.buffer_frames(block)
            recorder.write_frames(block)
            self.assertEqual(recorder.frames_recorded, 80)
            self.assertTrue(recorder.is_recording)
            recorder.resume_recording()
            recorder.write_frames(block)
            recorder.stop_recording()
            with wave.open(path, 'rb') as recording:
                self.assertEqual(recording.getnframes(), 160)
        self.assertFalse(recorder.is_paused)


if __name__ == '__main__':
    unittest.main()
