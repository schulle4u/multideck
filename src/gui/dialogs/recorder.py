"""Context-sensitive direct recording controls and weekly recording planner."""

from dataclasses import replace
import sys

import wx
from m45wxcontrols import AccessibleListbook, UniversalListCtrl

from audio.recording_scheduler import RecordingSchedule
from config.defaults import DECK_STATE_EMPTY
from utils.i18n import _


def weekday_names():
    return (_("Monday"), _("Tuesday"), _("Wednesday"), _("Thursday"),
            _("Friday"), _("Saturday"), _("Sunday"))


class ScheduleDialog(wx.Dialog):
    """Edit a weekly window; weekdays refer to the day recording starts."""

    def __init__(self, parent, schedule=None):
        super().__init__(parent, title=_("Recording Schedule"),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.schedule = schedule or RecordingSchedule()
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.enabled = wx.CheckBox(panel, label=_("&Enabled"))
        self.enabled.SetValue(self.schedule.enabled)
        sizer.Add(self.enabled, 0, wx.ALL, 10)
        fields = wx.FlexGridSizer(cols=2, vgap=10, hgap=10)
        fields.AddGrowableCol(1)
        for attribute, label, value in (
                ('name', _("&Name:"), self.schedule.name),
                ('start', _("&Start time (HH:MM):"), self.schedule.start_time),
                ('end', _("&End time (HH:MM):"), self.schedule.end_time)):
            # Native edit controls derive their accessible label from the
            # preceding sibling. Create each label before its input, rather
            # than relying on sizer order or SetName alone.
            fields.Add(wx.StaticText(panel, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
            control = wx.TextCtrl(panel, value=value)
            control.SetName(label.replace('&', ''))
            setattr(self, attribute, control)
            fields.Add(control, 1, wx.EXPAND)
        sizer.Add(fields, 0, wx.EXPAND | wx.ALL, 10)
        self.start_playback = wx.CheckBox(panel, label=_("Start &playback with recording"))
        self.start_playback.SetValue(self.schedule.start_playback)
        sizer.Add(self.start_playback, 0, wx.ALL, 10)
        box = wx.StaticBoxSizer(wx.VERTICAL, panel, _("Start on weekdays"))
        self.days = []
        for number, name in enumerate(weekday_names(), 1):
            check = wx.CheckBox(box.GetStaticBox(), label=name)
            check.SetValue(number in self.schedule.weekdays)
            box.Add(check, 0, wx.ALL, 3)
            self.days.append(check)
        sizer.Add(box, 0, wx.EXPAND | wx.ALL, 10)
        note = wx.StaticText(panel, label=_(
            "Local time. An end time before the start time ends on the following day."))
        note.Wrap(420)
        sizer.Add(note, 0, wx.EXPAND | wx.ALL, 10)
        panel.SetSizer(sizer)
        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(panel, 1, wx.EXPAND)
        outer.Add(self.CreateButtonSizer(wx.OK | wx.CANCEL), 0, wx.EXPAND | wx.ALL, 10)
        self.SetSizerAndFit(outer)
        self.SetMinSize(self.GetSize())
        self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)
        self.CenterOnParent()

    def _on_ok(self, event):
        try:
            self.schedule = RecordingSchedule(
                start_time=self.start.GetValue().strip(),
                end_time=self.end.GetValue().strip(),
                weekdays=tuple(i for i, check in enumerate(self.days, 1) if check.GetValue()),
                enabled=self.enabled.GetValue(),
                name=self.name.GetValue().strip(),
                start_playback=self.start_playback.GetValue())
        except ValueError:
            wx.MessageBox(_("Enter valid, different start and end times in HH:MM format "
                            "and select at least one weekday."),
                          _("Invalid Schedule"), wx.OK | wx.ICON_ERROR, self)
            return
        self.EndModal(wx.ID_OK)


class RecorderDialog(wx.Dialog):
    """Modeless dialog owning one master or deck recording context."""

    def __init__(self, parent, deck_id=None):
        self.main_frame = parent
        self.deck_id = deck_id
        deck = parent.mixer.get_deck_by_id(deck_id) if deck_id is not None else None
        name = deck.name if deck else _("Master")
        super().__init__(parent, title=_("Recorder: {}").format(name),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self._refreshing = False
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.book = AccessibleListbook(panel, name=_("Categories"))
        self.book.SetStaticLabel(_("Cate&gories"))
        self.book.GetListBox().SetName(_("Categories"))
        self.book.GetListBox().SetLabel(_("Categories"))
        self.book.AddPage(self._create_recording_page(self.book.GetPageArea()), _("Recording"))
        self.book.AddPage(self._create_planner_page(self.book.GetPageArea()), _("Planner"))
        sizer.Add(self.book, 1, wx.EXPAND | wx.ALL, 10)
        close = wx.Button(panel, wx.ID_CLOSE, _("&Close"))
        close.Bind(wx.EVT_BUTTON, lambda event: self.Close())
        sizer.Add(close, 0, wx.ALIGN_RIGHT | wx.ALL, 10)
        panel.SetSizer(sizer)
        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(panel, 1, wx.EXPAND)
        self.SetSizer(outer)
        self.Fit()
        size = self.GetSize()
        self.SetSize((max(920, size.width), max(460, size.height)))
        self.SetMinSize(self.GetSize())
        if parent.theme_manager:
            parent.theme_manager.apply_theme(self)
        self.CenterOnParent()
        self._timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._update_state, self._timer)
        self._timer.Start(250)
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_key)
        if sys.platform != 'win32':
            self.Bind(wx.EVT_SHOW, self._on_first_show)
        self._refresh_schedules()
        self._update_state()
        self.book.GetListBox().SetFocus()

    @property
    def schedules(self):
        return self.main_frame.recording_scheduler.schedules.setdefault(self.deck_id, [])

    def _on_first_show(self, event):
        """Size hidden pages after realization, as in the effects dialog."""
        event.Skip()
        if not event.IsShown():
            return
        self.Unbind(wx.EVT_SHOW)
        size = self.book.GetPageArea().GetClientSize()
        if size.width > 0 and size.height > 0:
            for index in range(self.book.GetPageCount()):
                page = self.book.GetPage(index)
                if not page.IsShown():
                    page.SetSize(0, 0, size.width, size.height)
                    page.Layout()

    def _create_recording_page(self, parent):
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.status = wx.StaticText(panel, label=_("Stopped"))
        sizer.Add(self.status, 0, wx.ALL, 10)
        buttons = wx.BoxSizer(wx.HORIZONTAL)
        self.record = wx.Button(panel, label=_("&Record"))
        self.stop = wx.Button(panel, label=_("&Stop"))
        self.record.Bind(wx.EVT_BUTTON, self._on_record)
        self.stop.Bind(wx.EVT_BUTTON, self._on_stop)
        buttons.Add(self.record, 0, wx.ALL, 5)
        buttons.Add(self.stop, 0, wx.ALL, 5)
        sizer.Add(buttons, 0, wx.ALL, 5)
        panel.SetSizer(sizer)
        return panel

    def _create_planner_page(self, parent):
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.schedule_list = UniversalListCtrl(
            panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SUNKEN,
            checkboxes=True,
            list_type=self.main_frame.config_manager.get('UI', 'deck_list_type', 'auto'))
        for col, (label, width) in enumerate(((_("Enabled"), 80), (_("Name"), 180), (_("Start"), 80),
                                             (_("End"), 80), (_("Weekdays"), 360))):
            self.schedule_list.InsertColumn(col, label, width=width, checkbox=(col == 0))
        self.schedule_list.GetControl().SetName(_("Recording Schedules"))
        self.schedule_list.GetControl().SetLabel(_("Recording Schedules"))
        self.schedule_list.GetControl().SetMinSize((740, 180))
        self.schedule_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self._update_selection)
        self.schedule_list.Bind(UniversalListCtrl.EVT_ITEM_CHECKED, self._on_checked)
        sizer.Add(self.schedule_list.GetControl(), 1, wx.EXPAND | wx.ALL, 10)
        buttons = wx.BoxSizer(wx.HORIZONTAL)
        add = wx.Button(panel, label=_("&Add..."))
        self.edit = wx.Button(panel, label=_("&Edit..."))
        self.delete = wx.Button(panel, label=_("&Delete"))
        for button, handler in ((add, self._on_add), (self.edit, self._on_edit),
                                (self.delete, self._on_delete)):
            button.Bind(wx.EVT_BUTTON, handler)
            buttons.Add(button, 0, wx.ALL, 5)
        sizer.Add(buttons, 0, wx.LEFT | wx.RIGHT, 5)
        note = wx.StaticText(panel, label=_(
            "Schedules run while MultiDeck is open and are saved with the project. "
            "They use the output directory from Recorder settings."))
        note.Wrap(560)
        sizer.Add(note, 0, wx.EXPAND | wx.ALL, 10)
        panel.SetSizer(sizer)
        return panel

    def _update_state(self, event=None):
        recorder = self.main_frame._get_context_recorder(self.deck_id)
        recording = recorder is not None and recorder.is_recording
        paused = recording and recorder.is_paused
        label = _("&Resume") if paused else (_("&Pause") if recording else _("&Record"))
        if self.record.GetLabel() != label:
            self.record.SetLabel(label)
        self.stop.Enable(recording)
        deck = self.main_frame.mixer.get_deck_by_id(self.deck_id) if self.deck_id is not None else None
        can_start = self.deck_id is None or (deck and deck.state != DECK_STATE_EMPTY
                                             and not self.main_frame._is_missing_local_deck_file(deck))
        self.record.Enable(bool(recording or can_start))
        status = _("Paused") if paused else (_("Recording") if recording else _("Stopped"))
        if self.status.GetLabel() != status:
            self.status.SetLabel(status)

    def _on_record(self, event):
        recorder = self.main_frame._get_context_recorder(self.deck_id)
        if recorder and recorder.is_recording:
            if recorder.is_paused:
                recorder.resume_recording()
            else:
                recorder.pause_recording()
        elif self.deck_id is None:
            self.main_frame._on_toggle_recording(event)
        else:
            deck = self.main_frame.mixer.get_deck_by_id(self.deck_id)
            if deck:
                self.main_frame._on_toggle_deck_recording(deck)
        self._update_state()

    def _on_stop(self, event):
        self.main_frame.recording_scheduler.release(self.deck_id)
        self.main_frame._stop_context_recording(self.deck_id)
        self._update_state()

    def _refresh_schedules(self, selection=wx.NOT_FOUND):
        self._refreshing = True
        try:
            self.schedule_list.DeleteAllItems()
            names = weekday_names()
            for schedule in self.schedules:
                self.schedule_list.Append([schedule.enabled, schedule.name, schedule.start_time, schedule.end_time,
                                           ', '.join(names[day - 1] for day in schedule.weekdays)])
            if 0 <= selection < len(self.schedules):
                self.schedule_list.SelectRow(selection)
        finally:
            self._refreshing = False
        self._update_selection()

    def _update_selection(self, event=None):
        selected = 0 <= self.schedule_list.GetSelectedRow() < len(self.schedules)
        self.edit.Enable(selected)
        self.delete.Enable(selected)

    def _ensure_output_directory(self):
        config = self.main_frame.config_manager
        if config.get('Recorder', 'output_directory', ''):
            return True
        with wx.DirDialog(self, _("Choose recording output directory")) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return False
            config.set('Recorder', 'output_directory', dialog.GetPath())
            config.save()
        return True

    def _changed(self, selection):
        self.main_frame._mark_project_modified()
        self._refresh_schedules(selection)
        self.main_frame.recording_scheduler.tick()

    def _edit_schedule(self, index=None):
        with ScheduleDialog(self, self.schedules[index] if index is not None else None) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            schedule = dialog.schedule
        if schedule.enabled and not self._ensure_output_directory():
            return
        if index is None:
            index = len(self.schedules)
            self.schedules.append(schedule)
        else:
            self.schedules[index] = schedule
        self._changed(index)

    def _on_add(self, event):
        self._edit_schedule()

    def _on_edit(self, event):
        index = self.schedule_list.GetSelectedRow()
        if 0 <= index < len(self.schedules):
            self._edit_schedule(index)

    def _on_delete(self, event):
        index = self.schedule_list.GetSelectedRow()
        if 0 <= index < len(self.schedules):
            del self.schedules[index]
            self._changed(min(index, len(self.schedules) - 1))

    def _on_checked(self, event):
        if self._refreshing:
            return
        index = event.GetIndex()
        if 0 <= index < len(self.schedules):
            enabled = event.IsChecked()
            if enabled and not self._ensure_output_directory():
                self._refresh_schedules(index)
                return
            self.schedules[index] = replace(self.schedules[index], enabled=enabled)
            self._changed(index)

    def _on_key(self, event):
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.Close()
        else:
            event.Skip()

    def _on_close(self, event):
        self._timer.Stop()
        if getattr(self.main_frame, '_recorder_dialog', None) is self:
            self.main_frame._recorder_dialog = None
        self.Destroy()
