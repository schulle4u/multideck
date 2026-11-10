"""Weekly recording windows in local wall-clock time, independent of the GUI."""

from dataclasses import dataclass
from datetime import datetime, time, timedelta
import re


@dataclass(frozen=True)
class RecordingSchedule:
    start_time: str = '20:00'
    end_time: str = '22:00'
    weekdays: tuple = (1, 2, 3, 4, 5, 6, 7)
    enabled: bool = True
    name: str = ''
    start_playback: bool = False

    def __post_init__(self):
        for value in (self.start_time, self.end_time):
            if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', value):
                raise ValueError('Times must use HH:MM.')
            time.fromisoformat(value)
        if self.start_time == self.end_time:
            raise ValueError('Start and end times must differ.')
        if not self.weekdays or any(day not in range(1, 8) for day in self.weekdays):
            raise ValueError('Select at least one weekday (1–7).')

    def is_active(self, now):
        if not self.enabled:
            return False
        start = datetime.combine(now.date(), time.fromisoformat(self.start_time))
        end = datetime.combine(now.date(), time.fromisoformat(self.end_time))
        if end < start:
            if now < end:
                start -= timedelta(days=1)
            else:
                end += timedelta(days=1)
        return start.isoweekday() in self.weekdays and start <= now < end


def schedules_from_dict(data):
    """Read slotN fields; reject malformed schedules rather than arming them."""
    slots = sorted({int(match.group(1)) for key in data
                    if (match := re.fullmatch(r'slot(\d+)_enabled', key))})
    result = []
    for slot in slots:
        prefix = f'slot{slot}_'
        enabled = data[prefix + 'enabled'].strip().lower()
        if enabled not in ('true', 'false', '1', '0', 'yes', 'no', 'on', 'off'):
            raise ValueError(f'Invalid enabled value in slot {slot}.')
        result.append(RecordingSchedule(
            start_time=data[prefix + 'start_time'].strip(),
            end_time=data[prefix + 'end_time'].strip(),
            weekdays=tuple(sorted({int(day.strip()) for day in
                                  data[prefix + 'weekdays'].split('#', 1)[0].split(',')})),
            enabled=enabled in ('true', '1', 'yes', 'on'),
            name=data.get(prefix + 'name', ''),
            start_playback=data.get(prefix + 'start_playback', '').strip().lower()
            in ('true', '1', 'yes', 'on'),
        ))
    return result


def schedules_to_dict(schedules):
    data = {}
    for slot, schedule in enumerate(schedules, 1):
        prefix = f'slot{slot}_'
        data.update({prefix + 'enabled': str(schedule.enabled),
                     prefix + 'name': schedule.name,
                     prefix + 'start_playback': str(schedule.start_playback),
                     prefix + 'start_time': schedule.start_time,
                     prefix + 'end_time': schedule.end_time,
                     prefix + 'weekdays': ','.join(map(str, schedule.weekdays))})
    return data


class RecordingScheduler:
    """Merge overlapping windows and stop only recordings started by us.

    A manual stop or failed start suppresses restarts until the window ends.
    Recorder identity prevents a later manual recording being stopped by us.
    """

    def __init__(self, get_recorder, start_recording, stop_recording):
        self.schedules = {}
        self._get_recorder = get_recorder
        self._start = start_recording
        self._stop = stop_recording
        self._attempted = set()
        self._owned = {}

    def tick(self, now=None):
        now = now or datetime.now()
        active = {}
        for target, schedules in self.schedules.items():
            windows = [schedule for schedule in schedules if schedule.is_active(now)]
            if windows:
                active[target] = any(schedule.start_playback for schedule in windows)
        for target in list(self._owned):
            if target not in active:
                recorder = self._owned.pop(target)
                if self._get_recorder(target) is recorder and recorder.is_recording:
                    self._stop(target)
        self._attempted.intersection_update(active)
        for target in active.keys() - self._attempted:
            self._attempted.add(target)
            recorder = self._get_recorder(target)
            if recorder is not None and recorder.is_recording:
                continue
            if self._start(target, active[target]):
                self._owned[target] = self._get_recorder(target)

    def release(self, target):
        """Detach a manually controlled recorder from automatic stopping."""
        self._owned.pop(target, None)

    def reset(self):
        for target, recorder in list(self._owned.items()):
            if self._get_recorder(target) is recorder and recorder.is_recording:
                self._stop(target)
        self._owned.clear()
        self._attempted.clear()
        self.schedules.clear()
