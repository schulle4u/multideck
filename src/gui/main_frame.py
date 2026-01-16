"""
Main Frame - Main application window
"""

import wx
import wx.adv
import os
from pathlib import Path

from gui.deck_panel import DeckPanel
from gui.dialogs import OptionsDialog
from gui.theme_manager import ThemeManager
from audio.audio_engine import AudioEngine
from audio.mixer import Mixer
from audio.recorder import Recorder
from config.config_manager import ConfigManager, ProjectManager
from config.defaults import (
    APP_NAME, APP_VERSION, SUPPORTED_FILE_FORMATS,
    PROJECT_FILE_FILTER, MODE_MIXER, MODE_SOLO, MODE_AUTOMATIC
)
from utils.i18n import _, get_i18n


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
        num_decks = self.config_manager.getint('General', 'deck_count', 10)
        self.mixer = Mixer(self.audio_engine, num_decks, self.recorder)

        # Load automation/crossfade settings
        self.mixer.auto_switch_interval = self.config_manager.getint('Automation', 'switch_interval', 10)
        self.mixer.crossfade_enabled = self.config_manager.getboolean('Automation', 'crossfade_enabled', True)
        self.mixer.crossfade_duration = self.config_manager.getfloat('Automation', 'crossfade_duration', 2.0)

        # Theme manager
        self.theme_manager = ThemeManager(self.config_manager)
        self.theme_manager.register_callback(self._on_theme_changed)

        # UI components
        self.deck_panels = []
        self.current_project_file = None

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

    def _create_menu_bar(self):
        """Create menu bar"""
        menu_bar = wx.MenuBar()

        # File menu
        file_menu = wx.Menu()
        file_menu.Append(wx.ID_OPEN, _("&Open Project...\tCtrl+O"))
        file_menu.Append(wx.ID_SAVE, _("&Save Project\tCtrl+S"))
        file_menu.Append(wx.ID_SAVEAS, _("Save Project &As..."))
        file_menu.AppendSeparator()

        # Recent Files submenu
        self.recent_menu = wx.Menu()
        file_menu.AppendSubMenu(self.recent_menu, _("&Recent Files"))
        self._update_recent_files_menu()

        file_menu.AppendSeparator()
        file_menu.Append(wx.ID_EXIT, _("E&xit\tAlt+F4"))
        menu_bar.Append(file_menu, _("&File"))

        # View menu
        view_menu = wx.Menu()
        self.statusbar_item = view_menu.AppendCheckItem(wx.ID_ANY, _("&Status Bar"))
        self.statusbar_item.Check(True)
        view_menu.AppendSeparator()
        self.theme_item = view_menu.Append(wx.ID_ANY, _("Toggle &Theme"))
        menu_bar.Append(view_menu, _("&View"))

        # Deck menu (for solo mode deck selection)
        self.deck_menu = wx.Menu()
        self.deck_menu_items = []
        num_decks = self.config_manager.getint('General', 'deck_count', 10)

        for i in range(num_decks):
            # Use Ctrl+1-9 and Ctrl+0 for deck 10
            if i < 9:
                shortcut = f"\tCtrl+{i + 1}"
            else:
                shortcut = "\tCtrl+0"

            deck_name = _("Deck") + f" {i + 1}"
            item_id = wx.NewIdRef()
            item = self.deck_menu.AppendRadioItem(item_id, f"{deck_name}{shortcut}")
            self.deck_menu_items.append(item)
            self.Bind(wx.EVT_MENU, lambda e, idx=i: self._on_deck_menu_select(idx), id=item_id)

        menu_bar.Append(self.deck_menu, _("&Deck"))

        # Tools menu
        tools_menu = wx.Menu()
        self.record_menu_item = tools_menu.Append(wx.ID_ANY, _("Start &Recording\tCtrl+R"))
        tools_menu.AppendSeparator()
        tools_menu.Append(wx.ID_PREFERENCES, _("&Options...\tCtrl+P"))
        menu_bar.Append(tools_menu, _("&Tools"))

        # Help menu
        help_menu = wx.Menu()
        help_menu.Append(wx.ID_HELP, _("&Keyboard Shortcuts\tF1"))
        help_menu.AppendSeparator()
        help_menu.Append(wx.ID_ABOUT, _("&About..."))
        menu_bar.Append(help_menu, _("&Help"))

        self.SetMenuBar(menu_bar)

        # Bind menu events
        self.Bind(wx.EVT_MENU, self._on_open_project, id=wx.ID_OPEN)
        self.Bind(wx.EVT_MENU, self._on_save_project, id=wx.ID_SAVE)
        self.Bind(wx.EVT_MENU, self._on_save_project_as, id=wx.ID_SAVEAS)
        self.Bind(wx.EVT_MENU, self._on_exit, id=wx.ID_EXIT)
        self.Bind(wx.EVT_MENU, self._on_toggle_statusbar, self.statusbar_item)
        self.Bind(wx.EVT_MENU, self._on_toggle_theme, self.theme_item)
        self.Bind(wx.EVT_MENU, self._on_toggle_recording, self.record_menu_item)
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

        # Scrolled window for deck panels
        scroll = wx.ScrolledWindow(panel)
        scroll.SetScrollRate(0, 20)

        deck_sizer = wx.BoxSizer(wx.VERTICAL)

        # Create deck panels
        for deck in self.mixer.decks:
            deck_panel = DeckPanel(scroll, deck)
            deck_panel.on_load_file = self._on_deck_load_file
            deck_panel.on_load_url = self._on_deck_load_url
            deck_panel.on_play = self._on_deck_play
            self.deck_panels.append(deck_panel)
            deck_sizer.Add(deck_panel, 0, wx.EXPAND | wx.ALL, 5)

        scroll.SetSizer(deck_sizer)
        main_sizer.Add(scroll, 1, wx.EXPAND | wx.ALL, 5)

        panel.SetSizer(main_sizer)

    def _create_mixer_panel(self, parent):
        """Create mixer control panel"""
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Operating mode
        mode_box = wx.StaticBoxSizer(wx.VERTICAL, panel, _("Operating Mode"))

        self.mixer_mode_radio = wx.RadioButton(panel, label=_("Mixer Mode"), style=wx.RB_GROUP)
        self.solo_mode_radio = wx.RadioButton(panel, label=_("Solo Mode"))
        self.auto_mode_radio = wx.RadioButton(panel, label=_("Automatic Mode"))

        self.mixer_mode_radio.SetValue(True)

        self.mixer_mode_radio.Bind(wx.EVT_RADIOBUTTON, lambda e: self._set_mode(MODE_MIXER))
        self.solo_mode_radio.Bind(wx.EVT_RADIOBUTTON, lambda e: self._set_mode(MODE_SOLO))
        self.auto_mode_radio.Bind(wx.EVT_RADIOBUTTON, lambda e: self._set_mode(MODE_AUTOMATIC))

        mode_box.Add(self.mixer_mode_radio, 0, wx.ALL, 5)
        mode_box.Add(self.solo_mode_radio, 0, wx.ALL, 5)
        mode_box.Add(self.auto_mode_radio, 0, wx.ALL, 5)

        sizer.Add(mode_box, 0, wx.ALL, 5)

        # Global playback controls
        playback_box = wx.StaticBoxSizer(wx.VERTICAL, panel, _("Global Playback"))

        button_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.global_play_pause_btn = wx.Button(panel, label=_("Play All"))
        self.global_play_pause_btn.SetToolTip(_("Play/Pause all decks"))
        self.global_play_pause_btn.Bind(wx.EVT_BUTTON, self._on_global_play_pause)
        button_sizer.Add(self.global_play_pause_btn, 0, wx.ALL, 5)

        self.global_stop_btn = wx.Button(panel, label=_("Stop All"))
        self.global_stop_btn.SetToolTip(_("Stop all decks and reset positions"))
        self.global_stop_btn.Bind(wx.EVT_BUTTON, self._on_global_stop)
        button_sizer.Add(self.global_stop_btn, 0, wx.ALL, 5)

        playback_box.Add(button_sizer, 0, wx.EXPAND)
        sizer.Add(playback_box, 0, wx.ALL, 5)

        # Master volume
        volume_box = wx.StaticBoxSizer(wx.VERTICAL, panel, _("Master Volume"))

        master_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.master_volume_slider = wx.Slider(
            panel, value=80, minValue=0, maxValue=100,
            style=wx.SL_HORIZONTAL
        )
        self.master_volume_slider.Bind(wx.EVT_SLIDER, self._on_master_volume_change)
        master_sizer.Add(self.master_volume_slider, 1, wx.EXPAND | wx.ALL, 5)

        volume_box.Add(master_sizer, 0, wx.EXPAND)
        sizer.Add(volume_box, 1, wx.ALL | wx.EXPAND, 5)

        panel.SetSizer(sizer)
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
        # Initialize deck menu state (disabled in mixer mode)
        self._update_deck_menu_state()

    def _set_mode(self, mode):
        """Set mixer operating mode"""
        self.mixer.set_mode(mode)

    def _on_mixer_mode_changed(self, old_mode, new_mode):
        """Handle mixer mode change"""
        mode_names = {
            MODE_MIXER: _("Mixer"),
            MODE_SOLO: _("Solo"),
            MODE_AUTOMATIC: _("Automatic"),
        }
        self.SetStatusText(f"{_('Mode')}: {mode_names.get(new_mode, new_mode)}", 1)
        # Update deck menu state
        self._update_deck_menu_state()
        # Update deck menu selection to current active deck
        if new_mode in [MODE_SOLO, MODE_AUTOMATIC]:
            self._update_deck_menu_selection(self.mixer.active_deck_index)

    def _on_master_volume_change(self, event):
        """Handle master volume change"""
        volume = self.master_volume_slider.GetValue() / 100.0
        self.mixer.set_master_volume(volume)
        self.SetStatusText(f"{_('Master')}: {int(volume * 100)}%", 2)

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
        """Update all deck panels to reflect current state"""
        for panel in self.deck_panels:
            panel.update()

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
            else:
                wx.MessageBox(_("Failed to load audio file"), _("Error"), wx.OK | wx.ICON_ERROR)

        dlg.Destroy()

    def _on_deck_load_url(self, deck):
        """Handle deck URL loading"""
        dlg = wx.TextEntryDialog(
            self,
            _("Enter stream URL:"),
            _("Load Stream"),
            "http://"
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
                else:
                    wx.MessageBox(_("Failed to load stream"), _("Error"), wx.OK | wx.ICON_ERROR)

        dlg.Destroy()

    def _update_deck_panel(self, deck_id):
        """Update specific deck panel"""
        if 1 <= deck_id <= len(self.deck_panels):
            self.deck_panels[deck_id - 1].update()

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

    def _on_open_project(self, event):
        """Handle open project"""
        dlg = wx.FileDialog(
            self,
            _("Open Project"),
            wildcard=PROJECT_FILE_FILTER,
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST
        )

        if dlg.ShowModal() == wx.ID_OK:
            filepath = dlg.GetPath()
            try:
                project_data = ProjectManager.load_project(filepath)
                self._load_project_data(project_data)
                self.current_project_file = filepath
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

        dlg.Destroy()

    def _save_project(self, filepath):
        """Save project to file"""
        try:
            project_data = self._get_project_data()
            ProjectManager.save_project(filepath, project_data)
            self.SetStatusText(_("Saved: {}").format(os.path.basename(filepath)), 0)
        except Exception as e:
            wx.MessageBox(_("Failed to save project: {}").format(e), _("Error"), wx.OK | wx.ICON_ERROR)

    def _get_project_data(self):
        """Get current project data"""
        return {
            'mixer': self.mixer.to_dict(),
            'decks': [deck.to_dict() for deck in self.mixer.decks],
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

    def _update_mixer_ui(self):
        """Update mixer UI controls"""
        mode_radios = {
            MODE_MIXER: self.mixer_mode_radio,
            MODE_SOLO: self.solo_mode_radio,
            MODE_AUTOMATIC: self.auto_mode_radio,
        }
        if self.mixer.mode in mode_radios:
            mode_radios[self.mixer.mode].SetValue(True)

        self.master_volume_slider.SetValue(int(self.mixer.master_volume * 100))

    def _on_toggle_statusbar(self, event):
        """Toggle status bar visibility"""
        if self.statusbar_item.IsChecked():
            self.statusbar.Show()
        else:
            self.statusbar.Hide()
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

    def _on_theme_changed(self, theme_name):
        """Handle theme change callback"""
        self._apply_current_theme()

    def _apply_current_theme(self):
        """Apply the current theme to all windows"""
        self.theme_manager.apply_theme(self)
        # Refresh all deck panels
        for panel in self.deck_panels:
            panel.Refresh()
        self.Refresh()
        self.Update()

    def _on_options(self, event):
        """Show options dialog"""
        dlg = OptionsDialog(self, self.config_manager, self.theme_manager)
        if dlg.ShowModal() == wx.ID_OK:
            # Reload recorder settings
            rec_format = self.config_manager.get('Recorder', 'format', 'wav')
            rec_bitrate = self.config_manager.getint('Recorder', 'bitrate', 192)
            self.recorder.set_format(rec_format)
            self.recorder.set_bitrate(rec_bitrate)

            # Reload automation settings
            self.mixer.auto_switch_interval = self.config_manager.getint('Automation', 'switch_interval', 10)
            self.mixer.crossfade_enabled = self.config_manager.getboolean('Automation', 'crossfade_enabled', True)
            self.mixer.crossfade_duration = self.config_manager.getfloat('Automation', 'crossfade_duration', 2.0)
        dlg.Destroy()

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
        info.SetWebSite("https://github.com/yourusername/multideck-audio-player")
        info.AddDeveloper("MultiDeck Audio Player Team")
        info.SetLicense("MIT License")
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

        # Set accelerator table
        accel_table = wx.AcceleratorTable(accel_entries)
        self.SetAcceleratorTable(accel_table)

    def _on_deck_shortcut(self, deck_index):
        """Handle Ctrl+N deck shortcut"""
        if deck_index < len(self.mixer.decks):
            self.mixer.set_active_deck(deck_index)
            deck = self.mixer.decks[deck_index]
            self.SetStatusText(_("Active deck: {}").format(deck.name), 0)
            # Update deck menu selection
            self._update_deck_menu_selection(deck_index)

    def _on_deck_menu_select(self, deck_index):
        """Handle deck selection from menu"""
        if deck_index < len(self.mixer.decks):
            self.mixer.set_active_deck(deck_index)
            deck = self.mixer.decks[deck_index]
            self.SetStatusText(_("Active deck: {}").format(deck.name), 0)

    def _update_deck_menu_selection(self, deck_index):
        """Update deck menu radio button selection"""
        if deck_index < len(self.deck_menu_items):
            self.deck_menu_items[deck_index].Check(True)

    def _update_deck_menu_state(self):
        """Enable/disable deck menu items based on mode"""
        is_solo_or_auto = self.mixer.mode in [MODE_SOLO, MODE_AUTOMATIC]
        for item in self.deck_menu_items:
            item.Enable(is_solo_or_auto)

    def _on_next_deck(self, event):
        """Handle Ctrl+Tab for next deck"""
        self.mixer.next_deck()
        self._update_deck_menu_selection(self.mixer.active_deck_index)
        deck = self.mixer.decks[self.mixer.active_deck_index]
        self.SetStatusText(_("Active deck: {}").format(deck.name), 0)

    def _on_previous_deck(self, event):
        """Handle Ctrl+Shift+Tab for previous deck"""
        self.mixer.previous_deck()
        self._update_deck_menu_selection(self.mixer.active_deck_index)
        deck = self.mixer.decks[self.mixer.active_deck_index]
        self.SetStatusText(_("Active deck: {}").format(deck.name), 0)

    def _on_mute_active_deck(self, event):
        """Handle Ctrl+M for mute"""
        if self.mixer.mode in [MODE_SOLO, MODE_AUTOMATIC]:
            deck = self.mixer.get_deck(self.mixer.active_deck_index)
            if deck:
                deck.toggle_mute()
                self._update_deck_panel(deck.deck_id)

    def _on_loop_active_deck(self, event):
        """Handle Ctrl+L for loop"""
        if self.mixer.mode in [MODE_SOLO, MODE_AUTOMATIC]:
            deck = self.mixer.get_deck(self.mixer.active_deck_index)
            if deck:
                deck.toggle_loop()
                self._update_deck_panel(deck.deck_id)

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
        self.record_menu_item.SetItemLabel(_("Stop &Recording\tCtrl+R"))

    def _on_recording_stopped(self, filepath, frames):
        """Callback when recording stops"""
        self.SetStatusText(_("Recording stopped: {}").format(os.path.basename(filepath)), 0)
        # Update menu item text
        self.record_menu_item.SetItemLabel(_("Start &Recording\tCtrl+R"))

    def _on_close(self, event):
        """Handle window close"""
        # Save window size
        width, height = self.GetSize()
        self.config_manager.set('UI', 'window_width', width)
        self.config_manager.set('UI', 'window_height', height)
        self.config_manager.save()

        # Cleanup
        self.mixer.cleanup()

        event.Skip()
