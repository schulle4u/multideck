"""Active deck and deck selection panel builders."""

import wx

from gui.controls.universal_list import UniversalListCtrl
from utils.i18n import _


def create_active_deck_panel(owner, parent):
    """Create the active deck control panel with listbox and controls."""
    panel = wx.Panel(parent)
    main_sizer = wx.BoxSizer(wx.HORIZONTAL)

    list_panel = _create_deck_selection_panel(owner, panel)
    main_sizer.Add(list_panel, 5, wx.EXPAND | wx.ALL, 5)

    controls_panel = _create_active_deck_controls_panel(owner, panel)
    main_sizer.Add(controls_panel, 7, wx.EXPAND | wx.ALL, 5)

    panel.SetSizer(main_sizer)
    return panel


def _create_deck_selection_panel(owner, parent):
    """Create the deck selection list panel."""
    list_panel = wx.Panel(parent)
    list_panel.SetName(_("Deck Selection"))
    list_panel.SetLabel(_("Deck Selection"))
    list_panel.SetMinSize((360, -1))

    list_panel_sizer = wx.BoxSizer(wx.VERTICAL)
    list_box = wx.StaticBoxSizer(wx.VERTICAL, list_panel, label=_("Deck Selection") + " (F6)")
    list_static_box = list_box.GetStaticBox()

    _create_deck_listbox(owner, list_static_box)
    deck_list_control = owner.deck_listbox.GetControl()
    list_box.Add(deck_list_control, 1, wx.EXPAND | wx.ALL, 5)

    list_panel_sizer.Add(list_box, 1, wx.EXPAND)
    list_panel.SetSizer(list_panel_sizer)
    return list_panel


def _create_deck_listbox(owner, parent):
    """Create the configured deck listbox implementation."""
    force_dataview = owner.config_manager.getboolean('UI', 'force_dataview', False)
    owner.deck_listbox = UniversalListCtrl(
        parent,
        style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SUNKEN,
        checkboxes=True,
        force_dataview=force_dataview
    )
    owner.deck_listbox.InsertColumn(0, _("Play"), width=80, checkbox=True)
    owner.deck_listbox.InsertColumn(1, _("Status"), width=80)
    owner.deck_listbox.InsertColumn(2, _("Deck"), width=wx.LIST_AUTOSIZE)
    owner.deck_listbox.InsertColumn(3, _("File"), width=wx.LIST_AUTOSIZE)
    owner.deck_listbox.InsertColumn(4, _("Output"), width=wx.LIST_AUTOSIZE)
    owner.deck_listbox.Bind(wx.EVT_LIST_ITEM_SELECTED, owner._on_deck_listbox_select)
    owner.deck_listbox.Bind(UniversalListCtrl.EVT_ITEM_CHECKED, owner._on_deck_play_checked)
    owner.deck_listbox.control.SetName(_("Deck Selection"))
    owner.deck_listbox.control.SetLabel(_("Deck Selection"))
    owner.deck_listbox.Bind(wx.EVT_CONTEXT_MENU, owner._on_deck_context_menu)
    owner.deck_listbox.Bind(wx.EVT_CHAR_HOOK, owner._on_deck_listbox_key)


def _create_active_deck_controls_panel(owner, parent):
    """Create the right-side active deck controls panel."""
    controls_panel = wx.Panel(parent)
    controls_panel.SetMinSize((420, -1))
    controls_panel_sizer = wx.BoxSizer(wx.VERTICAL)
    controls_box = wx.StaticBoxSizer(wx.VERTICAL, controls_panel, label=_("Active Deck Controls"))
    controls_static_box = controls_box.GetStaticBox()

    _create_active_deck_header(owner, controls_static_box, controls_box)
    controls_box.Add(_create_active_deck_button_sizer(owner, controls_static_box), 0, wx.EXPAND)

    controls_grid = _create_active_deck_control_grid(owner, controls_static_box)
    level_panel = _create_active_deck_level_panel(owner, controls_static_box)
    controls_box.Add(controls_grid, 0, wx.EXPAND | wx.TOP, 5)
    controls_box.Add(level_panel, 0, wx.EXPAND | wx.TOP, 10)

    controls_panel_sizer.Add(controls_box, 1, wx.EXPAND)
    controls_panel.SetSizer(controls_panel_sizer)
    controls_panel.Bind(wx.EVT_SIZE, owner._on_active_controls_resize)
    return controls_panel


