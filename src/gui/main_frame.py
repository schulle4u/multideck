"""
Main Frame - Main application window
"""

import wx
import wx.adv
import os
from pathlib import Path

from gui.dialogs import OptionsDialog, CustomTextEntryDialog
from gui.theme_manager import ThemeManager
from audio.audio_engine import AudioEngine
from audio.mixer import Mixer
from audio.recorder import Recorder
from config.config_manager import ConfigManager, ProjectManager
from config.defaults import (
    APP_NAME, APP_VERSION, APP_AUTHOR, APP_WEBSITE, APP_LICENSE,
    SUPPORTED_FILE_FORMATS, PROJECT_FILE_FILTER, MODE_MIXER, MODE_SOLO, MODE_AUTOMATIC,
    DECK_STATE_EMPTY, DECK_STATE_PLAYING, DECK_STATE_PAUSED
)
from utils.i18n import _, get_i18n
from utils.helpers import format_time, parse_time


class MainFrame(wx.Frame):
    """Main application window"""

    def __init__(self):
        """Initialize main frame"""
        super().__init__(None, title=f"{APP_NAME} v{APP_VERSION}", size=(1200, 800))

        # Configuration
        self.config_manager = ConfigManager()

        # Audio setup
        buffer_size = self.config_manager.getint('Audio', 'buffer_size', 2048)
        sample_rate = self.config_manager.getint('Audio', 'sample_rate', 44100)
        device = self.config_manager.get('Audio', 'output_device', 'default')

        self.audio_engine = AudioEngine(buffer_size, sample_rate, device)

        # Recorder (create before mixer so it can be passed to mixer)
        bit_depth = self.config_manager.getint('Recorder', 'bit_depth', 16)
        rec_format = self.config_manager.get('Recorder', 'format', 'wav')
        rec_bitrate = self.config_manager.getint('Recorder', 'bitrate', 192)
        pre_roll = self.config_manager.getfloat('Recorder', 'pre_roll_seconds', 30.0)
        self.recorder = Recorder(sample_rate, 2, bit_depth, rec_format, rec_bitrate, pre_roll)
        self.recorder.on_recording_started = self._on_recording_started
        self.recorder.on_recording_stopped = self._on_recording_stopped

        # Mixer (with recorder reference for master output recording)
        num_decks = self.config_manager.get_deck_count()
        self.mixer = Mixer(self.audio_engine, num_decks, self.recorder)
        self.mixer.on_deck_recording_started = self._on_deck_recording_started
        self.mixer.on_deck_recording_stopped = self._on_deck_recording_stopped

        # Load automation/crossfade settings
        self.mixer.auto_switch_interval = self.config_manager.getint('Automation', 'switch_interval', 10)
        self.mixer.crossfade_enabled = self.config_manager.getboolean('Automation', 'crossfade_enabled', True)
        self.mixer.crossfade_duration = self.config_manager.getfloat('Automation', 'crossfade_duration', 2.0)

        # Load level-based switching settings
        self.mixer.level_switch_enabled = self.config_manager.getboolean('Automation', 'level_switch_enabled', False)
        self.mixer.level_threshold_db = self.config_manager.getfloat('Automation', 'level_threshold_db', -30.0)
        self.mixer.level_hysteresis_db = self.config_manager.getfloat('Automation', 'level_hysteresis_db', 3.0)
        self.mixer.level_hold_time = self.config_manager.getfloat('Automation', 'level_hold_time', 3.0)

        # Theme manager
        self.theme_manager = ThemeManager(self.config_manager)
        self.theme_manager.register_callback(self._on_theme_changed)

        # UI components
        self.current_project_file = None
        self._project_modified = False  # Track unsaved changes

        # Create UI
        self._create_menu_bar()
        self._create_ui()
        self._create_status_bar()

        # Window settings
        self._apply_window_settings()

        # Apply theme after UI is created
        wx.CallAfter(self._apply_current_theme)

        # Setup keyboard shortcuts
        self._setup_keyboard_shortcuts()

        # Bind close event
        self.Bind(wx.EVT_CLOSE, self._on_close)

        # Setup callbacks
        self._setup_callbacks()

        # Position update timer (for slider during playback)
        self._position_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_position_timer, self._position_timer)
        self._position_timer.Start(250)  # Update 4x per second
        self._slider_dragging = False  # Track if user is dragging slider

    def _create_menu_bar(self):
        """Create menu bar"""
        menu_bar = wx.MenuBar()

        # File menu
        file_menu = wx.Menu()
        file_menu.Append(wx.ID_NEW, _("&New Project...") + "\tCtrl+N")
        file_menu.Append(wx.ID_OPEN, _("&Open Project...") + "\tCtrl+O")
        file_menu.Append(wx.ID_SAVE, _("&Save Project") + "\tCtrl+S")
        file_menu.Append(wx.ID_SAVEAS, _("Save Project &As...") + "\tCtrl+Shift+S")
        file_menu.AppendSeparator()

        self.import_m3u_item = file_menu.Append(wx.ID_ANY, _("&Import M3U Playlist...") + "\tCtrl+I")
        self.export_m3u_item = file_menu.Append(wx.ID_ANY, _("&Export M3U Playlist...") + "\tCtrl+E")

        file_menu.AppendSeparator()
        # Recent Files submenu
        self.recent_menu = wx.Menu()
        file_menu.AppendSubMenu(self.recent_menu, _("&Recent Files"))
        self._update_recent_files_menu()

        file_menu.AppendSeparator()
        file_menu.Append(wx.ID_EXIT, _("E&xit") + "\tAlt+F4")
        menu_bar.Append(file_menu, _("&File"))

        # View menu
        view_menu = wx.Menu()
        self.statusbar_item = view_menu.AppendCheckItem(wx.ID_ANY, _("&Status Bar") + "\tCtrl+T")
        self.statusbar_item.Check(True)
        self.level_meter_item = view_menu.AppendCheckItem(wx.ID_ANY, _("&Level Meter"))
        self.level_meter_item.Check(self.config_manager.getboolean('UI', 'show_level_meter', True))
        view_menu.AppendSeparator()
        self.theme_item = view_menu.Append(wx.ID_ANY, _("Toggle &Theme") + "\tCtrl+Shift+T")
        menu_bar.Append(view_menu, _("&View"))

        # Tools menu
        tools_menu = wx.Menu()
        self.record_menu_item = tools_menu.Append(wx.ID_ANY, _("Start &Recording") + "\tCtrl+R")
        tools_menu.AppendSeparator()
        self.effects_menu_item = tools_menu.Append(wx.ID_ANY, _("Audio &Effects...") + "\tCtrl+Shift+E")
        tools_menu.AppendSeparator()
        tools_menu.Append(wx.ID_PREFERENCES, _("&Options...") + "\tCtrl+P")
        menu_bar.Append(tools_menu, _("&Tools"))

        # Help menu
        help_menu = wx.Menu()
        help_menu.Append(wx.ID_HELP, _("&Keyboard Shortcuts") + "\tF1")
        help_menu.AppendSeparator()
        help_menu.Append(wx.ID_ABOUT, _("&About..."))
        menu_bar.Append(help_menu, _("&Help"))

        self.SetMenuBar(menu_bar)

        # Bind menu events
        self.Bind(wx.EVT_MENU, self._on_new_project, id=wx.ID_NEW)
        self.Bind(wx.EVT_MENU, self._on_open_project, id=wx.ID_OPEN)
        self.Bind(wx.EVT_MENU, self._on_save_project, id=wx.ID_SAVE)
        self.Bind(wx.EVT_MENU, self._on_save_project_as, id=wx.ID_SAVEAS)
        self.Bind(wx.EVT_MENU, self._on_import_m3u, self.import_m3u_item)
        self.Bind(wx.EVT_MENU, self._on_export_m3u, self.export_m3u_item)
        self.Bind(wx.EVT_MENU, self._on_exit, id=wx.ID_EXIT)
        self.Bind(wx.EVT_MENU, self._on_toggle_statusbar, self.statusbar_item)
        self.Bind(wx.EVT_MENU, self._on_toggle_level_meter, self.level_meter_item)
        self.Bind(wx.EVT_MENU, self._on_toggle_theme, self.theme_item)
        self.Bind(wx.EVT_MENU, self._on_toggle_recording, self.record_menu_item)
        self.Bind(wx.EVT_MENU, self._on_show_effects_dialog, self.effects_menu_item)
        self.Bind(wx.EVT_MENU, self._on_options, id=wx.ID_PREFERENCES)
        self.Bind(wx.EVT_MENU, self._on_help, id=wx.ID_HELP)
        self.Bind(wx.EVT_MENU, self._on_about, id=wx.ID_ABOUT)

    def _create_ui(self):
        """Create main UI"""
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Mixer controls at top
        mixer_panel = self._create_mixer_panel(panel)
        main_sizer.Add(mixer_panel, 0, wx.EXPAND | wx.ALL, 5)

        main_sizer.Add(wx.StaticLine(panel), 0, wx.EXPAND | wx.ALL, 5)

        # Active deck control panel with deck selection list
        active_deck_panel = self._create_active_deck_panel(panel)
        main_sizer.Add(active_deck_panel, 1, wx.EXPAND | wx.ALL, 5)

        panel.SetSizer(main_sizer)

        # Initialize deck list and select first deck
        self._update_deck_listbox()
        if self.deck_listbox.GetCount() > 0:
            self.deck_listbox.SetSelection(0)
            self._update_active_deck_controls()

    def _create_mixer_panel(self, parent):
        """Create mixer control panel"""
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Operating mode
        mode_panel = wx.Panel(panel)
        mode_panel_sizer = wx.BoxSizer(wx.VERTICAL)
        mode_box = wx.StaticBoxSizer(wx.VERTICAL, mode_panel, label=_("Operating Mode"))
        mode_static_box = mode_box.GetStaticBox()

        self.mixer_mode_radio = wx.RadioButton(mode_static_box, label=_("Mixer Mode") + "\tF3", style=wx.RB_GROUP)
        self.solo_mode_radio = wx.RadioButton(mode_static_box, label=_("Solo Mode") + "\tF4")
        self.auto_mode_radio = wx.RadioButton(mode_static_box, label=_("Automatic Mode") + "\tF5")

        self.mixer_mode_radio.SetValue(True)

        self.mixer_mode_radio.Bind(wx.EVT_RADIOBUTTON, lambda e: self._set_mode(MODE_MIXER))
        self.solo_mode_radio.Bind(wx.EVT_RADIOBUTTON, lambda e: self._set_mode(MODE_SOLO))
        self.auto_mode_radio.Bind(wx.EVT_RADIOBUTTON, lambda e: self._set_mode(MODE_AUTOMATIC))

        mode_box.Add(self.mixer_mode_radio, 0, wx.ALL, 5)
        mode_box.Add(self.solo_mode_radio, 0, wx.ALL, 5)
        mode_box.Add(self.auto_mode_radio, 0, wx.ALL, 5)

        mode_panel_sizer.Add(mode_box, 1, wx.EXPAND)
        mode_panel.SetSizer(mode_panel_sizer)
        sizer.Add(mode_panel, 0, wx.ALL, 5)

        # Global playback controls
        playback_panel = wx.Panel(panel)
        playback_panel_sizer = wx.BoxSizer(wx.VERTICAL)
        playback_box = wx.StaticBoxSizer(wx.VERTICAL, playback_panel, label=_("Global Playback"))
        playback_static_box = playback_box.GetStaticBox()

        button_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.global_play_pause_btn = wx.Button(playback_static_box, label=_("Play All"))
        self.global_play_pause_btn.SetToolTip(_("Play/Pause all decks"))
        self.global_play_pause_btn.Bind(wx.EVT_BUTTON, self._on_global_play_pause)
        button_sizer.Add(self.global_play_pause_btn, 0, wx.ALL, 5)

        self.global_stop_btn = wx.Button(playback_static_box, label=_("Stop All"))
        self.global_stop_btn.SetToolTip(_("Stop all decks and reset positions"))
        self.global_stop_btn.Bind(wx.EVT_BUTTON, self._on_global_stop)
        button_sizer.Add(self.global_stop_btn, 0, wx.ALL, 5)

        playback_box.Add(button_sizer, 0, wx.EXPAND)
        playback_panel_sizer.Add(playback_box, 1, wx.EXPAND)
        playback_panel.SetSizer(playback_panel_sizer)
        sizer.Add(playback_panel, 0, wx.ALL, 5)

        # Master volume
        volume_panel = wx.Panel(panel)
        volume_panel_sizer = wx.BoxSizer(wx.VERTICAL)
        volume_box = wx.StaticBoxSizer(wx.VERTICAL, volume_panel, label=_("Master Volume"))
        volume_static_box = volume_box.GetStaticBox()

        master_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.master_volume_slider = wx.Slider(
            volume_static_box, value=80, minValue=0, maxValue=100,
            style=wx.SL_HORIZONTAL
        )
        self.master_volume_slider.Bind(wx.EVT_SLIDER, self._on_master_volume_change)
        master_sizer.Add(self.master_volume_slider, 1, wx.EXPAND | wx.ALL, 5)

        volume_box.Add(master_sizer, 0, wx.EXPAND)
        volume_panel_sizer.Add(volume_box, 1, wx.EXPAND)
        volume_panel.SetSizer(volume_panel_sizer)
        sizer.Add(volume_panel, 1, wx.ALL | wx.EXPAND, 5)

        panel.SetSizer(sizer)
        return panel

    def _create_active_deck_panel(self, parent):
        """Create the active deck control panel with listbox and controls"""
        panel = wx.Panel(parent)
        main_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Left side: Deck listbox
        list_panel = wx.Panel(panel)
        list_panel.SetName(_("Deck Selection"))
        list_panel.SetLabel(_("Deck Selection"))
        list_panel_sizer = wx.BoxSizer(wx.VERTICAL)
        list_box = wx.StaticBoxSizer(wx.VERTICAL, list_panel, label=_("Deck Selection") + " (F6)")
        list_static_box = list_box.GetStaticBox()

        self.deck_listbox = wx.ListBox(list_static_box, style=wx.LB_SINGLE)
        self.deck_listbox.SetName(_("Deck Selection"))
        self.deck_listbox.SetLabel(_("Deck Selection"))
        self.deck_listbox.Bind(wx.EVT_LISTBOX, self._on_deck_listbox_select)
        self.deck_listbox.Bind(wx.EVT_CONTEXT_MENU, self._on_deck_context_menu)
        # Use CHAR_HOOK to intercept Enter before native ListBox processing
        self.deck_listbox.Bind(wx.EVT_CHAR_HOOK, self._on_deck_listbox_key)
        list_box.Add(self.deck_listbox, 1, wx.EXPAND | wx.ALL, 5)

        list_panel_sizer.Add(list_box, 1, wx.EXPAND)
        list_panel.SetSizer(list_panel_sizer)
        main_sizer.Add(list_panel, 1, wx.EXPAND | wx.ALL, 5)

        # Right side: Controls for active deck
        controls_panel = wx.Panel(panel)
        controls_panel_sizer = wx.BoxSizer(wx.VERTICAL)
        controls_box = wx.StaticBoxSizer(wx.VERTICAL, controls_panel, label=_("Active Deck Controls"))
        controls_static_box = controls_box.GetStaticBox()

        # Deck name/status display
        self.active_deck_label = wx.StaticText(controls_static_box, label=_("No deck selected"))
        font = self.active_deck_label.GetFont()
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.active_deck_label.SetFont(font)
        controls_box.Add(self.active_deck_label, 0, wx.ALL, 5)

        self.active_deck_status = wx.StaticText(controls_static_box, label="")
        controls_box.Add(self.active_deck_status, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)

        # Playback buttons
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.active_play_btn = wx.Button(controls_static_box, label=_("Play"))
        self.active_play_btn.SetName(_("Play"))
        self.active_play_btn.Bind(wx.EVT_BUTTON, self._on_active_play_pause)
        button_sizer.Add(self.active_play_btn, 1, wx.ALL, 5)

        self.active_stop_btn = wx.Button(controls_static_box, label=_("Stop"))
        self.active_stop_btn.SetName(_("Stop"))
        self.active_stop_btn.Bind(wx.EVT_BUTTON, self._on_active_stop)
        button_sizer.Add(self.active_stop_btn, 1, wx.ALL, 5)

        self.active_menu_btn = wx.Button(controls_static_box, label=_("Menu..."))
        self.active_menu_btn.SetName(_("Menu..."))
        self.active_menu_btn.Bind(wx.EVT_BUTTON, self._on_active_menu)
        button_sizer.Add(self.active_menu_btn, 1, wx.ALL, 5)

        controls_box.Add(button_sizer, 0, wx.EXPAND)

        # Volume slider
        volume_sizer = wx.BoxSizer(wx.HORIZONTAL)
        volume_label = wx.StaticText(controls_static_box, label=_("Volume") + ":")
        volume_sizer.Add(volume_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        self.active_volume_slider = wx.Slider(
            controls_static_box, value=100, minValue=0, maxValue=100,
            style=wx.SL_HORIZONTAL
        )
        self.active_volume_slider.SetName(_("Volume"))
        self.active_volume_slider.Bind(wx.EVT_SLIDER, self._on_active_volume_change)
        volume_sizer.Add(self.active_volume_slider, 1, wx.ALL | wx.EXPAND, 5)

        controls_box.Add(volume_sizer, 0, wx.EXPAND)

        # Balance slider
        balance_sizer = wx.BoxSizer(wx.HORIZONTAL)
        balance_label = wx.StaticText(controls_static_box, label=_("Balance") + ":")
        balance_sizer.Add(balance_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        self.active_balance_slider = wx.Slider(
            controls_static_box, value=0, minValue=-100, maxValue=100,
            style=wx.SL_HORIZONTAL
        )
        self.active_balance_slider.SetName(_("Balance"))
        self.active_balance_slider.Bind(wx.EVT_SLIDER, self._on_active_balance_change)
        balance_sizer.Add(self.active_balance_slider, 1, wx.ALL | wx.EXPAND, 5)

        controls_box.Add(balance_sizer, 0, wx.EXPAND)

        # Mute and Loop checkboxes
        checkbox_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.active_mute_cb = wx.CheckBox(controls_static_box, label=_("Mute"))
        self.active_mute_cb.SetName(_("Mute"))
        self.active_mute_cb.Bind(wx.EVT_CHECKBOX, self._on_active_mute_change)
        checkbox_sizer.Add(self.active_mute_cb, 0, wx.ALL, 5)

        self.active_loop_cb = wx.CheckBox(controls_static_box, label=_("Loop"))
        self.active_loop_cb.SetName(_("Loop"))
        self.active_loop_cb.Bind(wx.EVT_CHECKBOX, self._on_active_loop_change)
        checkbox_sizer.Add(self.active_loop_cb, 0, wx.ALL, 5)

        controls_box.Add(checkbox_sizer, 0)

        # Position/Seek slider (only for local files)
        position_panel = wx.Panel(controls_static_box)
        position_panel.SetLabel(_("Position"))
        position_panel.SetName(_("Position"))
        position_panel_sizer = wx.BoxSizer(wx.VERTICAL)
        position_box = wx.StaticBoxSizer(wx.VERTICAL, position_panel, label=_("Position"))
        position_static_box = position_box.GetStaticBox()

        # Time display
        time_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.active_position_label = wx.StaticText(position_static_box, label="0:00")
        self.active_position_label.SetName(_("Current position"))
        time_sizer.Add(self.active_position_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        time_sizer.AddStretchSpacer()

        self.active_duration_label = wx.StaticText(position_static_box, label="0:00")
        self.active_duration_label.SetName(_("Total duration"))
        time_sizer.Add(self.active_duration_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        position_box.Add(time_sizer, 0, wx.EXPAND)

        # Position slider
        self.active_position_slider = wx.Slider(
            position_static_box, value=0, minValue=0, maxValue=1000,
            style=wx.SL_HORIZONTAL
        )
        self.active_position_slider.SetName(_("Playback position"))
        self.active_position_slider.Bind(wx.EVT_SLIDER, self._on_active_position_change)
        self.active_position_slider.Bind(wx.EVT_LEFT_DOWN, self._on_position_slider_down)
        self.active_position_slider.Bind(wx.EVT_LEFT_UP, self._on_position_slider_up)
        position_box.Add(self.active_position_slider, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)

        position_panel_sizer.Add(position_box, 1, wx.EXPAND)
        position_panel.SetSizer(position_panel_sizer)
        controls_box.Add(position_panel, 0, wx.EXPAND | wx.TOP, 5)

        # Level meter
        level_panel = wx.Panel(controls_static_box)
        level_panel.SetLabel(_("Level"))
        level_panel.SetName(_("Level"))
        level_panel_sizer = wx.BoxSizer(wx.VERTICAL)
        level_box = wx.StaticBoxSizer(wx.HORIZONTAL, level_panel, label=_("Level"))
        level_static_box = level_box.GetStaticBox()

        self.active_level_bar = wx.Panel(level_static_box, size=(-1, 20))
        self.active_level_bar.SetMinSize((-1, 20))
        self.active_level_bar._value = 0  # 0-100
        self.active_level_bar.Bind(wx.EVT_PAINT, self._on_level_bar_paint)
        level_box.Add(self.active_level_bar, 1, wx.EXPAND | wx.ALL, 5)

        self.active_level_db_label = wx.StaticText(level_static_box, label="-inf dB")
        level_box.Add(self.active_level_db_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        self.level_box = level_box
        level_panel_sizer.Add(level_box, 1, wx.EXPAND)
        level_panel.SetSizer(level_panel_sizer)
        self.level_panel = level_panel
        show_level = self.config_manager.getboolean('UI', 'show_level_meter', True)
        if not show_level:
            level_panel.Hide()

        controls_box.Add(level_panel, 0, wx.EXPAND | wx.TOP, 5)

        controls_panel_sizer.Add(controls_box, 1, wx.EXPAND)
        controls_panel.SetSizer(controls_panel_sizer)
        main_sizer.Add(controls_panel, 2, wx.EXPAND | wx.ALL, 5)

        panel.SetSizer(main_sizer)
        return panel

    def _create_status_bar(self):
        """Create status bar"""
        self.statusbar = self.CreateStatusBar(3)
        self.statusbar.SetStatusWidths([-2, -2, -1])
        self.SetStatusText(_("Ready"), 0)
        self.SetStatusText(f"{_('Mode')}: {_('Mixer')}", 1)
        self.SetStatusText(f"{_('Master')}: 80%", 2)

    def _apply_window_settings(self):
        """Apply window settings from config"""
        width = self.config_manager.getint('UI', 'window_width', 1200)
        height = self.config_manager.getint('UI', 'window_height', 800)
        self.SetSize((width, height))

        # Center window
        self.Centre()

    def _setup_callbacks(self):
        """Setup mixer callbacks"""
        self.mixer.on_mode_change = self._on_mixer_mode_changed
        self.mixer.on_active_deck_change = self._on_active_deck_changed

    def _set_mode(self, mode):
        """Set mixer operating mode"""
        self.mixer.set_mode(mode)
        self._mark_project_modified()

    def _set_mode_with_ui(self, mode):
        """Set mixer operating mode and update radio buttons"""
        # Update radio button
        mode_radios = {
            MODE_MIXER: self.mixer_mode_radio,
            MODE_SOLO: self.solo_mode_radio,
            MODE_AUTOMATIC: self.auto_mode_radio,
        }
        if mode in mode_radios:
            mode_radios[mode].SetValue(True)
        # Set the mode
        self.mixer.set_mode(mode)
        self._mark_project_modified()

    def _on_mixer_mode_changed(self, old_mode, new_mode):
        """Handle mixer mode change"""
        mode_names = {
            MODE_MIXER: _("Mixer"),
            MODE_SOLO: _("Solo"),
            MODE_AUTOMATIC: _("Automatic"),
        }
        self.SetStatusText(f"{_('Mode')}: {mode_names.get(new_mode, new_mode)}", 1)

    def _on_active_deck_changed(self, old_index, new_index):
        """Handle active deck change (e.g., from automatic mode switching)"""
        # Use CallAfter since this may be called from background thread
        wx.CallAfter(self._update_active_deck_ui, new_index)

    def _update_active_deck_ui(self, deck_index):
        """Update UI to reflect the new active deck"""
        self._sync_listbox_selection(deck_index)
        if deck_index < len(self.mixer.decks):
            deck = self.mixer.decks[deck_index]
            self.SetStatusText(_("Active deck: {}").format(deck.name), 0)

    def _on_master_volume_change(self, event):
        """Handle master volume change"""
        volume = self.master_volume_slider.GetValue() / 100.0
        self.mixer.set_master_volume(volume)
        self.SetStatusText(f"{_('Master')}: {int(volume * 100)}%", 2)
        self._mark_project_modified()

    def _on_global_play_pause(self, event):
        """Handle global play/pause button"""
        self.mixer.toggle_play_pause_all()
        self._update_global_play_button()
        self._update_all_deck_panels()

    def _on_global_stop(self, event):
        """Handle global stop button"""
        self.mixer.stop_all()
        self._update_global_play_button()
        self._update_all_deck_panels()

    def _update_global_play_button(self):
        """Update global play/pause button label based on playback state"""
        if self.mixer.is_any_playing():
            self.global_play_pause_btn.SetLabel(_("Pause All"))
        else:
            self.global_play_pause_btn.SetLabel(_("Play All"))

    def _update_all_deck_panels(self):
        """Update UI to reflect current state of all decks"""
        self._update_deck_listbox()
        self._update_active_deck_controls()

    def _on_deck_play(self, deck):
        """Handle deck play request - preload audio to prevent underflow"""
        self.mixer.ensure_deck_loaded(deck)

    def _on_deck_load_file(self, deck):
        """Handle deck file loading"""
        dlg = wx.FileDialog(
            self,
            _("Choose an audio file"),
            wildcard="|".join([f"{name}|{pattern}" for name, pattern in SUPPORTED_FILE_FORMATS]),
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST
        )

        if dlg.ShowModal() == wx.ID_OK:
            filepath = dlg.GetPath()
            if deck.load_file(filepath):
                # Preload audio data to avoid stuttering on first playback
                self._preload_deck_audio(deck)
                self.SetStatusText(_("Loaded: {}").format(os.path.basename(filepath)), 0)
                self._update_deck_panel(deck.deck_id)
                # Add to recent files
                self.config_manager.add_recent_file(filepath)
                self._update_recent_files_menu()
                self._mark_project_modified()
            else:
                wx.MessageBox(_("Failed to load audio file"), _("Error"), wx.OK | wx.ICON_ERROR)

        dlg.Destroy()

    def _on_deck_load_url(self, deck):
        """Handle deck URL loading"""
        dlg = CustomTextEntryDialog(
            self,
            _("Enter stream URL:"),
            _("Load Stream"),
            default_value = "http://"
        )

        if dlg.ShowModal() == wx.ID_OK:
            url = dlg.GetValue().strip()
            if url:
                if deck.load_file(url):
                    self.SetStatusText(_("Loaded stream: {}").format(url), 0)
                    self._update_deck_panel(deck.deck_id)
                    # Add to recent files
                    self.config_manager.add_recent_file(url)
                    self._update_recent_files_menu()
                    self._mark_project_modified()
                else:
                    wx.MessageBox(_("Failed to load stream"), _("Error"), wx.OK | wx.ICON_ERROR)

        dlg.Destroy()

    def _update_deck_panel(self, deck_id):
        """Update UI for a specific deck"""
        # Update listbox to reflect changes
        self._update_deck_listbox()
        # Update active deck controls if this is the selected deck
        selection = self.deck_listbox.GetSelection()
        if selection != wx.NOT_FOUND and selection == deck_id - 1:
            self._update_active_deck_controls()

    def _update_deck_listbox(self):
        """Update deck listbox with current deck names and status"""
        current_selection = self.deck_listbox.GetSelection()
        self.deck_listbox.Clear()
        for i, deck in enumerate(self.mixer.decks):
            # Build display text: deck name + file info if loaded
            display_text = deck.name
            if deck.file_path:
                if deck.is_stream:
                    file_info = deck.file_path
                else:
                    file_info = os.path.basename(deck.file_path)
                display_text = f"{deck.name}: {file_info}"
            if self.mixer.is_deck_recording(deck.deck_id):
                display_text = f"[REC] {display_text}"
            self.deck_listbox.Append(display_text)
        # Restore selection
        if current_selection != wx.NOT_FOUND and current_selection < self.deck_listbox.GetCount():
            self.deck_listbox.SetSelection(current_selection)

    def _on_deck_listbox_select(self, event):
        """Handle deck listbox selection"""
        deck_index = self.deck_listbox.GetSelection()
        if deck_index != wx.NOT_FOUND:
            # Update mixer's active deck for Solo/Automatic mode
            self.mixer.set_active_deck(deck_index)
            # Update controls to show selected deck
            self._update_active_deck_controls()

    def _update_active_deck_controls(self):
        """Update the active deck control panel to reflect selected deck"""
        deck_index = self.deck_listbox.GetSelection()
        if deck_index == wx.NOT_FOUND or deck_index >= len(self.mixer.decks):
            self.active_deck_label.SetLabel(_("No deck selected"))
            self.active_deck_status.SetLabel("")
            self.active_play_btn.Enable(False)
            self.active_stop_btn.Enable(False)
            # Disable position slider
            self.active_position_slider.SetValue(0)
            self.active_position_slider.Enable(False)
            self.active_position_label.SetLabel("--:--")
            self.active_duration_label.SetLabel("--:--")
            return

        deck = self.mixer.decks[deck_index]

        # Update labels
        self.active_deck_label.SetLabel(deck.name)

        # Update status
        status_text = {
            DECK_STATE_EMPTY: _("Empty"),
            "loaded": _("Loaded"),
            DECK_STATE_PLAYING: _("Playing"),
            DECK_STATE_PAUSED: _("Paused"),
            "error": _("Error"),
        }.get(deck.state, deck.state)

        file_info = ""
        if deck.file_path:
            if deck.is_stream:
                file_info = deck.file_path
            else:
                file_info = os.path.basename(deck.file_path)
            status_text = f"{status_text} - {file_info}"

        self.active_deck_status.SetLabel(status_text)

        # Update play button
        if deck.is_playing:
            self.active_play_btn.SetLabel(_("Pause"))
            self.active_play_btn.SetName(_("Pause"))
        else:
            self.active_play_btn.SetLabel(_("Play"))
            self.active_play_btn.SetName(_("Play"))

        # Enable/disable controls based on state
        is_loaded = deck.state != DECK_STATE_EMPTY
        self.active_play_btn.Enable(is_loaded)
        self.active_stop_btn.Enable(is_loaded)

        # Update sliders
        self.active_volume_slider.SetValue(int(deck.volume * 100))
        self.active_balance_slider.SetValue(int(deck.balance * 100))

        # Update checkboxes
        self.active_mute_cb.SetValue(deck.mute)
        self.active_loop_cb.SetValue(deck.loop)

        # Update position slider and time display
        self._update_position_display(deck)

    def _get_selected_deck(self):
        """Get the currently selected deck from listbox"""
        deck_index = self.deck_listbox.GetSelection()
        if deck_index != wx.NOT_FOUND and deck_index < len(self.mixer.decks):
            return self.mixer.decks[deck_index]
        return None

    def _on_active_play_pause(self, event):
        """Handle play/pause for active deck"""
        deck = self._get_selected_deck()
        if deck and deck.state != "empty":
            # Preload audio before starting playback
            if not deck.is_playing:
                self.mixer.ensure_deck_loaded(deck)
            deck.toggle_play_pause()
            self._update_active_deck_controls()
            self._update_deck_panel(deck.deck_id)

    def _on_active_stop(self, event):
        """Handle stop for active deck"""
        deck = self._get_selected_deck()
        if deck:
            deck.stop()
            self._update_active_deck_controls()
            self._update_deck_panel(deck.deck_id)

    def _on_active_menu(self, event):
        """Show menu for active deck (from button)"""
        self._show_deck_context_menu(self.active_menu_btn)

    def _on_deck_listbox_key(self, event):
        """Handle key events in deck listbox for accessibility"""
        key = event.GetKeyCode()
        # Open context menu on Enter or Application/Menu key
        # This helps VoiceOver users on macOS who can't trigger EVT_CONTEXT_MENU
        if key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._show_deck_context_menu(self.deck_listbox)
            # Don't Skip() - we handled the event
        else:
            event.Skip()

    def _on_deck_context_menu(self, event):
        """Show context menu for deck listbox (right-click or Shift+F10)"""
        self._show_deck_context_menu(self.deck_listbox)

    def _show_deck_context_menu(self, parent_widget):
        """Show the deck context menu on the specified widget"""
        deck = self._get_selected_deck()
        if not deck:
            return

        menu = wx.Menu()
        load_file_item = menu.Append(wx.ID_ANY, _("Load File...") + "\tCtrl+F")
        load_url_item = menu.Append(wx.ID_ANY, _("Load URL...") + "\tCtrl+U")
        menu.AppendSeparator()

        rename_item = menu.Append(wx.ID_ANY, _("Rename Deck") + "...\tF2")
        menu.AppendSeparator()

        toggle_loop_item = menu.Append(wx.ID_ANY, _("Toggle Loop") + "\tCtrl+L")
        menu.AppendSeparator()

        unload_item = menu.Append(wx.ID_ANY, _("Unload Deck") + "\tDel")
        unload_item.Enable(deck.state != DECK_STATE_EMPTY)

        menu.AppendSeparator()
        if self.mixer.is_deck_recording(deck.deck_id):
            record_deck_item = menu.Append(wx.ID_ANY, _("Stop Recording Deck") + "\tCtrl+Shift+R")
        else:
            record_deck_item = menu.Append(wx.ID_ANY, _("Start Recording Deck") + "\tCtrl+Shift+R")
        record_deck_item.Enable(deck.state != DECK_STATE_EMPTY)

        self.Bind(wx.EVT_MENU, lambda e: self._on_deck_load_file(deck), load_file_item)
        self.Bind(wx.EVT_MENU, lambda e: self._on_deck_load_url(deck), load_url_item)
        self.Bind(wx.EVT_MENU, lambda e: self._on_active_rename(), rename_item)
        self.Bind(wx.EVT_MENU, lambda e: self._on_active_toggle_loop(), toggle_loop_item)
        self.Bind(wx.EVT_MENU, lambda e: self._on_active_unload(), unload_item)
        self.Bind(wx.EVT_MENU, lambda e: self._on_toggle_deck_recording(deck), record_deck_item)

        parent_widget.PopupMenu(menu)
        menu.Destroy()

    def _on_active_rename(self):
        """Rename the active deck"""
        deck = self._get_selected_deck()
        if not deck:
            return

        dlg = CustomTextEntryDialog(self, _("Enter new deck name:"), _("Rename Deck"), default_value = deck.name)
        if dlg.ShowModal() == wx.ID_OK:
            new_name = dlg.GetValue().strip()
            if new_name:
                deck.set_name(new_name)
                self._update_deck_listbox()
                self._update_active_deck_controls()
                self._update_deck_panel(deck.deck_id)
                self._mark_project_modified()
        dlg.Destroy()

    def _on_active_toggle_loop(self):
        """Toggle loop for active deck"""
        deck = self._get_selected_deck()
        if deck:
            deck.toggle_loop()
            self._update_active_deck_controls()
            self._update_deck_panel(deck.deck_id)

    def _on_active_unload(self):
        """Unload the active deck"""
        deck = self._get_selected_deck()
        if deck:
            if self.mixer.is_deck_recording(deck.deck_id):
                self.mixer.stop_deck_recording(deck.deck_id)
            deck.unload()
            self._update_active_deck_controls()
            self._update_deck_panel(deck.deck_id)
            self._mark_project_modified()

    def _on_active_volume_change(self, event):
        """Handle volume change for active deck"""
        deck = self._get_selected_deck()
        if deck:
            volume = self.active_volume_slider.GetValue() / 100.0
            deck.set_volume(volume)
            self._update_deck_panel(deck.deck_id)
            self._mark_project_modified()

    def _on_active_balance_change(self, event):
        """Handle balance change for active deck"""
        deck = self._get_selected_deck()
        if deck:
            balance = self.active_balance_slider.GetValue() / 100.0
            deck.set_balance(balance)
            self._update_deck_panel(deck.deck_id)
            self._mark_project_modified()

    def _on_active_mute_change(self, event):
        """Handle mute change for active deck"""
        deck = self._get_selected_deck()
        if deck:
            deck.set_mute(self.active_mute_cb.GetValue())
            self._update_deck_panel(deck.deck_id)
            self._mark_project_modified()

    def _on_active_loop_change(self, event):
        """Handle loop change for active deck"""
        deck = self._get_selected_deck()
        if deck:
            deck.set_loop(self.active_loop_cb.GetValue())
            self._update_deck_panel(deck.deck_id)
            self._mark_project_modified()

    def _on_active_position_change(self, event):
        """Handle position slider change for active deck"""
        if self._slider_dragging:
            return  # Don't seek while dragging, wait for mouse up

        deck = self._get_selected_deck()
        if deck and deck.can_seek():
            slider_value = self.active_position_slider.GetValue()
            duration = self.mixer.get_deck_duration_seconds(deck)
            if duration > 0:
                position_seconds = (slider_value / 1000.0) * duration
                deck.seek(position_seconds)
                self._update_position_display(deck)

    def _on_position_slider_down(self, event):
        """Handle mouse down on position slider"""
        self._slider_dragging = True
        event.Skip()

    def _on_position_slider_up(self, event):
        """Handle mouse up on position slider - perform seek"""
        self._slider_dragging = False
        event.Skip()

        # Now perform the seek
        deck = self._get_selected_deck()
        if deck and deck.can_seek():
            slider_value = self.active_position_slider.GetValue()
            duration = self.mixer.get_deck_duration_seconds(deck)
            if duration > 0:
                position_seconds = (slider_value / 1000.0) * duration
                deck.seek(position_seconds)
                self._update_position_display(deck)

    def _on_position_timer(self, event):
        """Timer callback to update position slider and level meter during playback"""
        if self._slider_dragging:
            return  # Don't update while user is dragging

        deck = self._get_selected_deck()
        if deck:
            if deck.is_playing and deck.can_seek():
                self._update_position_display(deck)
            self._update_level_meter(deck)

    def _update_position_display(self, deck):
        """Update position slider and time labels for a deck"""
        if not deck.can_seek():
            self.active_position_slider.SetValue(0)
            self.active_position_slider.Enable(False)
            self.active_position_label.SetLabel("--:--")
            self.active_duration_label.SetLabel("--:--")
            return

        duration = self.mixer.get_deck_duration_seconds(deck)
        position = deck.get_position_seconds()

        # Update time labels
        self.active_position_label.SetLabel(format_time(position))
        self.active_duration_label.SetLabel(format_time(duration))

        # Update slider
        if duration > 0:
            slider_value = int((position / duration) * 1000)
            self.active_position_slider.SetValue(slider_value)

        self.active_position_slider.Enable(True)

    def _update_level_meter(self, deck):
        """Update level meter bar and dB label for a deck"""
        if deck.is_playing:
            db = deck.rms_level_db
            db_text = f"{db:.1f} dB" if db > -59.0 else "-inf dB"
            self.active_level_db_label.SetLabel(db_text)
            new_value = int(max(0, min(100, ((db + 60.0) / 60.0) * 100)))
        else:
            self.active_level_db_label.SetLabel("-inf dB")
            new_value = 0

        if self.active_level_bar._value != new_value:
            self.active_level_bar._value = new_value
            self.active_level_bar.Refresh(eraseBackground=False)

    def _on_level_bar_paint(self, event):
        """Paint the visual level meter bar"""
        panel = event.GetEventObject()
        dc = wx.BufferedPaintDC(panel)
        w, h = panel.GetSize()

        # Background
        bg = panel.GetBackgroundColour()
        dc.SetBackground(wx.Brush(bg))
        dc.Clear()

        # Draw border
        dc.SetPen(wx.Pen(wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT), 1))
        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        dc.DrawRectangle(0, 0, w, h)

        # Draw filled portion
        value = panel._value
        if value > 0:
            fill_w = int((value / 100.0) * (w - 2))
            if fill_w > 0:
                # Green for normal levels, yellow above -12dB, red above -3dB
                if value > 95:  # roughly -3dB
                    color = wx.Colour(220, 50, 50)
                elif value > 80:  # roughly -12dB
                    color = wx.Colour(220, 180, 50)
                else:
                    color = wx.Colour(50, 180, 50)
                dc.SetPen(wx.TRANSPARENT_PEN)
                dc.SetBrush(wx.Brush(color))
                dc.DrawRectangle(1, 1, fill_w, h - 2)

    def _on_seek_forward(self, event):
        """Seek forward 5 seconds"""
        deck = self._get_selected_deck()
        if deck and deck.can_seek():
            deck.seek_relative(5.0)
            self._update_position_display(deck)
            self.SetStatusText(_("{}: {} / {}").format(
                deck.name,
                format_time(deck.get_position_seconds()),
                format_time(self.mixer.get_deck_duration_seconds(deck))
            ), 0)

    def _on_seek_backward(self, event):
        """Seek backward 5 seconds"""
        deck = self._get_selected_deck()
        if deck and deck.can_seek():
            deck.seek_relative(-5.0)
            self._update_position_display(deck)
            self.SetStatusText(_("{}: {} / {}").format(
                deck.name,
                format_time(deck.get_position_seconds()),
                format_time(self.mixer.get_deck_duration_seconds(deck))
            ), 0)

    def _on_seek_forward_large(self, event):
        """Seek forward 30 seconds"""
        deck = self._get_selected_deck()
        if deck and deck.can_seek():
            deck.seek_relative(30.0)
            self._update_position_display(deck)

    def _on_seek_backward_large(self, event):
        """Seek backward 30 seconds"""
        deck = self._get_selected_deck()
        if deck and deck.can_seek():
            deck.seek_relative(-30.0)
            self._update_position_display(deck)

    def _on_jump_to_time(self, event):
        """Show dialog to jump to specific timecode"""
        deck = self._get_selected_deck()
        if not deck or not deck.can_seek():
            wx.MessageBox(
                _("No seekable audio loaded in the selected deck."),
                _("Jump to Time"),
                wx.OK | wx.ICON_INFORMATION
            )
            return

        duration = self.mixer.get_deck_duration_seconds(deck)
        current_pos = format_time(deck.get_position_seconds())
        duration_str = format_time(duration)

        dlg = CustomTextEntryDialog(
            self,
            _("Enter time (M:SS or H:MM:SS):") + f"\n{_('Duration')}: {duration_str}",
            _("Jump to Time"),
            default_value = current_pos
        )

        if dlg.ShowModal() == wx.ID_OK:
            time_str = dlg.GetValue().strip()
            seconds = parse_time(time_str)

            if seconds is not None:
                # Clamp to valid range
                seconds = max(0, min(seconds, duration))
                deck.seek(seconds)
                self._update_position_display(deck)
                self.SetStatusText(_("{}: {} / {}").format(
                    deck.name,
                    format_time(seconds),
                    duration_str
                ), 0)
            else:
                wx.MessageBox(
                    _("Invalid time format. Use M:SS or H:MM:SS (e.g., 1:30 or 1:05:30)"),
                    _("Error"),
                    wx.OK | wx.ICON_ERROR
                )

        dlg.Destroy()

    def _on_jump_to_deck_list(self, event):
        """Handle F6 to jump to deck listbox"""
        self.deck_listbox.SetFocus()

    def _sync_listbox_selection(self, deck_index):
        """Sync listbox selection with mixer's active deck"""
        if deck_index < self.deck_listbox.GetCount():
            self.deck_listbox.SetSelection(deck_index)
            self._update_active_deck_controls()

    def _on_deck_info_changed(self, deck):
        """Handle deck info changes (name, loaded file, etc.)"""
        self._update_deck_listbox()
        # Update active controls if this deck is selected
        selection = self.deck_listbox.GetSelection()
        if selection != wx.NOT_FOUND and selection == deck.deck_id - 1:
            self._update_active_deck_controls()

    def _preload_deck_audio(self, deck):
        """Preload audio data for a deck to avoid stuttering on first playback"""
        if deck.file_path and not deck.is_stream:
            try:
                # Load audio file in background thread to avoid blocking UI
                import threading

                def load_audio():
                    result = self.audio_engine.load_audio_file(deck.file_path)
                    if result:
                        audio_data, sample_rate, channels = result
                        deck.audio_data = audio_data
                        deck.sample_rate = sample_rate
                        deck.channels = channels
                        # Cache in mixer
                        self.mixer._loaded_audio_cache[deck.deck_id] = audio_data

                thread = threading.Thread(target=load_audio, daemon=True)
                thread.start()
            except Exception as e:
                print(f"Error preloading audio: {e}")

    def _update_window_title(self):
        """Update window title to reflect project name and modified state"""
        title = f"{APP_NAME} v{APP_VERSION}"
        if self.current_project_file:
            project_name = os.path.basename(self.current_project_file)
            title = f"{APP_NAME} - {project_name}"
        if self._project_modified:
            title = f"{title} " + _("[Unsaved]")
        self.SetTitle(title)

    def _mark_project_modified(self):
        """Mark the project as having unsaved changes"""
        if not self._project_modified:
            self._project_modified = True
            self._update_window_title()

    def _clear_project_modified(self):
        """Clear the modified flag (after save, new, or load)"""
        self._project_modified = False
        self._update_window_title()

    def _check_unsaved_changes(self) -> bool:
        """Check for unsaved changes and prompt user if necessary.

        Returns True if safe to proceed, False if user cancelled.
        """
        if not self._project_modified:
            return True

        project_name = os.path.basename(self.current_project_file) if self.current_project_file else _("Untitled Project")

        dlg = wx.MessageDialog(
            self,
            _("Save changes to {}?").format(project_name),
            _("Unsaved Changes"),
            wx.YES_NO | wx.CANCEL | wx.ICON_QUESTION
        )
        dlg.SetYesNoCancelLabels(_("&Yes"), _("&No"), _("&Cancel"))
        result = dlg.ShowModal()
        dlg.Destroy()

        if result == wx.ID_YES:
            if self.current_project_file:
                self._save_project(self.current_project_file)
            else:
                # Save As dialog
                save_dlg = wx.FileDialog(self, _("Save Project As"), wildcard=PROJECT_FILE_FILTER,
                                         style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
                if save_dlg.ShowModal() == wx.ID_OK:
                    filepath = save_dlg.GetPath()
                    if not filepath.endswith('.mdap'):
                        filepath += '.mdap'
                    self._save_project(filepath)
                    self.current_project_file = filepath
                    save_dlg.Destroy()
                else:
                    save_dlg.Destroy()
                    return False  # Cancelled
            return True
        elif result == wx.ID_NO:
            return True  # Discard changes
        else:
            return False  # Cancelled

    def _reset_to_defaults(self):
        """Reset all mixer and deck settings to defaults"""
        # Stop all playback
        self.mixer.stop_all()

        # Unload all decks and reset their settings
        for i, deck in enumerate(self.mixer.decks):
            deck.unload()
            deck.set_volume(1.0)
            deck.set_balance(0.0)
            deck.set_mute(False)
            deck.set_loop(False)
            deck.set_name(f"Deck {i + 1}")
            self.mixer.clear_deck_cache(deck.deck_id)

        # Reset mixer to defaults from global config
        self.mixer.set_master_volume(0.8)
        self.mixer.set_mode(MODE_MIXER)
        self.mixer.active_deck_index = 0
        self.mixer.auto_switch_interval = self.config_manager.getint('Automation', 'switch_interval', 10)
        self.mixer.crossfade_enabled = self.config_manager.getboolean('Automation', 'crossfade_enabled', True)
        self.mixer.crossfade_duration = self.config_manager.getfloat('Automation', 'crossfade_duration', 2.0)
        self.mixer.level_switch_enabled = self.config_manager.getboolean('Automation', 'level_switch_enabled', False)
        self.mixer.level_threshold_db = self.config_manager.getfloat('Automation', 'level_threshold_db', -30.0)
        self.mixer.level_hysteresis_db = self.config_manager.getfloat('Automation', 'level_hysteresis_db', 3.0)
        self.mixer.level_hold_time = self.config_manager.getfloat('Automation', 'level_hold_time', 3.0)

        # Update UI
        self._update_mixer_ui()
        self._update_all_deck_panels()

    def _on_new_project(self, event):
        """Handle New Project menu action"""
        if not self._check_unsaved_changes():
            return

        self._reset_to_defaults()
        self.current_project_file = None
        self._clear_project_modified()
        self.SetStatusText(_("New project created"), 0)

    def _on_open_project(self, event):
        """Handle open project"""
        if not self._check_unsaved_changes():
            return

        dlg = wx.FileDialog(
            self,
            _("Open Project"),
            wildcard=PROJECT_FILE_FILTER,
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST
        )

        if dlg.ShowModal() == wx.ID_OK:
            filepath = dlg.GetPath()
            try:
                self._reset_to_defaults()
                project_data = ProjectManager.load_project(filepath)
                self._load_project_data(project_data)
                self.current_project_file = filepath
                self._clear_project_modified()
                self.SetStatusText(_("Opened: {}").format(os.path.basename(filepath)), 0)
            except Exception as e:
                wx.MessageBox(_("Failed to open project: {}").format(e), _("Error"), wx.OK | wx.ICON_ERROR)

        dlg.Destroy()

    def _on_save_project(self, event):
        """Handle save project"""
        if self.current_project_file:
            self._save_project(self.current_project_file)
        else:
            self._on_save_project_as(event)

    def _on_save_project_as(self, event):
        """Handle save project as"""
        dlg = wx.FileDialog(
            self,
            _("Save Project As"),
            wildcard=PROJECT_FILE_FILTER,
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
        )

        if dlg.ShowModal() == wx.ID_OK:
            filepath = dlg.GetPath()
            if not filepath.endswith('.mdap'):
                filepath += '.mdap'
            self._save_project(filepath)
            self.current_project_file = filepath
            self._update_window_title()

        dlg.Destroy()

    def _save_project(self, filepath):
        """Save project to file"""
        try:
            project_data = self._get_project_data()
            ProjectManager.save_project(filepath, project_data)
            self._clear_project_modified()
            self.SetStatusText(_("Saved: {}").format(os.path.basename(filepath)), 0)
        except Exception as e:
            wx.MessageBox(_("Failed to save project: {}").format(e), _("Error"), wx.OK | wx.ICON_ERROR)

    def _get_project_data(self):
        """Get current project data"""
        return {
            'mixer': self.mixer.to_dict(),
            'decks': [deck.to_dict() for deck in self.mixer.decks],
            'master_effects': self.mixer.get_master_effects_dict(),
            'deck_effects': [deck.get_effects_dict() for deck in self.mixer.decks],
        }

    def _load_project_data(self, project_data):
        """Load project data"""
        # Load mixer settings
        if 'mixer' in project_data:
            self.mixer.from_dict(project_data['mixer'])
            self._update_mixer_ui()

        # Load deck settings
        if 'decks' in project_data:
            for i, deck_data in enumerate(project_data['decks']):
                if i < len(self.mixer.decks) and deck_data:
                    self.mixer.decks[i].from_dict(deck_data)
                    self._update_deck_panel(i + 1)

        # Load effects settings
        if 'master_effects' in project_data and project_data['master_effects']:
            self.mixer.load_master_effects_dict(project_data['master_effects'])

        deck_effects = project_data.get('deck_effects', [])
        for i, fx_data in enumerate(deck_effects):
            if i < len(self.mixer.decks) and fx_data:
                self.mixer.decks[i].load_effects_dict(fx_data)

    def _update_mixer_ui(self):
        """Update mixer UI controls after loading project"""
        # Update radio buttons
        mode_radios = {
            MODE_MIXER: self.mixer_mode_radio,
            MODE_SOLO: self.solo_mode_radio,
            MODE_AUTOMATIC: self.auto_mode_radio,
        }
        if self.mixer.mode in mode_radios:
            mode_radios[self.mixer.mode].SetValue(True)

        # Update master volume slider
        self.master_volume_slider.SetValue(int(self.mixer.master_volume * 100))

        # Update status bar
        mode_names = {
            MODE_MIXER: _("Mixer"),
            MODE_SOLO: _("Solo"),
            MODE_AUTOMATIC: _("Automatic"),
        }
        self.SetStatusText(f"{_('Mode')}: {mode_names.get(self.mixer.mode, self.mixer.mode)}", 1)
        self.SetStatusText(f"{_('Master')}: {int(self.mixer.master_volume * 100)}%", 2)

        # Properly activate the mode (starts automatic switching thread if needed)
        loaded_mode = self.mixer.mode
        self.mixer.mode = MODE_MIXER  # Reset to trigger proper mode change
        self.mixer.set_mode(loaded_mode)

        if loaded_mode in [MODE_SOLO, MODE_AUTOMATIC]:
            self._sync_listbox_selection(self.mixer.active_deck_index)

    def _on_toggle_statusbar(self, event):
        """Toggle status bar visibility"""
        if self.statusbar_item.IsChecked():
            self.statusbar.Show()
        else:
            self.statusbar.Hide()
        self.Layout()

    def _on_toggle_level_meter(self, event):
        """Toggle level meter gauge visibility"""
        show = self.level_meter_item.IsChecked()
        if show:
            self.level_panel.Show()
        else:
            self.level_panel.Hide()
            self.active_level_bar._value = 0
        self.config_manager.set('UI', 'show_level_meter', show)
        self.config_manager.save()
        self.Layout()

    def _on_toggle_theme(self, event):
        """Toggle between light and dark theme"""
        self.theme_manager.toggle_theme()

    def _update_recent_files_menu(self):
        """Update the Recent Files submenu"""
        # Clear existing menu items
        for item in list(self.recent_menu.GetMenuItems()):
            self.recent_menu.Delete(item)

        # Get recent files from config
        recent_files = self.config_manager.get_recent_files()

        if recent_files:
            # Add menu items for each recent file
            for i, filepath in enumerate(recent_files):
                # Create a display name (filename or URL)
                if filepath.startswith('http://') or filepath.startswith('https://'):
                    display_name = filepath
                else:
                    display_name = os.path.basename(filepath)

                item_id = wx.NewIdRef()
                self.recent_menu.Append(item_id, f"&{i + 1}. {display_name}")
                self.Bind(wx.EVT_MENU, lambda e, path=filepath: self._on_recent_file(path), id=item_id)

            # Add separator and clear option
            self.recent_menu.AppendSeparator()

        # Add clear option (even if list is empty, for consistency)
        clear_id = wx.NewIdRef()
        clear_item = self.recent_menu.Append(clear_id, _("&Clear Recent Files"))
        clear_item.Enable(len(recent_files) > 0)
        self.Bind(wx.EVT_MENU, self._on_clear_recent_files, id=clear_id)

    def _on_recent_file(self, filepath):
        """Handle loading a file from the recent files list"""
        # Find the first empty deck or use the first deck
        target_deck = None
        for deck in self.mixer.decks:
            if not deck.file_path:
                target_deck = deck
                break

        if target_deck is None:
            # All decks are loaded, use the first deck
            target_deck = self.mixer.decks[0]

        # Check if it's a URL or file
        if filepath.startswith('http://') or filepath.startswith('https://'):
            if target_deck.load_file(filepath):
                self.SetStatusText(_("Loaded stream: {}").format(filepath), 0)
                self._update_deck_panel(target_deck.deck_id)
                # Move to top of recent files
                self.config_manager.add_recent_file(filepath)
                self._update_recent_files_menu()
                self._mark_project_modified()
            else:
                # Remove invalid entry
                self.config_manager.remove_recent_file(filepath)
                self._update_recent_files_menu()
                wx.MessageBox(_("Failed to load stream"), _("Error"), wx.OK | wx.ICON_ERROR)
        else:
            # Check if file exists
            if os.path.exists(filepath):
                if target_deck.load_file(filepath):
                    self._preload_deck_audio(target_deck)
                    self.SetStatusText(_("Loaded: {}").format(os.path.basename(filepath)), 0)
                    self._update_deck_panel(target_deck.deck_id)
                    # Move to top of recent files
                    self.config_manager.add_recent_file(filepath)
                    self._update_recent_files_menu()
                    self._mark_project_modified()
                else:
                    wx.MessageBox(_("Failed to load audio file"), _("Error"), wx.OK | wx.ICON_ERROR)
            else:
                # File doesn't exist, remove from recent list
                self.config_manager.remove_recent_file(filepath)
                self._update_recent_files_menu()
                wx.MessageBox(_("File not found. Removed from recent files."), _("Error"), wx.OK | wx.ICON_ERROR)

    def _on_clear_recent_files(self, event):
        """Clear the recent files list"""
        self.config_manager.clear_recent_files()
        self._update_recent_files_menu()
        self.SetStatusText(_("Recent files cleared"), 0)

    def _on_import_m3u(self, event):
        """Import M3U playlist into free decks"""
        dlg = wx.FileDialog(
            self,
            _("Import M3U Playlist"),
            wildcard="M3U Playlist (*.m3u;*.m3u8)|*.m3u;*.m3u8|" + _("All Files") + " (*.*)|*.*",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST
        )

        if dlg.ShowModal() == wx.ID_OK:
            m3u_path = dlg.GetPath()
            entries = self._parse_m3u_file(m3u_path)

            if not entries:
                wx.MessageBox(
                    _("No valid entries found in playlist."),
                    _("Import M3U"),
                    wx.OK | wx.ICON_INFORMATION
                )
                dlg.Destroy()
                return

            # Find free decks and load entries
            loaded_count = 0
            skipped_count = 0

            for entry in entries:
                # Find next free deck
                target_deck = None
                for deck in self.mixer.decks:
                    if not deck.file_path:
                        target_deck = deck
                        break

                if target_deck is None:
                    # No more free decks
                    skipped_count = len(entries) - loaded_count
                    break

                # Load entry into deck
                if target_deck.load_file(entry):
                    # Preload audio for local files
                    if not entry.startswith(('http://', 'https://')):
                        self._preload_deck_audio(target_deck)
                    self._update_deck_panel(target_deck.deck_id)
                    self.config_manager.add_recent_file(entry)
                    loaded_count += 1
                else:
                    skipped_count += 1

            # Update UI
            self._update_recent_files_menu()
            if loaded_count > 0:
                self._mark_project_modified()

            # Show result message
            if skipped_count > 0:
                msg = _("Imported {loaded} entries. {skipped} entries skipped (no free decks or load errors).").format(
                    loaded=loaded_count, skipped=skipped_count
                )
            else:
                msg = _("Imported {loaded} entries.").format(loaded=loaded_count)

            self.SetStatusText(msg, 0)

        dlg.Destroy()

    def _parse_m3u_file(self, m3u_path):
        """Parse M3U file and return list of file paths/URLs.

        Handles:
        - Extended M3U format (#EXTM3U, #EXTINF lines are ignored)
        - Relative and absolute paths
        - HTTP/HTTPS URLs
        - UTF-8 and Latin-1 encodings
        """
        entries = []
        m3u_dir = os.path.dirname(os.path.abspath(m3u_path))

        # Try UTF-8 first, then Latin-1
        content = None
        for encoding in ['utf-8', 'latin-1']:
            try:
                with open(m3u_path, 'r', encoding=encoding) as f:
                    content = f.read()
                break
            except UnicodeDecodeError:
                continue

        if content is None:
            return entries

        for line in content.splitlines():
            line = line.strip()

            # Skip empty lines and comments/extended info
            if not line or line.startswith('#'):
                continue

            # Check if it's a URL
            if line.startswith(('http://', 'https://')):
                entries.append(line)
            else:
                # Handle file path (could be relative or absolute)
                if os.path.isabs(line):
                    file_path = line
                else:
                    # Resolve relative path based on M3U file location
                    file_path = os.path.normpath(os.path.join(m3u_dir, line))

                # Only add if file exists
                if os.path.exists(file_path):
                    entries.append(file_path)

        return entries

    def _on_export_m3u(self, event):
        """Export loaded deck files/URLs to M3U playlist"""
        # Collect all loaded files/URLs from decks
        entries = []
        for deck in self.mixer.decks:
            if deck.file_path:
                entries.append(deck.file_path)

        if not entries:
            wx.MessageBox(
                _("No files loaded in any deck. Nothing to export."),
                _("Export M3U"),
                wx.OK | wx.ICON_INFORMATION
            )
            return

        # Show save dialog
        dlg = wx.FileDialog(
            self,
            _("Export M3U Playlist"),
            wildcard="M3U Playlist (*.m3u)|*.m3u|M3U8 Playlist (*.m3u8)|*.m3u8",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
        )

        if dlg.ShowModal() == wx.ID_OK:
            m3u_path = dlg.GetPath()

            # Ensure file has extension
            if not m3u_path.lower().endswith(('.m3u', '.m3u8')):
                m3u_path += '.m3u'

            try:
                with open(m3u_path, 'w', encoding='utf-8') as f:
                    f.write('#EXTM3U\n')
                    for entry in entries:
                        # Write EXTINF with deck name/filename
                        if entry.startswith(('http://', 'https://')):
                            name = entry
                        else:
                            name = os.path.basename(entry)
                        f.write(f'#EXTINF:-1,{name}\n')
                        f.write(f'{entry}\n')

                self.SetStatusText(_("Exported {count} entries to {file}").format(
                    count=len(entries),
                    file=os.path.basename(m3u_path)
                ), 0)

            except IOError as e:
                wx.MessageBox(
                    _("Failed to write playlist file: {}").format(str(e)),
                    _("Error"),
                    wx.OK | wx.ICON_ERROR
                )

        dlg.Destroy()

    def _on_theme_changed(self, theme_name):
        """Handle theme change callback"""
        self._apply_current_theme()

    def _apply_current_theme(self):
        """Apply the current theme to all windows"""
        self.theme_manager.apply_theme(self)
        self.Refresh()
        self.Update()

    def _on_show_effects_dialog(self, event):
        """Show modeless effects dialog (single instance)."""
        if hasattr(self, '_effects_dialog') and self._effects_dialog:
            self._effects_dialog.Raise()
            self._effects_dialog.SetFocus()
            return
        from gui.dialogs import EffectsDialog
        self._effects_dialog = EffectsDialog(self, self.mixer)
        self._effects_dialog.Show()

    def _on_options(self, event):
        """Show options dialog"""
        dlg = OptionsDialog(self, self.config_manager, self.theme_manager)
        # Remember current device setting before dialog opens
        old_device = self.config_manager.get('Audio', 'output_device', 'default')

        if dlg.ShowModal() == wx.ID_OK:
            applied = dlg._applied_sections

            # Apply sections that weren't already applied via per-tab Apply buttons
            if 'audio' not in applied:
                self.apply_audio_settings(old_device)
            if 'automation' not in applied:
                self.apply_automation_settings()
            if 'recorder' not in applied:
                self.apply_recorder_settings()
            if 'streaming' not in applied:
                self.apply_streaming_settings()

        dlg.Destroy()

    def apply_audio_settings(self, old_device):
        """Apply audio settings from config at runtime.

        Args:
            old_device: Previous device setting to compare against for hot-swap
        """
        new_device = self.config_manager.get('Audio', 'output_device', 'default')
        if new_device != old_device:
            self._apply_audio_device_change(new_device)

    def apply_automation_settings(self):
        """Apply automation settings from config to current mixer"""
        self.mixer.auto_switch_interval = self.config_manager.getint('Automation', 'switch_interval', 10)
        self.mixer.crossfade_enabled = self.config_manager.getboolean('Automation', 'crossfade_enabled', True)
        self.mixer.crossfade_duration = self.config_manager.getfloat('Automation', 'crossfade_duration', 2.0)
        self.mixer.level_switch_enabled = self.config_manager.getboolean('Automation', 'level_switch_enabled', False)
        self.mixer.level_threshold_db = self.config_manager.getfloat('Automation', 'level_threshold_db', -30.0)
        self.mixer.level_hysteresis_db = self.config_manager.getfloat('Automation', 'level_hysteresis_db', 3.0)
        self.mixer.level_hold_time = self.config_manager.getfloat('Automation', 'level_hold_time', 3.0)

    def apply_recorder_settings(self):
        """Apply recorder settings from config at runtime"""
        self.recorder.set_format(self.config_manager.get('Recorder', 'format', 'wav'))
        self.recorder.set_bitrate(self.config_manager.getint('Recorder', 'bitrate', 192))
        if not self.recorder.is_recording:
            self.recorder.bit_depth = self.config_manager.getint('Recorder', 'bit_depth', 16)
        self.recorder.set_pre_roll_seconds(self.config_manager.getfloat('Recorder', 'pre_roll_seconds', 30.0))
        # Update config for future per-deck recorders
        self.mixer.set_recorder_config(self._get_recorder_config())

    def apply_streaming_settings(self):
        """Apply streaming settings from config to all active stream handlers"""
        auto_reconnect = self.config_manager.getboolean('Streaming', 'auto_reconnect', True)
        reconnect_wait = self.config_manager.getint('Streaming', 'reconnect_wait', 5)
        for deck in self.mixer.decks:
            if deck.stream_handler:
                deck.stream_handler.set_reconnect_settings(auto_reconnect, reconnect_wait)

    def _apply_audio_device_change(self, new_device):
        """Apply audio device change at runtime without restart"""
        import threading

        def change_device():
            try:
                # Get the mixer's audio callback for stream restart
                callback = self.mixer._audio_callback if hasattr(self.mixer, '_audio_callback') else None

                success = self.audio_engine.set_device(new_device, callback)

                # Update GUI on main thread
                wx.CallAfter(self._on_device_change_complete, success)

            except Exception as e:
                wx.CallAfter(self._on_device_change_error, str(e))

        # Run device change in background thread to avoid blocking GUI
        thread = threading.Thread(target=change_device, daemon=True)
        thread.start()

        self.SetStatusText(_("Changing audio device..."), 0)

    def _on_device_change_complete(self, success):
        """Called when device change completes"""
        if success:
            self.SetStatusText(_("Audio device changed successfully"), 0)
        else:
            self.SetStatusText(_("Audio device change failed"), 0)
            wx.MessageBox(
                _("Failed to change audio device. The application will use the previous device."),
                _("Warning"),
                wx.OK | wx.ICON_WARNING
            )

    def _on_device_change_error(self, error_msg):
        """Called when device change fails with error"""
        self.SetStatusText(_("Audio device error"), 0)
        wx.MessageBox(
            _("Error changing audio device: {}").format(error_msg),
            _("Error"),
            wx.OK | wx.ICON_ERROR
        )

    def _on_help(self, event):
        """Show keyboard shortcuts"""
        shortcuts_file = Path(__file__).parent.parent.parent / 'docs' / 'shortcuts.txt'
        if shortcuts_file.exists():
            try:
                os.startfile(str(shortcuts_file))  # Windows
            except AttributeError:
                import subprocess
                subprocess.call(['xdg-open', str(shortcuts_file)])  # Linux
        else:
            wx.MessageBox(_("Shortcuts file not found"), _("Error"), wx.OK | wx.ICON_ERROR)

    def _on_about(self, event):
        """Show about dialog"""
        info = wx.adv.AboutDialogInfo()
        info.SetName(APP_NAME)
        info.SetVersion(APP_VERSION)
        info.SetDescription(_("Accessible cross-platform audio player for simultaneous playback"))
        info.SetWebSite(APP_WEBSITE, desc="M45.dev")
        info.SetCopyright("Copyright (C) " + APP_AUTHOR)
        info.SetLicense(APP_LICENSE)
        wx.adv.AboutBox(info)

    def _on_exit(self, event):
        """Handle exit"""
        self.Close()

    def _setup_keyboard_shortcuts(self):
        """Setup keyboard accelerators"""
        accel_entries = []

        # Ctrl+1 to Ctrl+0 for deck selection
        for i in range(1, 11):
            key = ord('0') if i == 10 else ord(str(i))
            accel_id = wx.NewIdRef()
            accel_entries.append(wx.AcceleratorEntry(wx.ACCEL_CTRL, key, accel_id))
            self.Bind(wx.EVT_MENU, lambda e, deck_idx=i-1: self._on_deck_shortcut(deck_idx), id=accel_id)

        # Ctrl+Tab / Ctrl+Shift+Tab for next/previous deck
        next_id = wx.NewIdRef()
        prev_id = wx.NewIdRef()
        accel_entries.append(wx.AcceleratorEntry(wx.ACCEL_CTRL, wx.WXK_TAB, next_id))
        accel_entries.append(wx.AcceleratorEntry(wx.ACCEL_CTRL | wx.ACCEL_SHIFT, wx.WXK_TAB, prev_id))
        self.Bind(wx.EVT_MENU, self._on_next_deck, id=next_id)
        self.Bind(wx.EVT_MENU, self._on_previous_deck, id=prev_id)

        # Note: Space key removed from global shortcuts to avoid interfering with UI controls
        # Space will work naturally when Play/Pause buttons have focus

        # F3/F4/F5 for mode selection
        mode_mixer_id = wx.NewIdRef()
        mode_solo_id = wx.NewIdRef()
        mode_auto_id = wx.NewIdRef()
        accel_entries.append(wx.AcceleratorEntry(wx.ACCEL_NORMAL, wx.WXK_F3, mode_mixer_id))
        accel_entries.append(wx.AcceleratorEntry(wx.ACCEL_NORMAL, wx.WXK_F4, mode_solo_id))
        accel_entries.append(wx.AcceleratorEntry(wx.ACCEL_NORMAL, wx.WXK_F5, mode_auto_id))
        self.Bind(wx.EVT_MENU, lambda e: self._set_mode_with_ui(MODE_MIXER), id=mode_mixer_id)
        self.Bind(wx.EVT_MENU, lambda e: self._set_mode_with_ui(MODE_SOLO), id=mode_solo_id)
        self.Bind(wx.EVT_MENU, lambda e: self._set_mode_with_ui(MODE_AUTOMATIC), id=mode_auto_id)

        # Ctrl+M for mute active deck
        mute_id = wx.NewIdRef()
        accel_entries.append(wx.AcceleratorEntry(wx.ACCEL_CTRL, ord('M'), mute_id))
        self.Bind(wx.EVT_MENU, self._on_mute_active_deck, id=mute_id)

        # Ctrl+L for loop active deck
        loop_id = wx.NewIdRef()
        accel_entries.append(wx.AcceleratorEntry(wx.ACCEL_CTRL, ord('L'), loop_id))
        self.Bind(wx.EVT_MENU, self._on_loop_active_deck, id=loop_id)

        # Ctrl+R for recorder toggle
        record_id = wx.NewIdRef()
        accel_entries.append(wx.AcceleratorEntry(wx.ACCEL_CTRL, ord('R'), record_id))
        self.Bind(wx.EVT_MENU, self._on_toggle_recording, id=record_id)

        # Ctrl+Shift+R for per-deck recording toggle
        deck_record_id = wx.NewIdRef()
        accel_entries.append(wx.AcceleratorEntry(wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord('R'), deck_record_id))
        self.Bind(wx.EVT_MENU, self._on_toggle_deck_recording_shortcut, id=deck_record_id)

        # F6 for jump to deck list (accessibility standard)
        jump_f6_id = wx.NewIdRef()
        accel_entries.append(wx.AcceleratorEntry(wx.ACCEL_NORMAL, wx.WXK_F6, jump_f6_id))
        self.Bind(wx.EVT_MENU, self._on_jump_to_deck_list, id=jump_f6_id)

        # Ctrl+F for load file
        load_file_id = wx.NewIdRef()
        accel_entries.append(wx.AcceleratorEntry(wx.ACCEL_CTRL, ord('F'), load_file_id))
        self.Bind(wx.EVT_MENU, self._on_shortcut_load_file, id=load_file_id)

        # Ctrl+U for load URL
        load_url_id = wx.NewIdRef()
        accel_entries.append(wx.AcceleratorEntry(wx.ACCEL_CTRL, ord('U'), load_url_id))
        self.Bind(wx.EVT_MENU, self._on_shortcut_load_url, id=load_url_id)

        # F2 for rename deck
        rename_id = wx.NewIdRef()
        accel_entries.append(wx.AcceleratorEntry(wx.ACCEL_NORMAL, wx.WXK_F2, rename_id))
        self.Bind(wx.EVT_MENU, self._on_shortcut_rename, id=rename_id)

        # Delete for unload deck
        unload_id = wx.NewIdRef()
        accel_entries.append(wx.AcceleratorEntry(wx.ACCEL_NORMAL, wx.WXK_DELETE, unload_id))
        self.Bind(wx.EVT_MENU, self._on_shortcut_unload, id=unload_id)

        # Ctrl+Up/Down for deck volume
        vol_up_id = wx.NewIdRef()
        vol_down_id = wx.NewIdRef()
        accel_entries.append(wx.AcceleratorEntry(wx.ACCEL_CTRL, wx.WXK_UP, vol_up_id))
        accel_entries.append(wx.AcceleratorEntry(wx.ACCEL_CTRL, wx.WXK_DOWN, vol_down_id))
        self.Bind(wx.EVT_MENU, lambda e: self._on_deck_volume_change(5), id=vol_up_id)
        self.Bind(wx.EVT_MENU, lambda e: self._on_deck_volume_change(-5), id=vol_down_id)

        # Ctrl+Left/Right for deck balance
        bal_left_id = wx.NewIdRef()
        bal_right_id = wx.NewIdRef()
        accel_entries.append(wx.AcceleratorEntry(wx.ACCEL_CTRL, wx.WXK_LEFT, bal_left_id))
        accel_entries.append(wx.AcceleratorEntry(wx.ACCEL_CTRL, wx.WXK_RIGHT, bal_right_id))
        self.Bind(wx.EVT_MENU, lambda e: self._on_deck_balance_change(-5), id=bal_left_id)
        self.Bind(wx.EVT_MENU, lambda e: self._on_deck_balance_change(5), id=bal_right_id)

        # Ctrl+Shift+Up/Down for master volume
        master_up_id = wx.NewIdRef()
        master_down_id = wx.NewIdRef()
        accel_entries.append(wx.AcceleratorEntry(wx.ACCEL_CTRL | wx.ACCEL_SHIFT, wx.WXK_UP, master_up_id))
        accel_entries.append(wx.AcceleratorEntry(wx.ACCEL_CTRL | wx.ACCEL_SHIFT, wx.WXK_DOWN, master_down_id))
        self.Bind(wx.EVT_MENU, lambda e: self._on_master_volume_shortcut(5), id=master_up_id)
        self.Bind(wx.EVT_MENU, lambda e: self._on_master_volume_shortcut(-5), id=master_down_id)

        # Alt+Left/Right for seek ±5 seconds
        seek_fwd_id = wx.NewIdRef()
        seek_bwd_id = wx.NewIdRef()
        accel_entries.append(wx.AcceleratorEntry(wx.ACCEL_ALT, wx.WXK_RIGHT, seek_fwd_id))
        accel_entries.append(wx.AcceleratorEntry(wx.ACCEL_ALT, wx.WXK_LEFT, seek_bwd_id))
        self.Bind(wx.EVT_MENU, self._on_seek_forward, id=seek_fwd_id)
        self.Bind(wx.EVT_MENU, self._on_seek_backward, id=seek_bwd_id)

        # Alt+Shift+Left/Right for seek ±30 seconds
        seek_fwd_large_id = wx.NewIdRef()
        seek_bwd_large_id = wx.NewIdRef()
        accel_entries.append(wx.AcceleratorEntry(wx.ACCEL_ALT | wx.ACCEL_SHIFT, wx.WXK_RIGHT, seek_fwd_large_id))
        accel_entries.append(wx.AcceleratorEntry(wx.ACCEL_ALT | wx.ACCEL_SHIFT, wx.WXK_LEFT, seek_bwd_large_id))
        self.Bind(wx.EVT_MENU, self._on_seek_forward_large, id=seek_fwd_large_id)
        self.Bind(wx.EVT_MENU, self._on_seek_backward_large, id=seek_bwd_large_id)

        # Ctrl+J for jump to time
        jump_time_id = wx.NewIdRef()
        accel_entries.append(wx.AcceleratorEntry(wx.ACCEL_CTRL, ord('J'), jump_time_id))
        self.Bind(wx.EVT_MENU, self._on_jump_to_time, id=jump_time_id)

        # Set accelerator table
        accel_table = wx.AcceleratorTable(accel_entries)
        self.SetAcceleratorTable(accel_table)

    def _on_deck_shortcut(self, deck_index):
        """Handle Ctrl+N deck shortcut"""
        if deck_index < len(self.mixer.decks):
            self.mixer.set_active_deck(deck_index)
            deck = self.mixer.decks[deck_index]
            self.SetStatusText(_("Active deck: {}").format(deck.name), 0)
            # Update deck listbox selection
            self._sync_listbox_selection(deck_index)

    def _on_next_deck(self, event):
        """Handle Ctrl+Tab for next deck"""
        self.mixer.next_deck()
        deck_index = self.mixer.active_deck_index
        self._sync_listbox_selection(deck_index)
        deck = self.mixer.decks[deck_index]
        self.SetStatusText(_("Active deck: {}").format(deck.name), 0)

    def _on_previous_deck(self, event):
        """Handle Ctrl+Shift+Tab for previous deck"""
        self.mixer.previous_deck()
        deck_index = self.mixer.active_deck_index
        self._sync_listbox_selection(deck_index)
        deck = self.mixer.decks[deck_index]
        self.SetStatusText(_("Active deck: {}").format(deck.name), 0)

    def _on_mute_active_deck(self, event):
        """Handle Ctrl+M for mute"""
        deck = self.mixer.get_deck(self.mixer.active_deck_index)
        if deck:
            deck.toggle_mute()
            self._update_deck_panel(deck.deck_id)

    def _on_loop_active_deck(self, event):
        """Handle Ctrl+L for loop"""
        deck = self.mixer.get_deck(self.mixer.active_deck_index)
        if deck:
            deck.toggle_loop()
            self._update_deck_panel(deck.deck_id)

    def _on_shortcut_load_file(self, event):
        """Handle Ctrl+F for load file"""
        deck = self._get_selected_deck()
        if deck:
            self._on_deck_load_file(deck)

    def _on_shortcut_load_url(self, event):
        """Handle Ctrl+Shift+F for load URL"""
        deck = self._get_selected_deck()
        if deck:
            self._on_deck_load_url(deck)

    def _on_shortcut_rename(self, event):
        """Handle F2 for rename deck"""
        self._on_active_rename()

    def _on_shortcut_unload(self, event):
        """Handle Del for unload deck"""
        deck = self._get_selected_deck()
        if deck and deck.state != DECK_STATE_EMPTY:
            self._on_active_unload()

    def _on_deck_volume_change(self, delta):
        """Handle Ctrl+Up/Down for deck volume change"""
        deck = self._get_selected_deck()
        if deck:
            current = int(deck.volume * 100)
            new_value = max(0, min(100, current + delta))
            deck.set_volume(new_value / 100.0)
            self.active_volume_slider.SetValue(new_value)
            self._update_deck_panel(deck.deck_id)
            self.SetStatusText(_("{}: Volume {}%").format(deck.name, new_value), 0)

    def _on_deck_balance_change(self, delta):
        """Handle Ctrl+Left/Right for deck balance change"""
        deck = self._get_selected_deck()
        if deck:
            current = int(deck.balance * 100)
            new_value = max(-100, min(100, current + delta))
            deck.set_balance(new_value / 100.0)
            self.active_balance_slider.SetValue(new_value)
            self._update_deck_panel(deck.deck_id)
            balance_text = _("Center") if new_value == 0 else (
                _("Left {}%").format(abs(new_value)) if new_value < 0 else _("Right {}%").format(new_value)
            )
            self.SetStatusText(_("{}: Balance {}").format(deck.name, balance_text), 0)

    def _on_master_volume_shortcut(self, delta):
        """Handle Ctrl+Shift+Up/Down for master volume change"""
        current = self.master_volume_slider.GetValue()
        new_value = max(0, min(100, current + delta))
        self.master_volume_slider.SetValue(new_value)
        self.mixer.set_master_volume(new_value / 100.0)
        self.SetStatusText(f"{_('Master')}: {new_value}%", 2)

    def _on_toggle_recording(self, event):
        """Handle Ctrl+R for recording toggle"""
        if self.recorder.is_recording:
            self.recorder.stop_recording()
        else:
            output_dir = self.config_manager.get('Recorder', 'output_directory', '')
            if not output_dir:
                # Ask user for output directory
                dlg = wx.DirDialog(self, _("Choose recording output directory"))
                if dlg.ShowModal() == wx.ID_OK:
                    output_dir = dlg.GetPath()
                else:
                    dlg.Destroy()
                    return
                dlg.Destroy()

            self.recorder.start_recording(output_directory=output_dir)

    def _on_recording_started(self, filepath):
        """Callback when recording starts"""
        self.SetStatusText(_("Recording: {}").format(os.path.basename(filepath)), 0)
        # Update menu item text
        self.record_menu_item.SetItemLabel(_("Stop &Recording") + "\tCtrl+R")

    def _on_recording_stopped(self, filepath, frames):
        """Callback when recording stops"""
        self.SetStatusText(_("Recording stopped: {}").format(os.path.basename(filepath)), 0)
        # Update menu item text
        self.record_menu_item.SetItemLabel(_("Start &Recording") + "\tCtrl+R")

    # --- Per-deck recording ---

    def _get_recorder_config(self) -> dict:
        """Build recorder config dict from current settings."""
        return {
            'sample_rate': self.audio_engine.sample_rate,
            'channels': 2,
            'bit_depth': self.config_manager.getint('Recorder', 'bit_depth', 16),
            'format': self.config_manager.get('Recorder', 'format', 'wav'),
            'bitrate': self.config_manager.getint('Recorder', 'bitrate', 192),
            'pre_roll_seconds': self.config_manager.getfloat('Recorder', 'pre_roll_seconds', 30.0),
        }

    def _on_toggle_deck_recording(self, deck):
        """Toggle recording for a specific deck."""
        if self.mixer.is_deck_recording(deck.deck_id):
            self.mixer.stop_deck_recording(deck.deck_id)
        else:
            output_dir = self.config_manager.get('Recorder', 'output_directory', '')
            if not output_dir:
                dlg = wx.DirDialog(self, _("Choose recording output directory"))
                if dlg.ShowModal() == wx.ID_OK:
                    output_dir = dlg.GetPath()
                else:
                    dlg.Destroy()
                    return
                dlg.Destroy()

            self.mixer.set_recorder_config(self._get_recorder_config())
            if not self.mixer.start_deck_recording(deck.deck_id, output_dir):
                wx.MessageBox(
                    _("Failed to start recording for {}").format(deck.name),
                    _("Error"),
                    wx.OK | wx.ICON_ERROR
                )

    def _on_toggle_deck_recording_shortcut(self, event):
        """Handle Ctrl+Shift+R for per-deck recording toggle."""
        deck = self._get_selected_deck()
        if deck and deck.state != DECK_STATE_EMPTY:
            self._on_toggle_deck_recording(deck)

    def _on_deck_recording_started(self, deck_id, filepath):
        """Callback when a deck recording starts (called from audio thread)."""
        wx.CallAfter(self._handle_deck_recording_started, deck_id, filepath)

    def _handle_deck_recording_started(self, deck_id, filepath):
        """Handle deck recording started on the GUI thread."""
        deck = self.mixer.get_deck_by_id(deck_id)
        deck_name = deck.name if deck else f"Deck {deck_id}"
        self.SetStatusText(_("Recording started: {}").format(f"{deck_name} → {os.path.basename(filepath)}"), 0)
        self._update_deck_listbox()

    def _on_deck_recording_stopped(self, deck_id, filepath, frames):
        """Callback when a deck recording stops (called from audio thread)."""
        wx.CallAfter(self._handle_deck_recording_stopped, deck_id, filepath, frames)

    def _handle_deck_recording_stopped(self, deck_id, filepath, frames):
        """Handle deck recording stopped on the GUI thread."""
        deck = self.mixer.get_deck_by_id(deck_id)
        deck_name = deck.name if deck else f"Deck {deck_id}"
        self.SetStatusText(_("Recording stopped: {}").format(f"{deck_name} → {os.path.basename(filepath)}"), 0)
        self._update_deck_listbox()

    def _on_close(self, event):
        """Handle window close"""
        # Check for unsaved changes
        if not self._check_unsaved_changes():
            event.Veto()
            return

        # Stop position timer
        if self._position_timer.IsRunning():
            self._position_timer.Stop()

        # Save window size
        width, height = self.GetSize()
        self.config_manager.set('UI', 'window_width', width)
        self.config_manager.set('UI', 'window_height', height)
        self.config_manager.save()

        # Cleanup
        self.mixer.cleanup()

        event.Skip()
