"""
Dialogs - Various dialog windows for MultiDeck Audio Player
"""

import wx
import sounddevice as sd
from config.defaults import VALID_DECK_COUNTS
from utils.i18n import _, LANGUAGE_NAMES
from audio.recorder import FFMPEG_AVAILABLE


class OptionsDialog(wx.Dialog):
    """Options/Preferences dialog"""

    def __init__(self, parent, config_manager, theme_manager=None):
        """
        Initialize options dialog.

        Args:
            parent: Parent window (MainFrame)
            config_manager: ConfigManager instance
            theme_manager: ThemeManager instance (optional)
        """
        super().__init__(parent, title=_("Options"), size=(500, 400))

        self.config_manager = config_manager
        self.theme_manager = theme_manager
        self.main_frame = parent
        self._applied_sections = set()  # Track which sections were applied via Apply buttons
        self._initial_device = config_manager.get('Audio', 'output_device', 'default')
        self._create_ui()

        # Apply theme to dialog if theme manager is available
        if self.theme_manager:
            self.theme_manager.apply_theme(self)

    # Tab name constants matching notebook page order
    TAB_NAMES = ['general', 'audio', 'automation', 'recorder', 'streaming']

    def _create_ui(self):
        """Create dialog UI"""
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Notebook for different option categories
        self.notebook = wx.Notebook(panel)

        # General tab
        general_panel = self._create_general_tab(self.notebook)
        self.notebook.AddPage(general_panel, _("General"))

        # Audio tab
        audio_panel = self._create_audio_tab(self.notebook)
        self.notebook.AddPage(audio_panel, _("Audio"))

        # Automation tab
        automation_panel = self._create_automation_tab(self.notebook)
        self.notebook.AddPage(automation_panel, _("Automation"))

        # Recorder tab
        recorder_panel = self._create_recorder_tab(self.notebook)
        self.notebook.AddPage(recorder_panel, _("Recorder"))

        # Streaming tab
        streaming_panel = self._create_streaming_tab(self.notebook)
        self.notebook.AddPage(streaming_panel, _("Streaming"))

        main_sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 10)

        # Buttons: OK, Cancel, Apply
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.AddStretchSpacer()
        ok_button = wx.Button(panel, wx.ID_OK, label=_("&OK"))
        ok_button.SetName(_("&OK"))
        cancel_button = wx.Button(panel, wx.ID_CANCEL, label=_("&Cancel"))
        cancel_button.SetName(_("&Cancel"))
        self.apply_button = wx.Button(panel, wx.ID_APPLY, label=_("&Apply"))
        self.apply_button.SetName(_("&Apply"))
        self.apply_button.Disable()

        button_sizer.Add(ok_button, 0, wx.ALL, 5)
        button_sizer.Add(cancel_button, 0, wx.ALL, 5)
        button_sizer.Add(self.apply_button, 0, wx.ALL, 5)

        main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 5)

        panel.SetSizer(main_sizer)

        # Snapshot initial control values for change detection
        self._snapshot_initial_values()

        # Bind buttons
        ok_button.Bind(wx.EVT_BUTTON, self._on_ok)
        self.apply_button.Bind(wx.EVT_BUTTON, self._on_apply)

        # Bind notebook page change to update Apply button state
        self.notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self._on_page_changed)

        # Bind change events on all controls to update Apply button state
        # Note: theme_choice is excluded here because it already has a dedicated
        # handler (_on_theme_change) for live preview, which also updates Apply state.
        for ctrl in (self.language_choice, self.deck_count_choice,
                     self.device_choice, self.buffer_choice, self.rate_choice,
                     self.format_choice, self.bitrate_choice, self.depth_choice):
            ctrl.Bind(wx.EVT_CHOICE, self._on_control_changed)

        for ctrl in (self.interval_spin, self.crossfade_spin,
                     self.preroll_spin, self.wait_spin):
            ctrl.Bind(wx.EVT_SPINCTRL, self._on_control_changed)

        self.crossfade_check.Bind(wx.EVT_CHECKBOX, self._on_control_changed)
        self.auto_reconnect_check.Bind(wx.EVT_CHECKBOX, self._on_control_changed)
        self.output_dir_text.Bind(wx.EVT_TEXT, self._on_control_changed)

    def _create_general_tab(self, parent):
        """Create general options tab"""
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Language
        lang_sizer = wx.BoxSizer(wx.HORIZONTAL)
        lang_label = wx.StaticText(panel, label=_("Language") + ":")
        lang_sizer.Add(lang_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)

        current_lang = self.config_manager.get('General', 'language', 'en')
        languages = ['en', 'de']
        lang_choices = [LANGUAGE_NAMES.get(lang, lang) for lang in languages]

        self.language_choice = wx.Choice(panel, choices=lang_choices)
        self.language_choice.SetName(_("Language"))
        self.language_choice.SetSelection(languages.index(current_lang))
        lang_sizer.Add(self.language_choice, 1, wx.EXPAND | wx.ALL, 5)

        sizer.Add(lang_sizer, 0, wx.EXPAND | wx.ALL, 5)

        # Number of decks
        deck_sizer = wx.BoxSizer(wx.HORIZONTAL)
        deck_label = wx.StaticText(panel, label=_("Number of Decks") + ":")
        deck_sizer.Add(deck_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)

        current_deck_count = self.config_manager.get_deck_count()
        deck_choices = [str(n) for n in VALID_DECK_COUNTS]

        self.deck_count_choice = wx.Choice(panel, choices=deck_choices)
        self.deck_count_choice.SetName(_("Number of Decks"))
        self.deck_count_choice.SetSelection(VALID_DECK_COUNTS.index(current_deck_count))
        deck_sizer.Add(self.deck_count_choice, 1, wx.EXPAND | wx.ALL, 5)

        sizer.Add(deck_sizer, 0, wx.EXPAND | wx.ALL, 5)

        # Theme
        theme_sizer = wx.BoxSizer(wx.HORIZONTAL)
        theme_label = wx.StaticText(panel, label=_("Theme") + ":")
        theme_sizer.Add(theme_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)

        current_theme = self.config_manager.get('General', 'theme', 'system')
        theme_choices = [_("System"), _("Light"), _("Dark")]
        theme_values = ['system', 'light', 'dark']

        self.theme_choice = wx.Choice(panel, choices=theme_choices)
        self.theme_choice.SetName(_("Theme"))
        if current_theme in theme_values:
            self.theme_choice.SetSelection(theme_values.index(current_theme))
        self.theme_values = theme_values
        self.theme_choice.Bind(wx.EVT_CHOICE, self._on_theme_change)
        theme_sizer.Add(self.theme_choice, 1, wx.EXPAND | wx.ALL, 5)

        sizer.Add(theme_sizer, 0, wx.EXPAND | wx.ALL, 5)

        panel.SetSizer(sizer)
        return panel

    def _create_audio_tab(self, parent):
        """Create audio options tab"""
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Output device
        device_sizer = wx.BoxSizer(wx.HORIZONTAL)
        device_label = wx.StaticText(panel, label=_("Output Device") + ":")
        device_sizer.Add(device_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)

        # Get available output devices
        self.output_devices = self._get_output_devices()
        device_choices = [_("System Default")]
        self.device_values = ['default']

        for device in self.output_devices:
            device_choices.append(device['name'])
            self.device_values.append(str(device['index']))

        current_device = self.config_manager.get('Audio', 'output_device', 'default')

        self.device_choice = wx.Choice(panel, choices=device_choices)
        self.device_choice.SetName(_("Output Device"))
        # Find and set current selection
        if current_device in self.device_values:
            self.device_choice.SetSelection(self.device_values.index(current_device))
        else:
            self.device_choice.SetSelection(0)  # Default to system default
        device_sizer.Add(self.device_choice, 1, wx.EXPAND | wx.ALL, 5)

        sizer.Add(device_sizer, 0, wx.EXPAND | wx.ALL, 5)

        # Buffer size
        buffer_sizer = wx.BoxSizer(wx.HORIZONTAL)
        buffer_label = wx.StaticText(panel, label=_("Buffer Size") + ":")
        buffer_sizer.Add(buffer_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)

        current_buffer = self.config_manager.getint('Audio', 'buffer_size', 2048)
        buffer_choices = ['512', '1024', '2048', '4096']

        self.buffer_choice = wx.Choice(panel, choices=buffer_choices)
        self.buffer_choice.SetName(_("Buffer Size"))
        if str(current_buffer) in buffer_choices:
            self.buffer_choice.SetSelection(buffer_choices.index(str(current_buffer)))
        buffer_sizer.Add(self.buffer_choice, 1, wx.EXPAND | wx.ALL, 5)

        sizer.Add(buffer_sizer, 0, wx.EXPAND | wx.ALL, 5)

        # Sample rate
        rate_sizer = wx.BoxSizer(wx.HORIZONTAL)
        rate_label = wx.StaticText(panel, label=_("Sample Rate") + ":")
        rate_sizer.Add(rate_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)

        current_rate = self.config_manager.getint('Audio', 'sample_rate', 44100)
        rate_choices = ['44100', '48000']

        self.rate_choice = wx.Choice(panel, choices=rate_choices)
        self.rate_choice.SetName(_("Sample Rate"))
        if str(current_rate) in rate_choices:
            self.rate_choice.SetSelection(rate_choices.index(str(current_rate)))
        rate_sizer.Add(self.rate_choice, 1, wx.EXPAND | wx.ALL, 5)

        sizer.Add(rate_sizer, 0, wx.EXPAND | wx.ALL, 5)

        panel.SetSizer(sizer)
        return panel

    def _get_output_devices(self):
        """Get list of available audio output devices"""
        try:
            devices = sd.query_devices()
            hostapis = sd.query_hostapis()
            output_devices = []

            for idx, device in enumerate(devices):
                if device['max_output_channels'] > 0:
                    # Get host API name for this device
                    hostapi_idx = device['hostapi']
                    hostapi_name = hostapis[hostapi_idx]['name'] if hostapi_idx < len(hostapis) else ''

                    # Format display name with host API
                    display_name = f"{device['name']} ({hostapi_name})" if hostapi_name else device['name']

                    output_devices.append({
                        'index': idx,
                        'name': display_name,
                    })

            return output_devices
        except Exception as e:
            print(f"Error querying audio devices: {e}")
            return []

    def _create_automation_tab(self, parent):
        """Create automation options tab"""
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Switch interval
        interval_sizer = wx.BoxSizer(wx.HORIZONTAL)
        interval_label = wx.StaticText(panel, label=_("Switch Interval (seconds)") + ":")
        interval_sizer.Add(interval_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)

        current_interval = self.config_manager.getint('Automation', 'switch_interval', 10)
        self.interval_spin = wx.SpinCtrl(panel, value=str(current_interval),
                                         min=1, max=300, initial=current_interval)
        self.interval_spin.SetName(_("Switch Interval (seconds)"))
        interval_sizer.Add(self.interval_spin, 1, wx.EXPAND | wx.ALL, 5)

        sizer.Add(interval_sizer, 0, wx.EXPAND | wx.ALL, 5)

        # Crossfade enabled
        self.crossfade_check = wx.CheckBox(panel, label=_("Enable Crossfade"))
        self.crossfade_check.SetName(_("Enable Crossfade"))
        crossfade_enabled = self.config_manager.getboolean('Automation', 'crossfade_enabled', True)
        self.crossfade_check.SetValue(crossfade_enabled)
        sizer.Add(self.crossfade_check, 0, wx.ALL, 10)

        # Crossfade duration (in tenths of seconds for accessibility)
        duration_sizer = wx.BoxSizer(wx.HORIZONTAL)
        duration_label = wx.StaticText(panel, label=_("Crossfade Duration (0.1s)") + ":")
        duration_sizer.Add(duration_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)

        current_duration = self.config_manager.getfloat('Automation', 'crossfade_duration', 2.0)
        # Convert seconds to tenths (e.g., 2.0s -> 20)
        current_duration_tenths = int(current_duration * 10)
        self.crossfade_spin = wx.SpinCtrl(panel, value=str(current_duration_tenths),
                                          min=5, max=100, initial=current_duration_tenths)
        self.crossfade_spin.SetName(_("Crossfade Duration (0.1s)"))
        duration_sizer.Add(self.crossfade_spin, 1, wx.EXPAND | wx.ALL, 5)

        sizer.Add(duration_sizer, 0, wx.EXPAND | wx.ALL, 5)

        panel.SetSizer(sizer)
        return panel

    def _create_recorder_tab(self, parent):
        """Create recorder options tab"""
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Recording format
        format_sizer = wx.BoxSizer(wx.HORIZONTAL)
        format_label = wx.StaticText(panel, label=_("Format") + ":")
        format_sizer.Add(format_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)

        current_format = self.config_manager.get('Recorder', 'format', 'wav')

        # Build format choices based on FFmpeg availability
        format_choices = ['WAV']
        format_values = ['wav']
        if FFMPEG_AVAILABLE:
            format_choices.extend(['MP3', 'OGG Vorbis', 'FLAC'])
            format_values.extend(['mp3', 'ogg', 'flac'])

        self.format_choice = wx.Choice(panel, choices=format_choices)
        self.format_choice.SetName(_("Format"))
        if current_format in format_values:
            self.format_choice.SetSelection(format_values.index(current_format))
        else:
            self.format_choice.SetSelection(0)  # Default to WAV
        self.format_values = format_values
        format_sizer.Add(self.format_choice, 1, wx.EXPAND | wx.ALL, 5)

        sizer.Add(format_sizer, 0, wx.EXPAND | wx.ALL, 5)

        # Bitrate (for MP3/OGG)
        bitrate_sizer = wx.BoxSizer(wx.HORIZONTAL)
        bitrate_label = wx.StaticText(panel, label=_("Bitrate (MP3/OGG)") + ":")
        bitrate_sizer.Add(bitrate_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)

        current_bitrate = self.config_manager.getint('Recorder', 'bitrate', 192)
        bitrate_choices = ['64', '96', '128', '160', '192', '224', '256', '320']
        bitrate_labels = [f'{b} kbps' for b in bitrate_choices]

        self.bitrate_choice = wx.Choice(panel, choices=bitrate_labels)
        self.bitrate_choice.SetName(_("Bitrate (MP3/OGG)"))
        if str(current_bitrate) in bitrate_choices:
            self.bitrate_choice.SetSelection(bitrate_choices.index(str(current_bitrate)))
        else:
            self.bitrate_choice.SetSelection(4)  # Default to 192
        self.bitrate_values = bitrate_choices
        bitrate_sizer.Add(self.bitrate_choice, 1, wx.EXPAND | wx.ALL, 5)

        sizer.Add(bitrate_sizer, 0, wx.EXPAND | wx.ALL, 5)

        # FFmpeg status info
        if not FFMPEG_AVAILABLE:
            ffmpeg_info = wx.StaticText(
                panel,
                label=_("Note: Install FFmpeg for MP3, OGG, and FLAC support.")
            )
            ffmpeg_info.SetForegroundColour(wx.Colour(128, 128, 128))
            sizer.Add(ffmpeg_info, 0, wx.ALL, 10)

        # Bit depth (only for WAV format)
        depth_sizer = wx.BoxSizer(wx.HORIZONTAL)
        depth_label = wx.StaticText(panel, label=_("Bit Depth (WAV only)") + ":")
        depth_sizer.Add(depth_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)

        current_depth = self.config_manager.getint('Recorder', 'bit_depth', 16)
        depth_choices = ['16', '24', '32']

        self.depth_choice = wx.Choice(panel, choices=depth_choices)
        self.depth_choice.SetName(_("Bit Depth (WAV only)"))
        if str(current_depth) in depth_choices:
            self.depth_choice.SetSelection(depth_choices.index(str(current_depth)))
        depth_sizer.Add(self.depth_choice, 1, wx.EXPAND | wx.ALL, 5)

        sizer.Add(depth_sizer, 0, wx.EXPAND | wx.ALL, 5)

        # Pre-roll duration
        preroll_sizer = wx.BoxSizer(wx.HORIZONTAL)
        preroll_label = wx.StaticText(panel, label=_("Pre-Roll (seconds)") + ":")
        preroll_sizer.Add(preroll_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)

        current_preroll = self.config_manager.getint('Recorder', 'pre_roll_seconds', 30)
        self.preroll_spin = wx.SpinCtrl(panel, value=str(current_preroll),
                                        min=0, max=120, initial=current_preroll)
        self.preroll_spin.SetName(_("Pre-Roll (seconds)"))
        self.preroll_spin.SetToolTip(_("Buffer audio before recording starts (0 to disable)"))
        preroll_sizer.Add(self.preroll_spin, 1, wx.EXPAND | wx.ALL, 5)

        sizer.Add(preroll_sizer, 0, wx.EXPAND | wx.ALL, 5)

        # Output directory
        dir_sizer = wx.BoxSizer(wx.HORIZONTAL)
        dir_label = wx.StaticText(panel, label=_("Output Directory") + ":")
        dir_sizer.Add(dir_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)

        current_dir = self.config_manager.get('Recorder', 'output_directory', '')
        self.output_dir_text = wx.TextCtrl(panel, value=current_dir)
        self.output_dir_text.SetName(_("Output Directory"))
        dir_sizer.Add(self.output_dir_text, 1, wx.EXPAND | wx.ALL, 5)

        browse_btn = wx.Button(panel, label=_("Browse..."))
        browse_btn.SetName(_("Browse for Output Directory"))
        browse_btn.Bind(wx.EVT_BUTTON, self._on_browse_output_dir)
        dir_sizer.Add(browse_btn, 0, wx.ALL, 5)

        sizer.Add(dir_sizer, 0, wx.EXPAND | wx.ALL, 5)

        panel.SetSizer(sizer)
        return panel

    def _on_browse_output_dir(self, event):
        """Handle browse button for output directory"""
        dlg = wx.DirDialog(self, _("Choose Recording Output Directory"))
        if dlg.ShowModal() == wx.ID_OK:
            self.output_dir_text.SetValue(dlg.GetPath())
        dlg.Destroy()

    def _create_streaming_tab(self, parent):
        """Create streaming options tab"""
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Auto-reconnect
        self.auto_reconnect_check = wx.CheckBox(panel, label=_("Auto-reconnect on connection loss"))
        self.auto_reconnect_check.SetName(_("Auto-reconnect on connection loss"))
        self.auto_reconnect_check.SetValue(
            self.config_manager.getboolean('Streaming', 'auto_reconnect', True)
        )
        sizer.Add(self.auto_reconnect_check, 0, wx.ALL, 5)

        # Reconnect wait
        wait_sizer = wx.BoxSizer(wx.HORIZONTAL)
        wait_label = wx.StaticText(panel, label=_("Reconnect Wait (seconds)") + ":")
        wait_sizer.Add(wait_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)

        current_wait = self.config_manager.getint('Streaming', 'reconnect_wait', 5)
        self.wait_spin = wx.SpinCtrl(panel, value=str(current_wait),
                                     min=1, max=60, initial=current_wait)
        self.wait_spin.SetName(_("Reconnect Wait (seconds)"))
        wait_sizer.Add(self.wait_spin, 1, wx.EXPAND | wx.ALL, 5)

        sizer.Add(wait_sizer, 0, wx.EXPAND | wx.ALL, 5)

        panel.SetSizer(sizer)
        return panel

    def _on_theme_change(self, event):
        """Handle theme selection change - apply immediately"""
        if self.theme_manager:
            selected_theme = self.theme_values[self.theme_choice.GetSelection()]
            self.theme_manager.set_theme(selected_theme)
            # Re-apply theme to this dialog
            self.theme_manager.apply_theme(self)
        self._update_apply_state()

    # --- Change detection ---

    def _snapshot_initial_values(self):
        """Capture current control values as baseline for change detection"""
        self._initial_values = {
            'general': (
                self.language_choice.GetSelection(),
                self.deck_count_choice.GetSelection(),
                self.theme_choice.GetSelection(),
            ),
            'audio': (
                self.device_choice.GetSelection(),
                self.buffer_choice.GetSelection(),
                self.rate_choice.GetSelection(),
            ),
            'automation': (
                self.interval_spin.GetValue(),
                self.crossfade_check.GetValue(),
                self.crossfade_spin.GetValue(),
            ),
            'recorder': (
                self.format_choice.GetSelection(),
                self.bitrate_choice.GetSelection(),
                self.depth_choice.GetSelection(),
                self.preroll_spin.GetValue(),
                self.output_dir_text.GetValue(),
            ),
            'streaming': (
                self.auto_reconnect_check.GetValue(),
                self.wait_spin.GetValue(),
            ),
        }

    def _get_current_values(self, tab_name):
        """Get current control values for a given tab"""
        if tab_name == 'general':
            return (
                self.language_choice.GetSelection(),
                self.deck_count_choice.GetSelection(),
                self.theme_choice.GetSelection(),
            )
        elif tab_name == 'audio':
            return (
                self.device_choice.GetSelection(),
                self.buffer_choice.GetSelection(),
                self.rate_choice.GetSelection(),
            )
        elif tab_name == 'automation':
            return (
                self.interval_spin.GetValue(),
                self.crossfade_check.GetValue(),
                self.crossfade_spin.GetValue(),
            )
        elif tab_name == 'recorder':
            return (
                self.format_choice.GetSelection(),
                self.bitrate_choice.GetSelection(),
                self.depth_choice.GetSelection(),
                self.preroll_spin.GetValue(),
                self.output_dir_text.GetValue(),
            )
        elif tab_name == 'streaming':
            return (
                self.auto_reconnect_check.GetValue(),
                self.wait_spin.GetValue(),
            )
        return ()

    def _get_active_tab_name(self):
        """Get the name of the currently active notebook tab"""
        idx = self.notebook.GetSelection()
        if 0 <= idx < len(self.TAB_NAMES):
            return self.TAB_NAMES[idx]
        return ''

    def _has_tab_changes(self, tab_name):
        """Check if the given tab has unsaved changes compared to initial values"""
        return self._get_current_values(tab_name) != self._initial_values.get(tab_name)

    def _update_apply_state(self):
        """Enable or disable the Apply button based on current tab changes"""
        tab_name = self._get_active_tab_name()
        self.apply_button.Enable(self._has_tab_changes(tab_name))

    def _on_page_changed(self, event):
        """Handle notebook tab change - update Apply button state"""
        event.Skip()
        # Use CallAfter because the page selection may not be updated yet
        wx.CallAfter(self._update_apply_state)

    def _on_control_changed(self, event):
        """Handle any control value change - update Apply button state"""
        event.Skip()
        self._update_apply_state()

    # --- Per-section save methods ---

    def _save_general(self):
        """Save general settings to config and return restart reasons"""
        old_language = self.config_manager.get('General', 'language', 'en')
        old_deck_count = self.config_manager.get('General', 'deck_count', '10')

        languages = ['en', 'de']
        self.config_manager.set('General', 'language', languages[self.language_choice.GetSelection()])
        self.config_manager.set('General', 'deck_count',
                               VALID_DECK_COUNTS[self.deck_count_choice.GetSelection()])
        self.config_manager.set('General', 'theme',
                               self.theme_values[self.theme_choice.GetSelection()])

        restart_reasons = []
        if self.config_manager.get('General', 'language', 'en') != old_language:
            restart_reasons.append(_("Language"))
        if self.config_manager.get('General', 'deck_count', '10') != old_deck_count:
            restart_reasons.append(_("Number of decks"))
        return restart_reasons

    def _save_audio(self):
        """Save audio settings to config and return restart reasons"""
        old_buffer_size = self.config_manager.get('Audio', 'buffer_size', '2048')
        old_sample_rate = self.config_manager.get('Audio', 'sample_rate', '44100')

        self.config_manager.set('Audio', 'output_device',
                               self.device_values[self.device_choice.GetSelection()])

        buffer_choices = ['512', '1024', '2048', '4096']
        self.config_manager.set('Audio', 'buffer_size',
                               buffer_choices[self.buffer_choice.GetSelection()])

        rate_choices = ['44100', '48000']
        self.config_manager.set('Audio', 'sample_rate',
                               rate_choices[self.rate_choice.GetSelection()])

        restart_reasons = []
        if self.config_manager.get('Audio', 'buffer_size', '2048') != old_buffer_size:
            restart_reasons.append(_("Buffer size"))
        if self.config_manager.get('Audio', 'sample_rate', '44100') != old_sample_rate:
            restart_reasons.append(_("Sample rate"))
        return restart_reasons

    def _save_automation(self):
        """Save automation settings to config"""
        self.config_manager.set('Automation', 'switch_interval', self.interval_spin.GetValue())
        self.config_manager.set('Automation', 'crossfade_enabled', self.crossfade_check.GetValue())
        # Convert tenths back to seconds (e.g., 20 -> 2.0s)
        self.config_manager.set('Automation', 'crossfade_duration', self.crossfade_spin.GetValue() / 10.0)

    def _save_recorder(self):
        """Save recorder settings to config"""
        self.config_manager.set('Recorder', 'format',
                               self.format_values[self.format_choice.GetSelection()])
        self.config_manager.set('Recorder', 'bitrate',
                               self.bitrate_values[self.bitrate_choice.GetSelection()])

        depth_choices = ['16', '24', '32']
        self.config_manager.set('Recorder', 'bit_depth',
                               depth_choices[self.depth_choice.GetSelection()])

        self.config_manager.set('Recorder', 'pre_roll_seconds',
                               self.preroll_spin.GetValue())
        self.config_manager.set('Recorder', 'output_directory',
                               self.output_dir_text.GetValue())

    def _save_streaming(self):
        """Save streaming settings to config"""
        self.config_manager.set('Streaming', 'auto_reconnect',
                               self.auto_reconnect_check.GetValue())
        self.config_manager.set('Streaming', 'reconnect_wait', self.wait_spin.GetValue())

    def _show_restart_message(self, restart_reasons):
        """Show restart message if any settings require it"""
        if restart_reasons:
            reason_list = ", ".join(restart_reasons)
            wx.MessageBox(
                _("The following settings require restarting the application to take effect:") + "\n\n" + reason_list,
                _("Restart Required"),
                wx.OK | wx.ICON_INFORMATION
            )

    # --- Apply button handler ---

    def _apply_section(self, tab_name):
        """Save, apply, and mark a single section as applied. Returns restart reasons."""
        restart_reasons = []
        if tab_name == 'general':
            restart_reasons = self._save_general()
        elif tab_name == 'audio':
            old_device = self._initial_device
            restart_reasons = self._save_audio()
            self.config_manager.save()
            self.main_frame.apply_audio_settings(old_device)
            self._initial_device = self.config_manager.get('Audio', 'output_device', 'default')
        elif tab_name == 'automation':
            self._save_automation()
            self.config_manager.save()
            self.main_frame.apply_automation_settings()
        elif tab_name == 'recorder':
            self._save_recorder()
            self.config_manager.save()
            self.main_frame.apply_recorder_settings()
        elif tab_name == 'streaming':
            self._save_streaming()
            self.config_manager.save()
            self.main_frame.apply_streaming_settings()

        self.config_manager.save()
        self._applied_sections.add(tab_name)
        # Update baseline so Apply disables after applying
        self._initial_values[tab_name] = self._get_current_values(tab_name)
        self._update_apply_state()
        return restart_reasons

    def _on_apply(self, event):
        """Apply only the currently active tab's settings"""
        tab_name = self._get_active_tab_name()
        if not tab_name:
            return
        restart_reasons = self._apply_section(tab_name)
        self._show_restart_message(restart_reasons)

    # --- OK button handler ---

    def _on_ok(self, event):
        """Handle OK button - save and apply all sections not yet applied"""
        restart_reasons = []

        if 'general' not in self._applied_sections:
            restart_reasons.extend(self._save_general())
        if 'audio' not in self._applied_sections:
            restart_reasons.extend(self._save_audio())
        if 'automation' not in self._applied_sections:
            self._save_automation()
        if 'recorder' not in self._applied_sections:
            self._save_recorder()
        if 'streaming' not in self._applied_sections:
            self._save_streaming()

        self.config_manager.save()
        self._show_restart_message(restart_reasons)
        self.EndModal(wx.ID_OK)