def _create_active_deck_header(owner, parent, sizer):
    """Create active deck title and status text."""
    owner.active_deck_label = wx.StaticText(parent, label=_("No deck selected"))
    font = owner.active_deck_label.GetFont()
    font.SetWeight(wx.FONTWEIGHT_BOLD)
    font.SetPointSize(font.GetPointSize() + 2)
    owner.active_deck_label.SetFont(font)
    sizer.Add(owner.active_deck_label, 0, wx.ALL, 5)

    owner.active_deck_status = wx.StaticText(parent, label="")
    owner.active_deck_status.SetMinSize((-1, 44))
    sizer.Add(owner.active_deck_status, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)


def _create_active_deck_button_sizer(owner, parent):
    """Create active deck playback/menu buttons."""
    button_sizer = wx.GridSizer(rows=1, cols=3, vgap=8, hgap=8)

    owner.active_play_btn = wx.Button(parent, label=_("Play"))
    owner.active_play_btn.SetName(_("Play"))
    owner.active_play_btn.Bind(wx.EVT_BUTTON, owner._on_active_play_pause)
    button_sizer.Add(owner.active_play_btn, 1, wx.ALL, 5)

    owner.active_stop_btn = wx.Button(parent, label=_("Stop"))
    owner.active_stop_btn.SetName(_("Stop"))
    owner.active_stop_btn.Bind(wx.EVT_BUTTON, owner._on_active_stop)
    button_sizer.Add(owner.active_stop_btn, 1, wx.ALL, 5)

    owner.active_menu_btn = wx.Button(parent, label=_("Menu") + "...")
    owner.active_menu_btn.SetName(_("Menu") + "...")
    owner.active_menu_btn.Bind(wx.EVT_BUTTON, owner._on_active_menu)
    button_sizer.Add(owner.active_menu_btn, 1, wx.ALL, 5)
    return button_sizer


def _create_active_deck_control_grid(owner, parent):
    """Create the compact grid for deck controls."""
    controls_grid = wx.FlexGridSizer(rows=2, cols=2, vgap=10, hgap=10)
    controls_grid.AddGrowableCol(0, 1)
    controls_grid.AddGrowableCol(1, 1)
    controls_grid.Add(_create_active_deck_volume_panel(owner, parent), 1, wx.EXPAND)
    controls_grid.Add(_create_active_deck_balance_panel(owner, parent), 1, wx.EXPAND)
    controls_grid.Add(_create_active_deck_options_panel(owner, parent), 1, wx.EXPAND)
    controls_grid.Add(_create_active_deck_position_panel(owner, parent), 1, wx.EXPAND)
    return controls_grid


