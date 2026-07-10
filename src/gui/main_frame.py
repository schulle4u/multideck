"""
Main Frame - Main application window
"""

import wx
import wx.adv
import os
import subprocess
import sys
import time
from pathlib import Path

from m45wxcontrols import CustomTextEntryDialog
from gui.menus import create_menu_bar
from gui.panels import create_active_deck_panel, create_mixer_panel
from gui.playlist_service import M3UPlaylistService
from gui.shortcuts import setup_keyboard_shortcuts
from gui.theme_manager import ThemeManager
from audio.audio_engine import AudioEngine
from audio.icecast_streamer import IcecastStreamer
from audio.mixer import Mixer
from audio.recorder import Recorder
from config.config_manager import ConfigManager, ProjectManager
from config.defaults import (
    APP_NAME, APP_VERSION, APP_CODE_NAME, APP_AUTHOR, APP_WEBSITE, APP_LICENSE,
    SUPPORTED_FILE_FORMATS, PROJECT_FILE_FILTER, MODE_MIXER, MODE_SOLO, MODE_AUTOMATIC, MODE_MULTIROOM,
    DECK_STATE_EMPTY, DECK_STATE_PLAYING, DECK_STATE_PAUSED, DECK_STATE_ERROR
)
from utils.i18n import _, get_i18n
from utils.helpers import format_time, parse_time
from utils.tts_manager import TTSManager


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

        self.streamer = IcecastStreamer(sample_rate=sample_rate, channels=2, config=self._get_streaming_config())
        self.streamer.on_streaming_started = self._on_streaming_started
        self.streamer.on_streaming_stopped = self._on_streaming_stopped
        self.streamer.on_error = self._on_streaming_error

        # Mixer (with recorder reference for master output recording)
        num_decks = self.config_manager.get_deck_count()
        self.mixer = Mixer(self.audio_engine, num_decks, self.recorder, self.streamer)
        self.mixer.on_deck_recording_started = self._on_deck_recording_started
        self.mixer.on_deck_recording_stopped = self._on_deck_recording_stopped
        self.mixer.on_routing_error = self._on_routing_error

        # Load automation/crossfade settings
        self.mixer.auto_switch_interval = self.config_manager.getint('Automation', 'switch_interval', 10)
        self.mixer.crossfade_enabled = self.config_manager.getboolean('Automation', 'crossfade_enabled', True)
        self.mixer.crossfade_duration = self.config_manager.getfloat('Automation', 'crossfade_duration', 2.0)

        # Load level-based switching settings
        self.mixer.level_switch_enabled = self.config_manager.getboolean('Automation', 'level_switch_enabled', False)
        self.mixer.level_threshold_db = self.config_manager.getfloat('Automation', 'level_threshold_db', -30.0)
        self.mixer.level_hysteresis_db = self.config_manager.getfloat('Automation', 'level_hysteresis_db', 3.0)
        self.mixer.level_hold_time = self.config_manager.getfloat('Automation', 'level_hold_time', 3.0)

        # TTS manager
        self.tts_manager = TTSManager()
        self.mixer.tts_manager = self.tts_manager
        self.apply_tts_settings()

        # Theme manager
        self.theme_manager = ThemeManager(self.config_manager)
        self.theme_manager.register_callback(self._on_theme_changed)

        # UI components
        self.current_project_file = None
        self._project_modified = False  # Track unsaved changes
        self.playlist_service = M3UPlaylistService(self)

        # Create UI
        self._create_menu_bar()
        self._create_ui()
        self._create_status_bar()
        self._update_streaming_ui()

        # Set initial focus to deck list after UI is fully built
        deck_list_focus = self.config_manager.getboolean('UI', 'deck_list_focus', True)
        if deck_list_focus:
            wx.CallAfter(self.deck_listbox.SetFocus)

        # Window settings
        self._apply_window_settings()

        # Apply theme after UI is created
        wx.CallAfter(self._apply_current_theme)

        # Setup keyboard shortcuts
        setup_keyboard_shortcuts(self)

        # Bind close event
        self.Bind(wx.EVT_CLOSE, self._on_close)

        # Setup callbacks
        self._setup_callbacks()

        if self.config_manager.getboolean('Streaming', 'connect_at_startup', False):
            wx.CallAfter(self._start_livestream, False)

        # Position update timer (for slider during playback)
        self._position_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_position_timer, self._position_timer)
        self._position_timer.Start(250)  # Update 4x per second
        self._slider_dragging = False  # Track if user is dragging slider

        # Sleep timer (one-shot timer configured from Tools > Sleep Timer)
        self._sleep_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_sleep_timer_elapsed, self._sleep_timer)
        self._sleep_timer_config = None
        self._sleep_timer_started_at = None

    def _create_menu_bar(self):
        """Create menu bar"""
        self.SetMenuBar(create_menu_bar(self))
        self._update_deck_menu_items()

    def _create_ui(self):
        """Create main UI"""
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Mixer controls at top
        mixer_panel = create_mixer_panel(self, panel)
        main_sizer.Add(mixer_panel, 0, wx.EXPAND | wx.ALL, 5)

        main_sizer.Add(wx.StaticLine(panel), 0, wx.EXPAND | wx.ALL, 5)

        # Active deck control panel with deck selection list
        active_deck_panel = create_active_deck_panel(self, panel)
        main_sizer.Add(active_deck_panel, 1, wx.EXPAND | wx.ALL, 5)

        panel.SetSizer(main_sizer)

        # Initialize deck list and select first deck
        self._update_deck_listbox()
        if self.deck_listbox.GetItemCount() > 0:
            self.deck_listbox.SelectRow(0)
            self._update_active_deck_controls()

    def _set_active_volume_value_label(self, value):
        """Update the text label that mirrors the volume slider value."""
        self.active_volume_value_label.SetLabel(f"{int(value)}%")

    def _set_active_balance_value_label(self, value):
        """Update the text label that mirrors the balance slider value."""
        value = int(value)
        if value == 0:
            label = _("Center")
        elif value < 0:
            label = _("Left {}%").format(abs(value))
        else:
            label = _("Right {}%").format(value)
        self.active_balance_value_label.SetLabel(label)

    def _wrap_active_deck_status(self):
        """Wrap the active deck status text to the available panel width."""
        if not hasattr(self, 'active_deck_status'):
            return

        width = self.active_deck_status.GetContainingSizer().GetSize().GetWidth()
        if width > 40:
            self.active_deck_status.Wrap(max(200, width - 10))

    def _on_active_controls_resize(self, event):
        """Keep the active deck status readable while the panel is resized."""
        self._wrap_active_deck_status()
        event.Skip()

    def _is_missing_local_deck_file(self, deck):
        """Return True when a deck points to a local file that no longer exists."""
        return (
            bool(deck.file_path)
            and not deck.is_stream
            and not deck.is_soundcard_input
            and not os.path.exists(deck.file_path)
        )

    def _mark_deck_file_missing(self, deck):
        """Move a deck with a missing local file into an error state."""
        if not self._is_missing_local_deck_file(deck):
            return False

        deck.is_playing = False
        deck.is_paused = False
        deck.audio_data = None
        if hasattr(self.mixer, '_loaded_audio_cache'):
            self.mixer._loaded_audio_cache.pop(deck.deck_id, None)
        if deck.state != DECK_STATE_ERROR:
            deck._set_state(DECK_STATE_ERROR)
        return True

    def _get_missing_file_status_message(self, deck):
        """Create a user-facing status message for a missing deck file."""
        filename = os.path.basename(deck.file_path) if deck.file_path else _("Unknown file")
        return _("Cannot play '{}': file not found ({})").format(deck.name, filename)

    def _show_deck_playback_error(self, deck, message):
        """Update all visible deck UI after a playback request fails."""
        self.SetStatusText(message, 0)
        self.tts_manager.speak(message)
        self._update_global_play_button()
        self._update_deck_panel(deck.deck_id)

    def _ensure_deck_ready_for_playback(self, deck):
        """Validate and preload a deck before starting playback."""
        if deck.state == DECK_STATE_EMPTY:
            self._show_deck_playback_error(deck, _("Deck is empty"))
            return False

        if self._mark_deck_file_missing(deck):
            self._show_deck_playback_error(deck, self._get_missing_file_status_message(deck))
            return False

        if not deck.is_playing and not self.mixer.ensure_deck_loaded(deck):
            if self._mark_deck_file_missing(deck):
                message = self._get_missing_file_status_message(deck)
            else:
                deck.is_playing = False
                deck.is_paused = False
                deck._set_state(DECK_STATE_ERROR)
                message = _("Cannot play '{}': audio could not be loaded").format(deck.name)
            self._show_deck_playback_error(deck, message)
            return False

        return True

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

    def _get_output_device_choices(self):
        """Get output-device labels/values for the active deck UI."""
        devices = self.audio_engine.get_available_devices()
        labels = [_("Use Global Default")]
        values = [None]
        for device in devices:
            labels.append(device.get('display_name', device['name']))
            values.append(device['index'])
        return labels, values, devices

    def _create_deck_output_device_menu(self, deck_getter=None, store_attr=None):
        """Create a deck output-device submenu."""
        deck_getter = deck_getter or self._get_selected_deck
        output_menu = wx.Menu()
        output_labels, output_values, output_devices = self._get_output_device_choices()
        deck = deck_getter()
        current_device_id = deck.output_device_id if deck else None
        output_device_items = []

        for idx, label in enumerate(output_labels):
            output_device_item = output_menu.AppendRadioItem(wx.ID_ANY, label)
            selected_device_id = output_values[idx]
            if selected_device_id == current_device_id or (selected_device_id is None and current_device_id is None):
                output_device_item.Check(True)

            def handle_output_change(event, device_id=selected_device_id):
                deck = deck_getter()
                if not deck:
                    return
                if device_id is None:
                    device_name = 'default'
                else:
                    matching = next((item for item in output_devices if item['index'] == device_id), None)
                    device_name = matching['name'] if matching else str(device_id)
                self._apply_deck_output_device(deck, device_id, device_name)

            self.Bind(wx.EVT_MENU, handle_output_change, output_device_item)
            output_device_items.append((output_device_item, selected_device_id))

        if store_attr:
            setattr(self, store_attr, output_device_items)

        return output_menu

    def _update_deck_output_device_menu_items(self):
        """Update main-menu output-device choices for the selected deck."""
        if not hasattr(self, 'deck_output_device_items'):
            return

        deck = self._get_selected_deck()
        has_deck = deck is not None
        current_device_id = deck.output_device_id if deck else None

        for item, device_id in self.deck_output_device_items:
            item.Enable(has_deck)
            if device_id == current_device_id or (device_id is None and current_device_id is None):
                item.Check(True)

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
            MODE_MULTIROOM: self.multiroom_mode_radio,
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
            MODE_MULTIROOM: _("Multiroom"),
        }
        self.SetStatusText(f"{_('Mode')}: {mode_names.get(new_mode, new_mode)}", 1)
        self.tts_manager.speak(mode_names.get(new_mode, new_mode))

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
        slider_value = self.master_volume_slider.GetValue()
        self._set_master_volume_value_label(slider_value)
        volume = slider_value / 100.0
        self.mixer.set_master_volume(volume)
        self.SetStatusText(f"{_('Master')}: {int(volume * 100)}%", 2)
        self._mark_project_modified()

    def _set_master_volume_value_label(self, value):
        """Update the text label that mirrors the master volume slider value."""
        self.master_volume_value_label.SetLabel(f"{int(value)}%")

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
        self._ensure_deck_ready_for_playback(deck)

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
                self.mixer.restart_multiroom_routing()
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
            default_value = "http://",
            ok_label=_("&OK"), cancel_label=_("&Cancel")
        )

        if dlg.ShowModal() == wx.ID_OK:
            url = dlg.GetValue().strip()
            if url:
                if deck.load_file(url):
                    self.SetStatusText(_("Loaded stream: {}").format(url), 0)
                    self._update_deck_panel(deck.deck_id)
                    self.mixer.restart_multiroom_routing()
                    # Add to recent files
                    self.config_manager.add_recent_file(url)
                    self._update_recent_files_menu()
                    self._mark_project_modified()
                else:
                    wx.MessageBox(_("Failed to load stream"), _("Error"), wx.OK | wx.ICON_ERROR)

        dlg.Destroy()

    def _on_deck_load_soundcard_input(self, deck):
        """Handle loading a sound card input device into a deck"""
        from gui.dialogs.sound_card_input import SoundCardInputDialog
        dlg = SoundCardInputDialog(self)

        if dlg.ShowModal() == wx.ID_OK:
            device = dlg.GetSelectedDevice()
            if device:
                if deck.load_soundcard_input(device['id'], device['name']):
                    self.SetStatusText(_("Loaded sound card input: {}").format(device['name']), 0)
                    self._update_deck_panel(deck.deck_id)
                    self.mixer.restart_multiroom_routing()
                    self._mark_project_modified()
                else:
                    wx.MessageBox(
                        _("Failed to open sound card input"),
                        _("Error"),
                        wx.OK | wx.ICON_ERROR
                    )

        dlg.Destroy()

    def _on_deck_set_intro_file(self, deck):
        """Handle selecting a switch-intro audio file for a deck."""
        dlg = wx.FileDialog(
            self,
            _("Choose an intro audio file"),
            wildcard="|".join([f"{name}|{pattern}" for name, pattern in SUPPORTED_FILE_FORMATS]),
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST
        )

        if dlg.ShowModal() == wx.ID_OK:
            intro_path = dlg.GetPath()
            deck.set_intro_file(intro_path)
            self.SetStatusText(_("Intro set for {}: {}").format(deck.name, os.path.basename(intro_path)), 0)
            self._update_deck_panel(deck.deck_id)
            self._mark_project_modified()

        dlg.Destroy()

    def _on_deck_clear_intro_file(self, deck):
        """Handle clearing the switch-intro audio file from a deck."""
        if not deck.intro_file:
            return

        deck.set_intro_file(None)
        self.SetStatusText(_("Intro cleared for {}").format(deck.name), 0)
        self._update_deck_panel(deck.deck_id)
        self._mark_project_modified()

    def _update_deck_panel(self, deck_id):
        """Update UI for a specific deck"""
        # Update listbox to reflect changes
        self._update_deck_listbox()
        # Update active deck controls if this is the selected deck
        selection = self.deck_listbox.GetSelectedRow()
        if selection != wx.NOT_FOUND and selection == deck_id - 1:
            self._update_active_deck_controls()

    def _update_deck_listbox(self):
        current_selection = self.deck_listbox.GetSelectedRow()
        self._updating_deck_listbox = True
        try:
            self.deck_listbox.DeleteAllItems()
            for i, deck in enumerate(self.mixer.decks):
                deck_name = deck.name
                missing_file = self._mark_deck_file_missing(deck)
                if deck.file_path:
                    if deck.is_soundcard_input:
                        file_info = _("[Input] {}").format(deck.soundcard_device_name)
                    elif deck.is_stream:
                        file_info = deck.file_path
                    else:
                        file_info = os.path.basename(deck.file_path)
                        if missing_file:
                            file_info = "{} ({})".format(file_info, _("File missing"))
                else:
                    file_info = ""

                output_label = (
                    deck.output_device_name
                    if deck.output_device_id is not None
                    else _("Main device")
                )

                status = ""
                if missing_file:
                    status = _("missing")
                elif deck.state == DECK_STATE_ERROR:
                    status = _("Error")
                elif deck.is_playing:
                    status = "▶"
                    if self.mixer.is_deck_recording(deck.deck_id):
                        status = f"{status} ⏺"
                elif deck.is_paused:
                    status = "⏸"
                elif deck.state != DECK_STATE_EMPTY:
                    status = "⏹"

                row_data = [deck.is_playing, status, deck_name, file_info, output_label]
                self.deck_listbox.Append(row_data)

            if current_selection != -1 and current_selection < self.deck_listbox.GetItemCount():
                self.deck_listbox.SelectRow(current_selection)
        finally:
            self._updating_deck_listbox = False

    def _on_deck_listbox_select(self, event):
        """Handle deck listbox selection"""
        deck_index = self.deck_listbox.GetSelectedRow()
        if deck_index != wx.NOT_FOUND:
            # Update mixer's active deck for Solo/Automatic mode
            self.mixer.set_active_deck(deck_index, trigger_switch_event=True)
            # Update controls to show selected deck
            self._update_active_deck_controls()

    def _on_deck_play_checked(self, event):
        """Start or stop the deck whose list checkbox/toggle changed."""
        if getattr(self, '_updating_deck_listbox', False):
            return

        deck_index = event.GetIndex()
        if deck_index == wx.NOT_FOUND or deck_index >= len(self.mixer.decks):
            return

        deck = self.mixer.decks[deck_index]
        checked = event.IsChecked()

        if checked:
            if not self._ensure_deck_ready_for_playback(deck):
                self._updating_deck_listbox = True
                try:
                    self.deck_listbox.SetChecked(deck_index, False)
                finally:
                    self._updating_deck_listbox = False
                return
            if not deck.is_playing:
                deck.play()
        else:
            deck.stop()

        self._update_global_play_button()
        self._update_deck_panel(deck.deck_id)

    def _update_active_deck_controls(self):
        """Update the active deck control panel to reflect selected deck"""
        deck_index = self.deck_listbox.GetSelectedRow()
        if deck_index == wx.NOT_FOUND or deck_index >= len(self.mixer.decks):
            self.active_deck_label.SetLabel(_("No deck selected"))
            self.active_deck_status.SetLabel("")
            self.active_play_btn.Enable(False)
            self.active_stop_btn.Enable(False)
            self.active_volume_slider.SetValue(100)
            self.active_balance_slider.SetValue(0)
            self._set_active_volume_value_label(100)
            self._set_active_balance_value_label(0)
            self.active_volume_slider.Enable(False)
            self.active_balance_slider.Enable(False)
            self.active_mute_cb.SetValue(False)
            self.active_loop_cb.SetValue(False)
            self.active_mute_cb.Enable(False)
            self.active_loop_cb.Enable(False)
            # Disable position slider
            self.active_position_slider.SetValue(0)
            self.active_position_slider.Enable(False)
            self.active_position_label.SetLabel("--:--")
            self.active_duration_label.SetLabel("--:--")
            self._wrap_active_deck_status()
            self._update_deck_menu_items()
            return
        deck = self.mixer.decks[deck_index]

        # Update labels
        self.active_deck_label.SetLabel(deck.name)

        # Update status
        missing_file = self._mark_deck_file_missing(deck)
        status_text = {
            DECK_STATE_EMPTY: _("Empty"),
            "loaded": _("Loaded"),
            DECK_STATE_PLAYING: _("Playing"),
            DECK_STATE_PAUSED: _("Paused"),
            DECK_STATE_ERROR: _("Error"),
        }.get(deck.state, deck.state)

        file_info = ""
        if deck.file_path:
            if deck.is_stream:
                file_info = deck.file_path
            else:
                file_info = os.path.basename(deck.file_path)
            status_text = f"{status_text} - {file_info}"

        if missing_file:
            status_text = _("Error - file not found: {}").format(file_info or _("Unknown file"))
            if deck.file_path:
                status_text = f"{status_text}\n{deck.file_path}"

        if deck.intro_file:
            status_text = f"{status_text}\n{_('Intro')}: {os.path.basename(deck.intro_file)}"

        self.active_deck_status.SetLabel(status_text)
        self._wrap_active_deck_status()

        # Update play button
        if deck.is_playing:
            self.active_play_btn.SetLabel(_("Pause"))
            self.active_play_btn.SetName(_("Pause"))
        else:
            self.active_play_btn.SetLabel(_("Play"))
            self.active_play_btn.SetName(_("Play"))

        # Enable/disable controls based on state
        is_loaded = deck.state != DECK_STATE_EMPTY and not missing_file
        self.active_play_btn.Enable(is_loaded)
        self.active_stop_btn.Enable(is_loaded)
        self.active_volume_slider.Enable(True)
        self.active_balance_slider.Enable(True)
        self.active_mute_cb.Enable(True)
        self.active_loop_cb.Enable(True)

        # Update sliders
        volume_value = int(deck.volume * 100)
        balance_value = int(deck.balance * 100)
        self.active_volume_slider.SetValue(volume_value)
        self.active_balance_slider.SetValue(balance_value)
        self._set_active_volume_value_label(volume_value)
        self._set_active_balance_value_label(balance_value)

        # Update checkboxes
        self.active_mute_cb.SetValue(deck.mute)
        self.active_loop_cb.SetValue(deck.loop)

        # Update position slider and time display
        self._update_position_display(deck)
        self._update_deck_menu_items()

    def _get_selected_deck(self):
        """Get the currently selected deck from listbox"""
        if not hasattr(self, 'deck_listbox'):
            return None
        deck_index = self.deck_listbox.GetSelectedRow()
        if deck_index != wx.NOT_FOUND and deck_index < len(self.mixer.decks):
            return self.mixer.decks[deck_index]
        return None

    def _update_deck_menu_items(self):
        """Update main-menu deck items to reflect current selection/state."""
        if not hasattr(self, 'unload_item'):
            return

        deck = self._get_selected_deck()
        has_deck = deck is not None
        is_loaded = has_deck and deck.state != DECK_STATE_EMPTY
        can_record = is_loaded and not self._is_missing_local_deck_file(deck)
        is_recording = has_deck and self.mixer.is_deck_recording(deck.deck_id)

        self.load_file_item.Enable(has_deck)
        self.load_url_item.Enable(has_deck)
        self.load_input_item.Enable(has_deck)
        self.set_intro_item.Enable(has_deck)
        self.clear_intro_item.Enable(has_deck and bool(deck.intro_file))
        self.rename_item.Enable(has_deck)
        self.unload_item.Enable(is_loaded)
        self.record_deck_menu_item.Enable(can_record)
        self._update_deck_output_device_menu_items()
        if is_recording:
            self.record_deck_menu_item.SetItemLabel(_("Stop Recording Deck") + "\tCtrl+Shift+R")
        else:
            self.record_deck_menu_item.SetItemLabel(_("Start Recording Deck") + "\tCtrl+Shift+R")

    def _update_streaming_ui(self):
        """Update only the UI elements that control the master livestream."""
        self._update_livestream_control()
        self._update_stream_menu_item()

    def _update_livestream_control(self):
        """Update the global livestream checkbox state."""
        if not hasattr(self, 'active_stream_cb'):
            return
        self.active_stream_cb.SetValue(self.streamer.is_streaming)
        self.active_stream_cb.Enable(self._can_start_livestream())

    def _update_stream_menu_item(self):
        """Update the Tools menu entry for the master livestream."""
        if not hasattr(self, 'stream_menu_item'):
            return
        stream_label = _("Stop Livestream") + "\tF8" if self.streamer.is_streaming else _("Start Livestream") + "\tF8"
        self.stream_menu_item.SetItemLabel(stream_label)
        self.stream_menu_item.Enable(self._can_start_livestream())

    def _on_menu_open(self, event):
        """Refresh menu state just before a menu is shown."""
        if hasattr(self, 'deck_menu') and event.GetMenu() is self.deck_menu:
            self._update_deck_menu_items()
        if hasattr(self, 'stream_menu_item'):
            tools_menu = self.stream_menu_item.GetMenu()
            if tools_menu and event.GetMenu() is tools_menu:
                self._update_streaming_ui()
        event.Skip()

    def _on_selected_deck_load_file(self, event):
        """Load a file into the currently selected deck from the main menu."""
        deck = self._get_selected_deck()
        if deck:
            self._on_deck_load_file(deck)

    def _on_selected_deck_load_url(self, event):
        """Load a stream URL into the currently selected deck from the main menu."""
        deck = self._get_selected_deck()
        if deck:
            self._on_deck_load_url(deck)

    def _on_selected_deck_load_soundcard_input(self, event):
        """Load a sound card input into the currently selected deck from the main menu."""
        deck = self._get_selected_deck()
        if deck:
            self._on_deck_load_soundcard_input(deck)

    def _on_selected_deck_set_intro_file(self, event):
        """Set the intro file for the currently selected deck from the main menu."""
        deck = self._get_selected_deck()
        if deck:
            self._on_deck_set_intro_file(deck)

    def _on_selected_deck_clear_intro_file(self, event):
        """Clear the intro file for the currently selected deck from the main menu."""
        deck = self._get_selected_deck()
        if deck:
            self._on_deck_clear_intro_file(deck)

    def _on_selected_deck_toggle_recording(self, event):
        """Toggle recording for the currently selected deck from the main menu."""
        deck = self._get_selected_deck()
        if deck and deck.state != DECK_STATE_EMPTY:
            self._on_toggle_deck_recording(deck)

    def _on_active_play_pause(self, event):
        """Handle play/pause for active deck"""
        deck = self._get_selected_deck()
        if deck and deck.state != "empty":
            # Preload audio before starting playback
            if not deck.is_playing and not self._ensure_deck_ready_for_playback(deck):
                return
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

    def _apply_deck_output_device(self, deck, device_id, device_name=None):
        """Apply output-device changes for a deck."""
        if device_id is None:
            device_name = 'default'

        self.mixer.set_deck_output_device(deck.deck_id, device_id, device_name)
        self.SetStatusText(_("Output device updated for {}").format(deck.name), 0)
        self._update_deck_panel(deck.deck_id)
        self._mark_project_modified()

    def _on_deck_listbox_key(self, event):
        """Handle key events in deck listbox for accessibility"""
        key = event.GetKeyCode()
        # Open context menu on Enter or Application/Menu key
        # This helps VoiceOver users on macOS who can't trigger EVT_CONTEXT_MENU
        if key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._show_deck_context_menu(self.deck_listbox.control)
            # Don't Skip() - we handled the event
        else:
            event.Skip()

    def _on_deck_context_menu(self, event):
        """Show context menu for deck listbox (right-click or Shift+F10)"""
        self._show_deck_context_menu(self.deck_listbox.control)

    def _show_deck_context_menu(self, parent_widget):
        """Show the deck context menu on the specified widget"""
        deck = self._get_selected_deck()
        if not deck:
            return

        menu = wx.Menu()
        load_file_item = menu.Append(wx.ID_ANY, _("Load File") + "...\tCtrl+F")
        load_url_item = menu.Append(wx.ID_ANY, _("Load URL") + "...\tCtrl+U")
        load_input_item = menu.Append(wx.ID_ANY, _("Load sound card input") + "...\tCtrl+D")
        menu.AppendSeparator()
        set_intro_item = menu.Append(wx.ID_ANY, _("Set Intro File") + "...")
        clear_intro_item = menu.Append(wx.ID_ANY, _("Clear Intro File"))
        clear_intro_item.Enable(bool(deck.intro_file))
        output_menu = self._create_deck_output_device_menu(lambda: deck)
        menu.AppendSubMenu(output_menu, _("Output Device"))
        menu.AppendSeparator()

        rename_item = menu.Append(wx.ID_ANY, _("Rename Deck") + "...\tF2")
        unload_item = menu.Append(wx.ID_ANY, _("Unload Deck") + "\tDel")
        unload_item.Enable(deck.state != DECK_STATE_EMPTY)
        can_record = deck.state != DECK_STATE_EMPTY and not self._is_missing_local_deck_file(deck)

        menu.AppendSeparator()
        if self.mixer.is_deck_recording(deck.deck_id):
            record_deck_item = menu.Append(wx.ID_ANY, _("Stop Recording Deck") + "\tCtrl+Shift+R")
        else:
            record_deck_item = menu.Append(wx.ID_ANY, _("Start Recording Deck") + "\tCtrl+Shift+R")
        record_deck_item.Enable(can_record)

        self.Bind(wx.EVT_MENU, lambda e: self._on_deck_load_file(deck), load_file_item)
        self.Bind(wx.EVT_MENU, lambda e: self._on_deck_load_url(deck), load_url_item)
        self.Bind(wx.EVT_MENU, lambda e: self._on_deck_load_soundcard_input(deck), load_input_item)
        self.Bind(wx.EVT_MENU, lambda e: self._on_deck_set_intro_file(deck), set_intro_item)
        self.Bind(wx.EVT_MENU, lambda e: self._on_deck_clear_intro_file(deck), clear_intro_item)
        self.Bind(wx.EVT_MENU, lambda e: self._on_active_rename(), rename_item)
        self.Bind(wx.EVT_MENU, lambda e: self._on_active_unload(), unload_item)
        self.Bind(wx.EVT_MENU, lambda e: self._on_toggle_deck_recording(deck), record_deck_item)

        parent_widget.PopupMenu(menu)
        menu.Destroy()

    def _on_active_rename(self):
        """Rename the active deck"""
        deck = self._get_selected_deck()
        if not deck:
            return

        dlg = CustomTextEntryDialog(self, _("Enter new deck name:"), _("Rename Deck"), default_value = deck.name, ok_label=_("&OK"), cancel_label=_("&Cancel"))
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

    def _on_active_toggle_mute(self):
        """Toggle mute for active deck"""
        deck = self._get_selected_deck()
        if deck:
            deck.toggle_mute()
            self._update_active_deck_controls()
            self._update_deck_panel(deck.deck_id)

    def _on_active_unload(self):
        """Unload the active deck"""
        deck = self._get_selected_deck()
        if deck:
            if self.mixer.is_deck_recording(deck.deck_id):
                self.mixer.stop_deck_recording(deck.deck_id)
            deck.unload()
            self.mixer.restart_multiroom_routing()
            self._update_active_deck_controls()
            self._update_deck_panel(deck.deck_id)
            self._mark_project_modified()

    def _on_active_volume_change(self, event):
        """Handle volume change for active deck"""
        deck = self._get_selected_deck()
        if deck:
            slider_value = self.active_volume_slider.GetValue()
            self._set_active_volume_value_label(slider_value)
            volume = slider_value / 100.0
            deck.set_volume(volume)
            self._update_deck_panel(deck.deck_id)
            self._mark_project_modified()

    def _on_active_balance_change(self, event):
        """Handle balance change for active deck"""
        deck = self._get_selected_deck()
        if deck:
            slider_value = self.active_balance_slider.GetValue()
            self._set_active_balance_value_label(slider_value)
            balance = slider_value / 100.0
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

    def _on_active_stream_change(self, event):
        """Handle livestream toggle from the global playback controls."""
        should_stream = self.active_stream_cb.GetValue()
        if should_stream == self.streamer.is_streaming:
            return
        if should_stream:
            if not self._start_livestream():
                self.active_stream_cb.SetValue(False)
        else:
            self._stop_livestream()

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
                _("Jump to time"),
                wx.OK | wx.ICON_INFORMATION
            )
            return

        duration = self.mixer.get_deck_duration_seconds(deck)
        current_pos = format_time(deck.get_position_seconds())
        duration_str = format_time(duration)

        dlg = CustomTextEntryDialog(
            self,
            _("Enter time (M:SS or H:MM:SS):") + f"\n{_('Duration')}: {duration_str}",
            _("Jump to time"),
            default_value = current_pos,
            ok_label=_("&OK"), cancel_label=_("&Cancel")
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

    def _get_current_mode_radio(self):
        """Get current operating mode selection"""
        for radio in (
            self.mixer_mode_radio,
            self.solo_mode_radio,
            self.auto_mode_radio,
            self.multiroom_mode_radio,
        ):
            if radio.GetValue():
                return radio
        return self.mixer_mode_radio

    def _on_jump_to_panel(self, event):
        """Handle F6 to jump between panels"""
        focus = wx.Window.FindFocus()

        mode_radios = (
            self.mixer_mode_radio,
            self.solo_mode_radio,
            self.auto_mode_radio,
            self.multiroom_mode_radio,
        )

        if focus in mode_radios:
            self.deck_listbox.SetFocus()
        elif focus == self.deck_listbox.control:
            self.active_menu_btn.SetFocus()
        else:
            self._get_current_mode_radio().SetFocus()

    def _sync_listbox_selection(self, deck_index):
        """Sync listbox selection with mixer's active deck"""
        if deck_index < self.deck_listbox.GetItemCount():
            if self.deck_listbox.GetSelectedRow() != deck_index:
                self.deck_listbox.SelectRow(deck_index)
            self._update_active_deck_controls()

    def _on_deck_info_changed(self, deck):
        """Handle deck info changes (name, loaded file, etc.)"""
        self._update_deck_listbox()
        # Update active controls if this deck is selected
        selection = self.deck_listbox.GetSelectedRow()
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
                    deck = self.mixer.decks[i]
                    loaded = deck.from_dict(deck_data)
                    missing_file = deck_data.get('file')
                    if not loaded and missing_file and not missing_file.startswith(('http://', 'https://')):
                        deck.file_path = missing_file
                        deck.is_stream = False
                        deck.is_soundcard_input = False
                        self._mark_deck_file_missing(deck)
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
            MODE_MULTIROOM: self.multiroom_mode_radio,
        }
        if self.mixer.mode in mode_radios:
            mode_radios[self.mixer.mode].SetValue(True)

        # Update master volume slider
        master_volume_value = int(self.mixer.master_volume * 100)
        self.master_volume_slider.SetValue(master_volume_value)
        self._set_master_volume_value_label(master_volume_value)

        # Update status bar
        mode_names = {
            MODE_MIXER: _("Mixer"),
            MODE_SOLO: _("Solo"),
            MODE_AUTOMATIC: _("Automatic"),
            MODE_MULTIROOM: _("Multiroom"),
        }
        self.SetStatusText(f"{_('Mode')}: {mode_names.get(self.mixer.mode, self.mixer.mode)}", 1)
        self.SetStatusText(f"{_('Master')}: {int(self.mixer.master_volume * 100)}%", 2)

        # Properly activate the mode (starts automatic switching thread if needed)
        loaded_mode = self.mixer.mode
        self.mixer.mode = MODE_MIXER  # Reset to trigger proper mode change
        self.mixer.set_mode(loaded_mode)

        if loaded_mode in [MODE_SOLO, MODE_AUTOMATIC, MODE_MULTIROOM]:
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
        self.playlist_service.import_m3u()

    def _parse_m3u_file(self, m3u_path):
        """Parse M3U file and return list of file paths/URLs.

        Handles:
        - Extended M3U format (#EXTM3U, #EXTINF lines are ignored)
        - Relative and absolute paths
        - HTTP/HTTPS URLs
        - UTF-8 and Latin-1 encodings
        """
        return self.playlist_service.parse_m3u_file(m3u_path)

    def _on_export_m3u(self, event):
        """Export loaded deck files/URLs to M3U playlist"""
        self.playlist_service.export_m3u()

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
        from gui.dialogs.effects import EffectsDialog
        self._effects_dialog = EffectsDialog(self, self.mixer)
        self._effects_dialog.Show()

    def _on_sleep_timer(self, event):
        """Show sleep timer dialog and start or cancel the timer."""
        from gui.dialogs.sleep_timer import SleepTimerDialog

        remaining_seconds = self._get_sleep_timer_remaining_seconds()
        dlg = SleepTimerDialog(self, self._sleep_timer_config, remaining_seconds)
        result = dlg.ShowModal()

        if result == wx.ID_OK:
            self._start_sleep_timer(dlg.GetTimerConfig())
        elif dlg.WasTimerCancelled():
            self._cancel_sleep_timer()

        dlg.Destroy()

    def _get_sleep_timer_remaining_seconds(self):
        """Return remaining sleep timer seconds, or None if no timer is running."""
        if not hasattr(self, '_sleep_timer') or not self._sleep_timer.IsRunning():
            return None
        if not self._sleep_timer_config or self._sleep_timer_started_at is None:
            return None
        elapsed = time.monotonic() - self._sleep_timer_started_at
        return max(0, self._sleep_timer_config.seconds - elapsed)

    def _start_sleep_timer(self, config):
        """Start or replace the sleep timer with the supplied configuration."""
        if self._sleep_timer.IsRunning():
            self._sleep_timer.Stop()

        self._sleep_timer_config = config
        self._sleep_timer_started_at = time.monotonic()
        self._sleep_timer.Start(config.seconds * 1000, oneShot=True)

        message = _("Sleep timer started: {minutes} min").format(minutes=config.minutes)
        self.SetStatusText(message, 0)
        self.tts_manager.speak(message)

    def _cancel_sleep_timer(self):
        """Cancel the active sleep timer."""
        if self._sleep_timer.IsRunning():
            self._sleep_timer.Stop()
        self._sleep_timer_config = None
        self._sleep_timer_started_at = None
        message = _("Sleep timer cancelled")
        self.SetStatusText(message, 0)
        self.tts_manager.speak(message)

    def _on_sleep_timer_elapsed(self, event):
        """Run the selected action when the sleep timer expires."""
        config = self._sleep_timer_config
        self._sleep_timer_config = None
        self._sleep_timer_started_at = None
        if not config:
            return

        self._execute_sleep_timer_action(config.action)

    def _execute_sleep_timer_action(self, action):
        """Execute a sleep timer action on the GUI thread."""
        from gui.dialogs.sleep_timer import ACTION_SHUTDOWN, ACTION_STOP_ALL_AND_EXIT

        self.mixer.stop_all()
        self._update_global_play_button()
        self._update_all_deck_panels()

        if action == ACTION_STOP_ALL_AND_EXIT:
            self.SetStatusText(_("Sleep timer expired: stopping playback and exiting"), 0)
            self.Close()
            return

        if action == ACTION_SHUTDOWN:
            self.SetStatusText(_("Sleep timer expired: shutting down computer"), 0)
            if not self._shutdown_computer():
                wx.MessageBox(
                    _("Playback was stopped, but the computer could not be shut down automatically."),
                    _("Sleep Timer"),
                    wx.OK | wx.ICON_WARNING
                )
            return

        self.SetStatusText(_("Sleep timer expired: playback stopped"), 0)
        self.tts_manager.speak(_("Sleep timer expired"))

    def _shutdown_computer(self):
        """Request operating system shutdown. Returns True if the command was started."""
        try:
            if sys.platform == 'win32':
                command = ['shutdown', '/s', '/t', '0']
            elif sys.platform == 'darwin':
                command = ['osascript', '-e', 'tell application "System Events" to shut down']
            else:
                command = ['systemctl', 'poweroff']
            subprocess.Popen(command)
            return True
        except OSError:
            return False

    def _on_options(self, event):
        """Show options dialog"""
        from gui.dialogs.options import OptionsDialog
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
            if 'tts' not in applied:
                self.apply_tts_settings()

        dlg.Destroy()

    def apply_audio_settings(self, old_device):
        """Apply audio settings from config at runtime.

        Args:
            old_device: Previous device setting to compare against for hot-swap
        """
        new_device = self.config_manager.get('Audio', 'output_device', 'default')
        if new_device != old_device:
            self._apply_audio_device_change(new_device)
        elif self.mixer.mode == MODE_MULTIROOM:
            self.mixer.restart_multiroom_routing()

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
        """Apply streaming settings to incoming stream handlers and the livestream output."""
        auto_reconnect = self.config_manager.getboolean('Streaming', 'auto_reconnect', True)
        reconnect_wait = self.config_manager.getint('Streaming', 'reconnect_wait', 5)
        for deck in self.mixer.decks:
            if deck.stream_handler:
                deck.stream_handler.set_reconnect_settings(auto_reconnect, reconnect_wait)
        was_streaming = self.streamer.is_streaming
        if was_streaming:
            self.streamer.stop_streaming(notify=False)
        self.streamer.update_config(self._get_streaming_config())
        if was_streaming and not self.streamer.start_streaming():
            wx.CallAfter(
                wx.MessageBox,
                _("Livestream could not be restarted with the new settings."),
                _("Streaming Error"),
                wx.OK | wx.ICON_ERROR
            )
        self._update_streaming_ui()

    def apply_tts_settings(self):
        """Apply TTS settings from config to the TTS manager"""
        self.tts_manager.tts_enabled = self.config_manager.getboolean('TTS', 'tts_enabled', False)
        engine = self.config_manager.get('TTS', 'tts_engine', '')
        voice = self.config_manager.get('TTS', 'tts_voice', '')
        rate = self.config_manager.getint('TTS', 'tts_rate', 0)
        volume = self.config_manager.getint('TTS', 'tts_volume', -1)
        self.tts_manager.configure(engine, voice, rate, volume)

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
            self.mixer.restart_multiroom_routing()
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

    def _on_routing_error(self, message):
        """Display mixer routing warnings on the GUI thread."""
        wx.CallAfter(self.SetStatusText, message, 0)

    def _on_help(self, event):
        """Show keyboard shortcuts"""
        docs_dir = Path(__file__).parent.parent.parent / 'docs'
        lang = get_i18n().language
        documentation_file = docs_dir / f'documentation-{lang}.html'
        if not documentation_file.exists():
            documentation_file = docs_dir / 'documentation-en.html'
        if documentation_file.exists():
            try:
                os.startfile(str(documentation_file))  # Windows
            except AttributeError:
                import subprocess
                subprocess.call(['xdg-open', str(documentation_file)])  # Linux
        else:
            dlg = wx.MessageDialog(
                self,
                _("Documentation file not found. Open developer's website instead?"),
                _("Documentation not found"),
                wx.YES_NO | wx.ICON_QUESTION
            )
            dlg.SetYesNoLabels(_("&Yes"), _("&No"))
            result = dlg.ShowModal()
            dlg.Destroy()

            if result == wx.ID_YES:
                self._on_website(self)
            else:
                return False

    def _on_website(self, event):
        """Open the developer's website in default browser"""
        def open_website():
            try:
                import webbrowser
                webbrowser.open(APP_WEBSITE)
            except webbrowser.Error:
                wx.CallAfter(wx.MessageBox, _("Error opening website"), _("Error"), wx.OK | wx.ICON_ERROR)
        wx.CallLater(200, open_website)

    def _on_about(self, event):
        """Show about dialog"""
        info = wx.adv.AboutDialogInfo()
        info.SetName(APP_NAME)
        info.SetVersion(APP_VERSION + " (" + _("Code name") + ": " + APP_CODE_NAME + ")")
        info.SetDescription(_("Accessible cross-platform audio player for simultaneous playback"))
        info.SetWebSite(APP_WEBSITE, desc="M45.dev")
        info.SetCopyright("Copyright (C) " + APP_AUTHOR)
        info.SetLicense(APP_LICENSE)
        wx.adv.AboutBox(info)

    def _on_exit(self, event):
        """Handle exit"""
        self.Close()

    def _add_keyboard_shortcut(self, accel_entries, modifiers, key_code, handler):
        """Register one keyboard accelerator and bind it to a handler."""
        accel_id = wx.NewIdRef()
        accel_entries.append(wx.AcceleratorEntry(modifiers, key_code, accel_id))
        self.Bind(wx.EVT_MENU, handler, id=accel_id)

    def _on_deck_shortcut(self, deck_index):
        """Handle Ctrl+N deck shortcut"""
        if deck_index < len(self.mixer.decks):
            intro_started = self.mixer.set_active_deck(deck_index, trigger_switch_event=True)
            deck = self.mixer.decks[deck_index]
            message = _("Active deck: {}").format(deck.name)
            self.SetStatusText(message, 0)
            if not intro_started:
                self.tts_manager.speak(message)
            # Update deck listbox selection
            self._sync_listbox_selection(deck_index)

    def _on_next_deck(self, event):
        """Handle Ctrl+Tab for next deck"""
        intro_started = self.mixer.next_deck(trigger_switch_event=True)
        deck_index = self.mixer.active_deck_index
        self._sync_listbox_selection(deck_index)
        deck = self.mixer.decks[deck_index]
        message = _("Active deck: {}").format(deck.name)
        self.SetStatusText(message, 0)
        if not intro_started:
            self.tts_manager.speak(message)

    def _on_previous_deck(self, event):
        """Handle Ctrl+Shift+Tab for previous deck"""
        intro_started = self.mixer.previous_deck(trigger_switch_event=True)
        deck_index = self.mixer.active_deck_index
        self._sync_listbox_selection(deck_index)
        deck = self.mixer.decks[deck_index]
        message = _("Active deck: {}").format(deck.name)
        self.SetStatusText(message, 0)
        if not intro_started:
            self.tts_manager.speak(message)

    def _on_mute_active_deck(self, event):
        """Handle Ctrl+M for mute"""
        deck = self.mixer.get_deck(self.mixer.active_deck_index)
        if deck:
            deck.toggle_mute()
            self.tts_manager.speak(_("Toggle Mute {}").format(deck.name))
            self._update_deck_panel(deck.deck_id)

    def _on_loop_active_deck(self, event):
        """Handle Ctrl+L for loop"""
        deck = self.mixer.get_deck(self.mixer.active_deck_index)
        if deck:
            deck.toggle_loop()
            self.tts_manager.speak(_("Toggle Loop {}").format(deck.name))
            self._update_deck_panel(deck.deck_id)

    def _on_shortcut_load_file(self, event):
        """Handle Ctrl+F for load file"""
        deck = self._get_selected_deck()
        if deck:
            self._on_deck_load_file(deck)

    def _on_shortcut_load_url(self, event):
        """Handle Ctrl+U for load URL"""
        deck = self._get_selected_deck()
        if deck:
            self._on_deck_load_url(deck)

    def _on_shortcut_load_soundcard_input(self, event):
        """Handle Ctrl+D for load soundcard input"""
        deck = self._get_selected_deck()
        if deck:
            self._on_deck_load_soundcard_input(deck)

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
        self._set_master_volume_value_label(new_value)
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
        message = _("Recording: {}").format(os.path.basename(filepath))
        self.SetStatusText(message, 0)
        self.tts_manager.speak(message)
        # Update menu item text
        self.record_menu_item.SetItemLabel(_("Stop &Recording") + "\tCtrl+R")

    def _on_recording_stopped(self, filepath, frames):
        """Callback when recording stops"""
        message = _("Recording stopped: {}").format(os.path.basename(filepath))
        self.SetStatusText(message, 0)
        self.tts_manager.speak(message)
        # Update menu item text
        self.record_menu_item.SetItemLabel(_("Start &Recording") + "\tCtrl+R")

    def _on_streaming_started(self, stream_url):
        """Callback when livestreaming starts."""
        message = _("Livestream started")
        if stream_url:
            message = _("Livestream started: {}").format(stream_url)
        wx.CallAfter(self._handle_streaming_started, message)

    def _handle_streaming_started(self, message):
        """Handle livestream start on the GUI thread."""
        self.SetStatusText(message, 0)
        self.tts_manager.speak(message)
        self._update_streaming_ui()

    def _on_streaming_stopped(self, stream_url, frames):
        """Callback when livestreaming stops."""
        wx.CallAfter(self._handle_streaming_stopped)

    def _handle_streaming_stopped(self):
        """Handle livestream stop on the GUI thread."""
        self.SetStatusText(_("Livestream stopped"), 0)
        self.tts_manager.speak(_("Livestream stopped"))
        self._update_streaming_ui()

    def _on_streaming_error(self, message):
        """Handle livestream errors."""
        wx.CallAfter(self._handle_streaming_error, message)

    def _handle_streaming_error(self, message):
        """Handle livestream errors on the GUI thread."""
        self.SetStatusText(message, 0)
        self._update_streaming_ui()

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

    def _get_streaming_config(self) -> dict:
        """Build livestream config dict from current settings."""
        return {
            'server': self.config_manager.get('Streaming', 'server', ''),
            'port': self.config_manager.getint('Streaming', 'port', 8000),
            'mountpoint': self.config_manager.get('Streaming', 'mountpoint', '/stream'),
            'credentials': self.config_manager.get('Streaming', 'credentials', ''),
            'codec': self.config_manager.get('Streaming', 'codec', 'mp3'),
            'bitrate': self.config_manager.getint('Streaming', 'bitrate', 192),
            'name': self.config_manager.get('Streaming', 'name', 'MultiDeck Live'),
            'description': self.config_manager.get('Streaming', 'description', ''),
            'genre': self.config_manager.get('Streaming', 'genre', ''),
            'url': self.config_manager.get('Streaming', 'url', ''),
            'public': self.config_manager.getboolean('Streaming', 'public', False),
            'auto_reconnect': self.config_manager.getboolean('Streaming', 'auto_reconnect', True),
            'reconnect_wait': self.config_manager.getint('Streaming', 'reconnect_wait', 5),
            'queue_blocks': self.config_manager.getint('Streaming', 'queue_blocks', 128),
            'writer_poll_ms': self.config_manager.getint('Streaming', 'writer_poll_ms', 100),
            'ffmpeg_close_timeout': self.config_manager.getfloat('Streaming', 'ffmpeg_close_timeout', 5.0),
            'ffmpeg_loglevel': self.config_manager.get('Streaming', 'ffmpeg_loglevel', 'error'),
        }

    def _can_start_livestream(self) -> bool:
        """Check whether livestreaming can be started from the current configuration."""
        if self.streamer.is_streaming:
            return True
        return self.streamer.is_configured()

    def _show_streaming_configuration_error(self):
        """Explain why livestreaming cannot be started."""
        config_error = self.streamer.get_configuration_error()
        if config_error:
            wx.MessageBox(
                config_error,
                _("Streaming Settings Incomplete"),
                wx.OK | wx.ICON_INFORMATION
            )
            return
        wx.MessageBox(
            _("FFmpeg is required to start the livestream."),
            _("Streaming Error"),
            wx.OK | wx.ICON_ERROR
        )

    def _start_livestream(self, show_errors: bool = True) -> bool:
        """Start the master livestream."""
        self.streamer.update_config(self._get_streaming_config())
        if not self.streamer.is_configured():
            if show_errors:
                self._show_streaming_configuration_error()
            return False
        if not self.streamer.start_streaming():
            if show_errors:
                wx.MessageBox(
                    self.streamer.last_error or _("Failed to start livestream."),
                    _("Streaming Error"),
                    wx.OK | wx.ICON_ERROR
                )
            return False
        self._update_streaming_ui()
        return True

    def _stop_livestream(self):
        """Stop the master livestream."""
        self.streamer.stop_streaming()
        self._update_streaming_ui()

    def _on_toggle_livestream(self, event):
        """Toggle the master livestream from menus."""
        if self.streamer.is_streaming:
            self._stop_livestream()
        else:
            self._start_livestream()

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
        message = _("Recording started: {}").format(f"{deck_name} → {os.path.basename(filepath)}")
        self.SetStatusText(message, 0)
        self.tts_manager.speak(message)
        self._update_deck_listbox()
        selection = self.deck_listbox.GetSelectedRow()
        if selection != wx.NOT_FOUND and selection == deck_id - 1:
            self._update_active_deck_controls()

    def _on_deck_recording_stopped(self, deck_id, filepath, frames):
        """Callback when a deck recording stops (called from audio thread)."""
        wx.CallAfter(self._handle_deck_recording_stopped, deck_id, filepath, frames)

    def _handle_deck_recording_stopped(self, deck_id, filepath, frames):
        """Handle deck recording stopped on the GUI thread."""
        deck = self.mixer.get_deck_by_id(deck_id)
        deck_name = deck.name if deck else f"Deck {deck_id}"
        message = _("Recording stopped: {}").format(f"{deck_name} → {os.path.basename(filepath)}")
        self.SetStatusText(message, 0)
        self.tts_manager.speak(message)
        self._update_deck_listbox()
        selection = self.deck_listbox.GetSelectedRow()
        if selection != wx.NOT_FOUND and selection == deck_id - 1:
            self._update_active_deck_controls()

    def _on_close(self, event):
        """Handle window close"""
        # Check for unsaved changes
        if not self._check_unsaved_changes():
            event.Veto()
            return

        # Stop position timer
        if self._position_timer.IsRunning():
            self._position_timer.Stop()
        if hasattr(self, '_sleep_timer') and self._sleep_timer.IsRunning():
            self._sleep_timer.Stop()

        # Save window size
        width, height = self.GetSize()
        self.config_manager.set('UI', 'window_width', width)
        self.config_manager.set('UI', 'window_height', height)
        self.config_manager.save()

        # Cleanup
        self.tts_manager.shutdown()
        self.mixer.cleanup()

        event.Skip()
