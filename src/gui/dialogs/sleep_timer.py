"""
Sleep timer dialog for MultiDeck Audio Player.
"""

from dataclasses import dataclass

import wx

from utils.i18n import _


ACTION_STOP_ALL = "stop_all"
ACTION_STOP_ALL_AND_EXIT = "stop_all_and_exit"
ACTION_SHUTDOWN = "shutdown"


@dataclass(frozen=True)
class SleepTimerConfig:
    """Configuration selected in the sleep timer dialog."""

    minutes: int
    action: str

    @property
    def seconds(self) -> int:
        return self.minutes * 60


class SleepTimerDialog(wx.Dialog):
    """Dialog for configuring the playback sleep timer."""

    def __init__(self, parent, current_config=None, remaining_seconds=None):
        super().__init__(
            parent,
            title=_("Sleep Timer"),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self._timer_cancelled = False
        self._action_values = [
            ACTION_STOP_ALL,
            ACTION_STOP_ALL_AND_EXIT,
            ACTION_SHUTDOWN,
        ]

        self._create_ui(current_config, remaining_seconds)
        self.SetMinSize(self.GetSize())
        self.Center()

    def _create_ui(self, current_config, remaining_seconds):
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        if remaining_seconds is not None:
            status = _("A sleep timer is running. Remaining time: {minutes} min").format(
                minutes=max(1, round(remaining_seconds / 60))
            )
            status_label = wx.StaticText(panel, label=status)
            main_sizer.Add(status_label, 0, wx.EXPAND | wx.ALL, 10)

        time_sizer = wx.BoxSizer(wx.HORIZONTAL)
        time_label = wx.StaticText(panel, label=_("Time until action (minutes)") + ":")
        time_sizer.Add(time_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)

        initial_minutes = current_config.minutes if current_config else 30
        if remaining_seconds is not None:
            initial_minutes = max(1, round(remaining_seconds / 60))

        self.minutes_spin = wx.SpinCtrl(panel, value=str(initial_minutes), min=1, max=1440, initial=initial_minutes)
        self.minutes_spin.SetName(_("Time until action (minutes)"))
        time_sizer.Add(self.minutes_spin, 1, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(time_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)

        action_sizer = wx.BoxSizer(wx.HORIZONTAL)
        action_label = wx.StaticText(panel, label=_("Action after timer expires") + ":")
        action_sizer.Add(action_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)

        action_choices = [
            _("Stop playback on all active decks"),
            _("Stop playback and exit MultiDeck"),
            _("Stop playback and shut down the computer"),
        ]
        self.action_choice = wx.Choice(panel, choices=action_choices)
        self.action_choice.SetName(_("Action after timer expires"))
        if current_config and current_config.action in self._action_values:
            self.action_choice.SetSelection(self._action_values.index(current_config.action))
        else:
            self.action_choice.SetSelection(0)
        action_sizer.Add(self.action_choice, 1, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(action_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)

        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        if remaining_seconds is not None:
            cancel_timer_button = wx.Button(panel, wx.ID_ANY, label=_("Cancel Timer"))
            cancel_timer_button.SetName(_("Cancel Timer"))
            cancel_timer_button.Bind(wx.EVT_BUTTON, self._on_cancel_timer)
            button_sizer.Add(cancel_timer_button, 0, wx.ALL, 5)

        button_sizer.AddStretchSpacer()
        ok_button = wx.Button(panel, wx.ID_OK, label=_("&OK"))
        ok_button.SetName(_("&OK"))
        ok_button.SetDefault()
        cancel_button = wx.Button(panel, wx.ID_CANCEL, label=_("&Cancel"))
        cancel_button.SetName(_("&Cancel"))
        button_sizer.Add(ok_button, 0, wx.ALL, 5)
        button_sizer.Add(cancel_button, 0, wx.ALL, 5)
        main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 10)

        ok_button.Bind(wx.EVT_BUTTON, self._on_ok)

        panel.SetSizer(main_sizer)
        self.Fit()

    def _on_ok(self, event):
        self.EndModal(wx.ID_OK)

    def _on_cancel_timer(self, event):
        self._timer_cancelled = True
        self.EndModal(wx.ID_CANCEL)

    def WasTimerCancelled(self):
        return self._timer_cancelled

    def GetTimerConfig(self):
        """Return the selected timer configuration."""
        action_idx = self.action_choice.GetSelection()
        if action_idx == wx.NOT_FOUND:
            action_idx = 0
        return SleepTimerConfig(
            minutes=self.minutes_spin.GetValue(),
            action=self._action_values[action_idx],
        )