def _create_active_deck_volume_panel(owner, parent):
    """Create the active deck volume control panel."""
    volume_panel = wx.Panel(parent)
    volume_panel_sizer = wx.BoxSizer(wx.VERTICAL)
    volume_box = wx.StaticBoxSizer(wx.VERTICAL, volume_panel, label=_("Volume"))
    volume_static_box = volume_box.GetStaticBox()
    volume_header = wx.BoxSizer(wx.HORIZONTAL)
    volume_label = wx.StaticText(volume_static_box, label=_("Deck volume"))
    volume_header.Add(volume_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
    volume_header.AddStretchSpacer()
    owner.active_volume_value_label = wx.StaticText(volume_static_box, label="100%")
    volume_header.Add(owner.active_volume_value_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
    volume_box.Add(volume_header, 0, wx.EXPAND)

    owner.active_volume_slider = wx.Slider(
        volume_static_box, value=100, minValue=0, maxValue=100,
        style=wx.SL_HORIZONTAL
    )
    owner.active_volume_slider.SetName(_("Volume"))
    owner.active_volume_slider.Bind(wx.EVT_SLIDER, owner._on_active_volume_change)
    volume_box.Add(owner.active_volume_slider, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
    volume_panel_sizer.Add(volume_box, 1, wx.EXPAND)
    volume_panel.SetSizer(volume_panel_sizer)
    return volume_panel


def _create_active_deck_balance_panel(owner, parent):
    """Create the active deck balance control panel."""
    balance_panel = wx.Panel(parent)
    balance_panel_sizer = wx.BoxSizer(wx.VERTICAL)
    balance_box = wx.StaticBoxSizer(wx.VERTICAL, balance_panel, label=_("Balance"))
    balance_static_box = balance_box.GetStaticBox()
    balance_header = wx.BoxSizer(wx.HORIZONTAL)
    balance_label = wx.StaticText(balance_static_box, label=_("Left / Right"))
    balance_header.Add(balance_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
    balance_header.AddStretchSpacer()
    owner.active_balance_value_label = wx.StaticText(balance_static_box, label=_("Center"))
    balance_header.Add(owner.active_balance_value_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
    balance_box.Add(balance_header, 0, wx.EXPAND)

    owner.active_balance_slider = wx.Slider(
        balance_static_box, value=0, minValue=-100, maxValue=100,
        style=wx.SL_HORIZONTAL
    )
    owner.active_balance_slider.SetName(_("Balance"))
    owner.active_balance_slider.Bind(wx.EVT_SLIDER, owner._on_active_balance_change)
    balance_box.Add(owner.active_balance_slider, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
    balance_panel_sizer.Add(balance_box, 1, wx.EXPAND)
    balance_panel.SetSizer(balance_panel_sizer)
    return balance_panel


def _create_active_deck_options_panel(owner, parent):
    """Create active deck option checkboxes."""
    options_panel = wx.Panel(parent)
    options_panel_sizer = wx.BoxSizer(wx.VERTICAL)
    options_box = wx.StaticBoxSizer(wx.VERTICAL, options_panel, label=_("Options"))
    options_static_box = options_box.GetStaticBox()

    owner.active_mute_cb = wx.CheckBox(options_static_box, label=_("Mute"))
    owner.active_mute_cb.SetName(_("Mute"))
    owner.active_mute_cb.Bind(wx.EVT_CHECKBOX, owner._on_active_mute_change)
    options_box.Add(owner.active_mute_cb, 0, wx.ALL, 5)

    owner.active_loop_cb = wx.CheckBox(options_static_box, label=_("Loop"))
    owner.active_loop_cb.SetName(_("Loop"))
    owner.active_loop_cb.Bind(wx.EVT_CHECKBOX, owner._on_active_loop_change)
    options_box.Add(owner.active_loop_cb, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)

    options_panel_sizer.Add(options_box, 1, wx.EXPAND)
    options_panel.SetSizer(options_panel_sizer)
    return options_panel


def _create_active_deck_position_panel(owner, parent):
    """Create active deck position controls."""
    position_panel = wx.Panel(parent)
    position_panel.SetLabel(_("Position"))
    position_panel.SetName(_("Position"))
    position_panel_sizer = wx.BoxSizer(wx.VERTICAL)
    position_box = wx.StaticBoxSizer(wx.VERTICAL, position_panel, label=_("Position"))
    position_static_box = position_box.GetStaticBox()

    time_sizer = wx.BoxSizer(wx.HORIZONTAL)
    owner.active_position_label = wx.StaticText(position_static_box, label="0:00")
    owner.active_position_label.SetName(_("Current position"))
    time_sizer.Add(owner.active_position_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
    time_sizer.AddStretchSpacer()
    owner.active_duration_label = wx.StaticText(position_static_box, label="0:00")
    owner.active_duration_label.SetName(_("Total duration"))
    time_sizer.Add(owner.active_duration_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
    position_box.Add(time_sizer, 0, wx.EXPAND)

    owner.active_position_slider = wx.Slider(
        position_static_box, value=0, minValue=0, maxValue=1000,
        style=wx.SL_HORIZONTAL
    )
    owner.active_position_slider.SetName(_("Playback position"))
    owner.active_position_slider.Bind(wx.EVT_SLIDER, owner._on_active_position_change)
    owner.active_position_slider.Bind(wx.EVT_LEFT_DOWN, owner._on_position_slider_down)
    owner.active_position_slider.Bind(wx.EVT_LEFT_UP, owner._on_position_slider_up)
    position_box.Add(owner.active_position_slider, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)

    position_panel_sizer.Add(position_box, 1, wx.EXPAND)
    position_panel.SetSizer(position_panel_sizer)
    return position_panel


def _create_active_deck_level_panel(owner, parent):
    """Create active deck level meter controls."""
    level_panel = wx.Panel(parent)
    level_panel.SetLabel(_("Level"))
    level_panel.SetName(_("Level"))
    level_panel_sizer = wx.BoxSizer(wx.VERTICAL)
    level_box = wx.StaticBoxSizer(wx.HORIZONTAL, level_panel, label=_("Level"))
    level_static_box = level_box.GetStaticBox()

    owner.active_level_bar = wx.Panel(level_static_box, size=(-1, 20))
    owner.active_level_bar.SetMinSize((-1, 20))
    owner.active_level_bar._value = 0  # 0-100
    owner.active_level_bar.Bind(wx.EVT_PAINT, owner._on_level_bar_paint)
    level_box.Add(owner.active_level_bar, 1, wx.EXPAND | wx.ALL, 5)

    owner.active_level_db_label = wx.StaticText(level_static_box, label="-inf dB")
    level_box.Add(owner.active_level_db_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

    owner.level_box = level_box
    level_panel_sizer.Add(level_box, 1, wx.EXPAND)
    level_panel.SetSizer(level_panel_sizer)
    owner.level_panel = level_panel
    show_level = owner.config_manager.getboolean('UI', 'show_level_meter', True)
    if not show_level:
        level_panel.Hide()
    return level_panel
