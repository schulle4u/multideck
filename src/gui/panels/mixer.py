"""Mixer and global playback panel builders."""

import wx

from config.defaults import MODE_AUTOMATIC, MODE_MIXER, MODE_MULTIROOM, MODE_SOLO
from utils.i18n import _


def create_mixer_panel(owner, parent):
    """Create mixer control panel."""
    panel = wx.Panel(parent)
    sizer = wx.BoxSizer(wx.HORIZONTAL)

    sizer.Add(_create_mode_panel(owner, panel), 0, wx.ALL, 5)
    sizer.Add(_create_global_playback_panel(owner, panel), 0, wx.ALL, 5)
    sizer.Add(_create_master_volume_panel(owner, panel), 1, wx.ALL | wx.EXPAND, 5)

    panel.SetSizer(sizer)
    return panel


def _create_mode_panel(owner, parent):
    """Create operating mode controls."""
    mode_panel = wx.Panel(parent)
    mode_panel_sizer = wx.BoxSizer(wx.VERTICAL)
    mode_box = wx.StaticBoxSizer(wx.VERTICAL, mode_panel, label=_("Operating Mode"))
    mode_static_box = mode_box.GetStaticBox()
    owner.mixer_mode_radio = wx.RadioButton(mode_static_box, label=_("Mixer Mode") + "\tF3", style=wx.RB_GROUP)
    owner.solo_mode_radio = wx.RadioButton(mode_static_box, label=_("Solo Mode") + "\tF4")
    owner.auto_mode_radio = wx.RadioButton(mode_static_box, label=_("Automatic Mode") + "\tF5")
    owner.multiroom_mode_radio = wx.RadioButton(mode_static_box, label=_("Multiroom Mode") + "\tF7")
    owner.mixer_mode_radio.SetValue(True)
    owner.mixer_mode_radio.Bind(wx.EVT_RADIOBUTTON, lambda e: owner._set_mode(MODE_MIXER))
    owner.solo_mode_radio.Bind(wx.EVT_RADIOBUTTON, lambda e: owner._set_mode(MODE_SOLO))
    owner.auto_mode_radio.Bind(wx.EVT_RADIOBUTTON, lambda e: owner._set_mode(MODE_AUTOMATIC))
    owner.multiroom_mode_radio.Bind(wx.EVT_RADIOBUTTON, lambda e: owner._set_mode(MODE_MULTIROOM))
    mode_box.Add(owner.mixer_mode_radio, 0, wx.ALL, 5)
    mode_box.Add(owner.solo_mode_radio, 0, wx.ALL, 5)
    mode_box.Add(owner.auto_mode_radio, 0, wx.ALL, 5)
    mode_box.Add(owner.multiroom_mode_radio, 0, wx.ALL, 5)
    mode_panel_sizer.Add(mode_box, 1, wx.EXPAND)
    mode_panel.SetSizer(mode_panel_sizer)
    return mode_panel


def _create_global_playback_panel(owner, parent):
    """Create global playback controls."""
    playback_panel = wx.Panel(parent)
    playback_panel_sizer = wx.BoxSizer(wx.VERTICAL)
    playback_box = wx.StaticBoxSizer(wx.VERTICAL, playback_panel, label=_("Global Playback"))
    playback_static_box = playback_box.GetStaticBox()
    button_sizer = wx.BoxSizer(wx.HORIZONTAL)
    owner.global_play_pause_btn = wx.Button(playback_static_box, label=_("Play All"))
    owner.global_play_pause_btn.SetToolTip(_("Play/Pause all decks"))
    owner.global_play_pause_btn.Bind(wx.EVT_BUTTON, owner._on_global_play_pause)
    button_sizer.Add(owner.global_play_pause_btn, 0, wx.ALL, 5)
    owner.global_stop_btn = wx.Button(playback_static_box, label=_("Stop All"))
    owner.global_stop_btn.SetToolTip(_("Stop all decks and reset positions"))
    owner.global_stop_btn.Bind(wx.EVT_BUTTON, owner._on_global_stop)
    button_sizer.Add(owner.global_stop_btn, 0, wx.ALL, 5)
    playback_box.Add(button_sizer, 0, wx.EXPAND)
    owner.active_stream_cb = wx.CheckBox(playback_static_box, label=_("Enable Livestream"))
    owner.active_stream_cb.SetName(_("Enable Livestream"))
    owner.active_stream_cb.Bind(wx.EVT_CHECKBOX, owner._on_active_stream_change)
    playback_box.Add(owner.active_stream_cb, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
    playback_panel_sizer.Add(playback_box, 1, wx.EXPAND)
    playback_panel.SetSizer(playback_panel_sizer)
    return playback_panel


def _create_master_volume_panel(owner, parent):
    """Create master volume controls."""
    volume_panel = wx.Panel(parent)
    volume_panel_sizer = wx.BoxSizer(wx.VERTICAL)
    volume_box = wx.StaticBoxSizer(wx.VERTICAL, volume_panel, label=_("Master Volume"))
    volume_static_box = volume_box.GetStaticBox()
    volume_header = wx.BoxSizer(wx.HORIZONTAL)
    volume_label = wx.StaticText(volume_static_box, label=_("Master Volume"))
    volume_header.Add(volume_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
    volume_header.AddStretchSpacer()
    owner.master_volume_value_label = wx.StaticText(volume_static_box, label="80%")
    volume_header.Add(owner.master_volume_value_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
    volume_box.Add(volume_header, 0, wx.EXPAND)
    master_sizer = wx.BoxSizer(wx.HORIZONTAL)
    owner.master_volume_slider = wx.Slider(
        volume_static_box, value=80, minValue=0, maxValue=100,
        style=wx.SL_HORIZONTAL
    )
    owner.master_volume_slider.Bind(wx.EVT_SLIDER, owner._on_master_volume_change)
    master_sizer.Add(owner.master_volume_slider, 1, wx.EXPAND | wx.ALL, 5)
    volume_box.Add(master_sizer, 0, wx.EXPAND)
    volume_panel_sizer.Add(volume_box, 1, wx.EXPAND)
    volume_panel.SetSizer(volume_panel_sizer)
    return volume_panel
