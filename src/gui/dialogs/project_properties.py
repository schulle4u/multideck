"""Project-specific mixer settings dialog."""

import wx

from m45wxcontrols import AccessibleSpinCtrl
from utils.i18n import _


class ProjectPropertiesDialog(wx.Dialog):
    """Edit automation settings stored in the current project."""

    def __init__(self, parent, mixer, theme_manager=None):
        super().__init__(
            parent,
            title=_("Project Properties"),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self.mixer = mixer
        self.theme_manager = theme_manager
        self._create_ui()
        self.Fit()
        self.SetMinSize(self.GetSize())
        self.CenterOnParent()

        if self.theme_manager:
            self.theme_manager.apply_theme(self)

    def _create_ui(self):
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        settings_sizer = wx.BoxSizer(wx.VERTICAL)

        interval_sizer = wx.BoxSizer(wx.HORIZONTAL)
        interval_label = wx.StaticText(panel, label=_("Switch Interval (seconds)") + ":")
        interval_sizer.Add(interval_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        self.interval_spin = wx.SpinCtrl(
            panel,
            value=str(self.mixer.auto_switch_interval),
            min=1,
            max=300,
            initial=self.mixer.auto_switch_interval,
        )
        self.interval_spin.SetName(_("Switch Interval (seconds)"))
        interval_sizer.Add(self.interval_spin, 1, wx.EXPAND | wx.ALL, 5)
        settings_sizer.Add(interval_sizer, 0, wx.EXPAND | wx.ALL, 5)

        self.crossfade_check = wx.CheckBox(panel, label=_("Enable Crossfade"))
        self.crossfade_check.SetName(_("Enable Crossfade"))
        self.crossfade_check.SetValue(self.mixer.crossfade_enabled)
        settings_sizer.Add(self.crossfade_check, 0, wx.ALL, 10)

        self.crossfade_ctrl = AccessibleSpinCtrl(
            panel,
            label_text=_("Crossfade Duration (seconds)") + ":",
            initial_val=self.mixer.crossfade_duration,
            min_val=0.5,
            max_val=10.0,
            inc=0.1,
        )
        settings_sizer.Add(self.crossfade_ctrl, 0, wx.EXPAND | wx.ALL, 5)

        settings_sizer.Add(wx.StaticLine(panel), 0, wx.EXPAND | wx.ALL, 10)

        level_header = wx.StaticText(panel, label=_("Level-Based Switching"))
        header_font = level_header.GetFont()
        header_font.SetWeight(wx.FONTWEIGHT_BOLD)
        level_header.SetFont(header_font)
        settings_sizer.Add(level_header, 0, wx.ALL, 5)

        self.level_switch_check = wx.CheckBox(
            panel, label=_("Enable level-based switching")
        )
        self.level_switch_check.SetName(_("Enable level-based switching"))
        self.level_switch_check.SetValue(self.mixer.level_switch_enabled)
        settings_sizer.Add(self.level_switch_check, 0, wx.ALL, 10)

        self.threshold_spin = self._add_spin_setting(
            panel,
            settings_sizer,
            _("Threshold (dB)"),
            int(self.mixer.level_threshold_db),
            -60,
            0,
        )
        self.hysteresis_spin = self._add_spin_setting(
            panel,
            settings_sizer,
            _("Hysteresis (dB)"),
            int(self.mixer.level_hysteresis_db),
            0,
            20,
        )
        self.hold_time_spin = self._add_spin_setting(
            panel,
            settings_sizer,
            _("Hold Time (seconds)"),
            int(self.mixer.level_hold_time),
            1,
            30,
        )

        main_sizer.Add(settings_sizer, 1, wx.EXPAND | wx.ALL, 10)
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.AddStretchSpacer()
        ok_button = wx.Button(panel, wx.ID_OK, label=_("&OK"))
        ok_button.SetDefault()
        cancel_button = wx.Button(panel, wx.ID_CANCEL, label=_("&Cancel"))
        button_sizer.Add(ok_button, 0, wx.ALL, 5)
        button_sizer.Add(cancel_button, 0, wx.ALL, 5)
        main_sizer.Add(
            button_sizer,
            0,
            wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,
            10,
        )
        panel.SetSizer(main_sizer)

    @staticmethod
    def _add_spin_setting(parent, sizer, label, value, minimum, maximum):
        row = wx.BoxSizer(wx.HORIZONTAL)
        text = wx.StaticText(parent, label=label + ":")
        row.Add(text, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        control = wx.SpinCtrl(
            parent,
            value=str(value),
            min=minimum,
            max=maximum,
            initial=value,
        )
        control.SetName(label)
        row.Add(control, 1, wx.EXPAND | wx.ALL, 5)
        sizer.Add(row, 0, wx.EXPAND | wx.ALL, 5)
        return control

    def get_values(self):
        """Return the project mixer values entered by the user."""
        return {
            "auto_switch_interval": self.interval_spin.GetValue(),
            "crossfade_enabled": self.crossfade_check.GetValue(),
            "crossfade_duration": self.crossfade_ctrl.GetValue(),
            "level_switch_enabled": self.level_switch_check.GetValue(),
            "level_threshold_db": float(self.threshold_spin.GetValue()),
            "level_hysteresis_db": float(self.hysteresis_spin.GetValue()),
            "level_hold_time": float(self.hold_time_spin.GetValue()),
        }
