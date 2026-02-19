"""
Dialogs - Various dialog windows for MultiDeck Audio Player
"""

import wx
import sys
import sounddevice as sd
from config.defaults import VALID_DECK_COUNTS
from utils.i18n import _, LANGUAGE_NAMES
from audio.recorder import FFMPEG_AVAILABLE


class _ValueDisplayAccessible(wx.Accessible):
    """Hides slider value labels from screen reader dialog descriptions.

    NVDA collects ROLE_SYSTEM_STATICTEXT objects for its dialog description.
    Changing the role to ROLE_SYSTEM_WHITESPACE prevents these purely visual
    value displays (e.g. '50%', '+0 dB') from being included.
    """

    def GetRole(self, childId):
        return (wx.ACC_OK, wx.ROLE_SYSTEM_WHITESPACE)


class _FormattedSliderAccessible(wx.Accessible):
    """Overrides the MSAA VALUE property of a slider with a formatted string.

    wx.Slider reports its value as a percentage (0-100%) by default, which
    is meaningless for parameters like dB or milliseconds. This class
    returns the properly formatted value (e.g. '+3 dB', '300 ms') instead.
    """

    def __init__(self, slider, fmt_func):
        super().__init__(slider)
        self._slider = slider
        self._fmt_func = fmt_func

    def GetValue(self, childId):
        return (wx.ACC_OK, self._fmt_func(self._slider.GetValue()))


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
        super().__init__(parent, title=_("Options"),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)

        self.config_manager = config_manager
        self.theme_manager = theme_manager
        self.main_frame = parent
        self._applied_sections = set()  # Track which sections were applied via Apply buttons
        self._initial_device = config_manager.get('Audio', 'output_device', 'default')
        self._create_ui()
        self._fit_to_pages()
        size = self.GetSize()
        self.SetSize(max(size.width, 500), max(size.height, 380))
        self.SetMinSize(self.GetSize())

        # Apply theme to dialog if theme manager is available
        if self.theme_manager:
            self.theme_manager.apply_theme(self)

        # Focus category list on dialog open
        self.category_list.SetFocus()

    # Tab name constants matching book page order
    TAB_NAMES = ['general', 'audio', 'automation', 'recorder', 'streaming']

    def _create_ui(self):
        """Create dialog UI"""
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # ListBox (left) + page container (right) for option categories.
        # Uses manual Show/Hide instead of wx.Simplebook/Listbook/Notebook
        # to avoid focus-stealing and double screen reader announcements.
        book_sizer = wx.BoxSizer(wx.HORIZONTAL)

        page_names = [_("General"), _("Audio"), _("Automation"),
                      _("Recorder"), _("Streaming")]
        list_sizer = wx.BoxSizer(wx.VERTICAL)
        list_label = wx.StaticText(panel, label=_("Cate&gories"))
        list_sizer.Add(list_label, 0, wx.LEFT | wx.TOP | wx.BOTTOM, 5)
        self.category_list = wx.ListBox(panel, choices=page_names)
        self.category_list.SetName(_("Categories"))
        self.category_list.SetLabel(_("Categories"))
        self.category_list.SetSelection(0)
        list_sizer.Add(self.category_list, 1, wx.EXPAND | wx.ALL, 5)
        book_sizer.Add(list_sizer, 0, wx.EXPAND)

        self.page_container = wx.Panel(panel)
        self.page_sizer = wx.BoxSizer(wx.VERTICAL)
        self.pages = []

        # General page
        general_panel = self._create_general_tab(self.page_container)
        self.page_sizer.Add(general_panel, 1, wx.EXPAND)
        self.pages.append(general_panel)

        # Audio page
        audio_panel = self._create_audio_tab(self.page_container)
        self.page_sizer.Add(audio_panel, 1, wx.EXPAND)
        self.pages.append(audio_panel)

        # Automation page
        automation_panel = self._create_automation_tab(self.page_container)
        self.page_sizer.Add(automation_panel, 1, wx.EXPAND)
        self.pages.append(automation_panel)

        # Recorder page
        recorder_panel = self._create_recorder_tab(self.page_container)
        self.page_sizer.Add(recorder_panel, 1, wx.EXPAND)
        self.pages.append(recorder_panel)

        # Streaming page
        streaming_panel = self._create_streaming_tab(self.page_container)
        self.page_sizer.Add(streaming_panel, 1, wx.EXPAND)
        self.pages.append(streaming_panel)

        self.page_container.SetSizer(self.page_sizer)

        book_sizer.Add(self.page_container, 1, wx.EXPAND | wx.ALL, 5)

        main_sizer.Add(book_sizer, 1, wx.EXPAND | wx.ALL, 10)

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

        # Bind category selection to switch pages and update Apply button
        self.category_list.Bind(wx.EVT_LISTBOX, self._on_page_changed)

        # Bind change events on all controls to update Apply button state
        # Note: theme_choice is excluded here because it already has a dedicated
        # handler (_on_theme_change) for live preview, which also updates Apply state.
        for ctrl in (self.language_choice, self.deck_count_choice,
                     self.device_choice, self.buffer_choice, self.rate_choice,
                     self.format_choice, self.bitrate_choice, self.depth_choice):
            ctrl.Bind(wx.EVT_CHOICE, self._on_control_changed)

        for ctrl in (self.interval_spin, self.crossfade_spin,
                     self.threshold_spin, self.hysteresis_spin, self.hold_time_spin,
                     self.preroll_spin, self.wait_spin):
            ctrl.Bind(wx.EVT_SPINCTRL, self._on_control_changed)

        self.crossfade_check.Bind(wx.EVT_CHECKBOX, self._on_control_changed)
        self.level_switch_check.Bind(wx.EVT_CHECKBOX, self._on_control_changed)
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
        deck_label = wx.StaticText(panel, label=_("Number of decks") + ":")
        deck_sizer.Add(deck_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)

        current_deck_count = self.config_manager.get_deck_count()
        deck_choices = [str(n) for n in VALID_DECK_COUNTS]

        self.deck_count_choice = wx.Choice(panel, choices=deck_choices)
        self.deck_count_choice.SetName(_("Number of decks"))
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
        buffer_label = wx.StaticText(panel, label=_("Buffer size") + ":")
        buffer_sizer.Add(buffer_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)

        current_buffer = self.config_manager.getint('Audio', 'buffer_size', 2048)
        buffer_choices = ['512', '1024', '2048', '4096']

        self.buffer_choice = wx.Choice(panel, choices=buffer_choices)
        self.buffer_choice.SetName(_("Buffer size"))
        if str(current_buffer) in buffer_choices:
            self.buffer_choice.SetSelection(buffer_choices.index(str(current_buffer)))
        buffer_sizer.Add(self.buffer_choice, 1, wx.EXPAND | wx.ALL, 5)

        sizer.Add(buffer_sizer, 0, wx.EXPAND | wx.ALL, 5)

        # Sample rate
        rate_sizer = wx.BoxSizer(wx.HORIZONTAL)
        rate_label = wx.StaticText(panel, label=_("Sample rate") + ":")
        rate_sizer.Add(rate_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)

        current_rate = self.config_manager.getint('Audio', 'sample_rate', 44100)
        rate_choices = ['44100', '48000']

        self.rate_choice = wx.Choice(panel, choices=rate_choices)
        self.rate_choice.SetName(_("Sample rate"))
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

        # Separator
        sizer.Add(wx.StaticLine(panel), 0, wx.EXPAND | wx.ALL, 10)

        # Level-based switching header
        level_header = wx.StaticText(panel, label=_("Level-Based Switching"))
        header_font = level_header.GetFont()
        header_font.SetWeight(wx.FONTWEIGHT_BOLD)
        level_header.SetFont(header_font)
        sizer.Add(level_header, 0, wx.ALL, 5)

        # Enable level-based switching
        self.level_switch_check = wx.CheckBox(panel, label=_("Enable level-based switching"))
        self.level_switch_check.SetName(_("Enable level-based switching"))
        level_switch_enabled = self.config_manager.getboolean('Automation', 'level_switch_enabled', False)
        self.level_switch_check.SetValue(level_switch_enabled)
        sizer.Add(self.level_switch_check, 0, wx.ALL, 10)

        # Threshold
        threshold_sizer = wx.BoxSizer(wx.HORIZONTAL)
        threshold_label = wx.StaticText(panel, label=_("Threshold (dB)") + ":")
        threshold_sizer.Add(threshold_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)

        current_threshold = self.config_manager.getint('Automation', 'level_threshold_db', -30)
        self.threshold_spin = wx.SpinCtrl(panel, value=str(current_threshold),
                                          min=-60, max=0, initial=current_threshold)
        self.threshold_spin.SetName(_("Threshold (dB)"))
        threshold_sizer.Add(self.threshold_spin, 1, wx.EXPAND | wx.ALL, 5)

        sizer.Add(threshold_sizer, 0, wx.EXPAND | wx.ALL, 5)

        # Hysteresis
        hysteresis_sizer = wx.BoxSizer(wx.HORIZONTAL)
        hysteresis_label = wx.StaticText(panel, label=_("Hysteresis (dB)") + ":")
        hysteresis_sizer.Add(hysteresis_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)

        current_hysteresis = self.config_manager.getint('Automation', 'level_hysteresis_db', 3)
        self.hysteresis_spin = wx.SpinCtrl(panel, value=str(current_hysteresis),
                                           min=0, max=20, initial=current_hysteresis)
        self.hysteresis_spin.SetName(_("Hysteresis (dB)"))
        hysteresis_sizer.Add(self.hysteresis_spin, 1, wx.EXPAND | wx.ALL, 5)

        sizer.Add(hysteresis_sizer, 0, wx.EXPAND | wx.ALL, 5)

        # Hold time
        hold_sizer = wx.BoxSizer(wx.HORIZONTAL)
        hold_label = wx.StaticText(panel, label=_("Hold Time (seconds)") + ":")
        hold_sizer.Add(hold_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)

        current_hold = self.config_manager.getint('Automation', 'level_hold_time', 3)
        self.hold_time_spin = wx.SpinCtrl(panel, value=str(current_hold),
                                          min=1, max=30, initial=current_hold)
        self.hold_time_spin.SetName(_("Hold Time (seconds)"))
        hold_sizer.Add(self.hold_time_spin, 1, wx.EXPAND | wx.ALL, 5)

        sizer.Add(hold_sizer, 0, wx.EXPAND | wx.ALL, 5)

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

        browse_btn = wx.Button(panel, label=_("Browse") + "...")
        browse_btn.SetName(_("Browse") + "...")
        browse_btn.Bind(wx.EVT_BUTTON, self._on_browse_output_dir)
        dir_sizer.Add(browse_btn, 0, wx.ALL, 5)

        sizer.Add(dir_sizer, 0, wx.EXPAND | wx.ALL, 5)

        panel.SetSizer(sizer)
        return panel

    def _on_browse_output_dir(self, event):
        """Handle browse button for output directory"""
        dlg = wx.DirDialog(self, _("Choose recording output directory"))
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
                self.level_switch_check.GetValue(),
                self.threshold_spin.GetValue(),
                self.hysteresis_spin.GetValue(),
                self.hold_time_spin.GetValue(),
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
                self.level_switch_check.GetValue(),
                self.threshold_spin.GetValue(),
                self.hysteresis_spin.GetValue(),
                self.hold_time_spin.GetValue(),
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
        """Get the name of the currently active tab"""
        idx = self.category_list.GetSelection()
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
        """Handle category selection change - switch page and update Apply button"""
        event.Skip()
        self._show_page(self.category_list.GetSelection())
        self._update_apply_state()

    def _show_page(self, idx):
        """Show page at idx, hide and disable all others."""
        for i, page in enumerate(self.pages):
            active = (i == idx)
            page.Show(active)
            page.Enable(active)
        self.page_container.Layout()

    def _fit_to_pages(self):
        """Set page_container minimum size to the largest page, then Fit().

        All pages must be visible when this is called so their best sizes
        are correctly reported. After measuring, only page 0 is shown.
        """
        max_w, max_h = 0, 0
        for page in self.pages:
            best = page.GetBestSize()
            max_w = max(max_w, best.width)
            max_h = max(max_h, best.height)
        self.page_container.SetMinSize((max_w, max_h))
        self._show_page(0)
        self.Fit()

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
        self.config_manager.set('Automation', 'level_switch_enabled', self.level_switch_check.GetValue())
        self.config_manager.set('Automation', 'level_threshold_db', self.threshold_spin.GetValue())
        self.config_manager.set('Automation', 'level_hysteresis_db', self.hysteresis_spin.GetValue())
        self.config_manager.set('Automation', 'level_hold_time', self.hold_time_spin.GetValue())

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


class CustomTextEntryDialog(wx.Dialog):
    """Custom text entry dialog with translatable button labels"""

    def __init__(self, parent, message, caption, default_value=""):
        """
        Initialize custom text entry dialog.

        Args:
            parent: Parent window (MainFrame)
            message: text input message
            caption: text input caption
            default_value: optional default value
        """
        super().__init__(parent, title=caption)

        sizer = wx.BoxSizer(wx.VERTICAL)

        # Message
        text = wx.StaticText(self, label=message)
        sizer.Add(text, 0, wx.ALL, 10)

        # Text input
        self.text_ctrl = wx.TextCtrl(self, value=default_value)
        sizer.Add(self.text_ctrl, 0, wx.EXPAND | wx.ALL, 10)

        # Buttons
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        ok_button = wx.Button(self, wx.ID_OK, _("&OK"))
        cancel_button = wx.Button(self, wx.ID_CANCEL, _("&Cancel"))

        ok_button.SetDefault()  # OK as default button

        button_sizer.Add(ok_button, 0, wx.ALL, 5)
        button_sizer.Add(cancel_button, 0, wx.ALL, 5)

        sizer.Add(button_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

        self.SetSizer(sizer)
        self.Fit()
        self.Center()

        self.text_ctrl.SetFocus()

    def GetValue(self):
        """Return value from custom text entry dialog"""
        return self.text_ctrl.GetValue()


class EffectsDialog(wx.Dialog):
    """Modeless dialog for real-time audio effect controls."""

    def __init__(self, parent, mixer):
        """
        Initialize effects dialog.

        Args:
            parent: Parent window (MainFrame)
            mixer: Mixer instance with master_effects and per-deck effect chains
        """
        super().__init__(parent, title=_("Audio Effects"),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)

        self.mixer = mixer
        self.main_frame = parent

        self._create_ui()
        self._fit_to_pages()
        # ScrolledWindow pages report small minimum height (content scrolls),
        # so ensure a reasonable default size while respecting GTK minimums.
        size = self.GetSize()
        self.SetSize(max(size.width, 700), max(size.height, 600))
        self.SetMinSize(size)
        self.Center()

        # Apply theme
        if hasattr(parent, 'theme_manager') and parent.theme_manager:
            parent.theme_manager.apply_theme(self)

        # Focus category list on dialog open
        self.category_list.SetFocus()

        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)

    def _on_char_hook(self, event):
        """Close dialog on Escape key."""
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.Close()
        else:
            event.Skip()

    def _on_close(self, event):
        """Handle dialog close - clear reference in main frame."""
        if hasattr(self.main_frame, '_effects_dialog'):
            self.main_frame._effects_dialog = None
        self.Destroy()

    def _on_page_changed(self, event):
        """Handle category selection change - switch page."""
        event.Skip()
        self._show_page(self.category_list.GetSelection())

    def _show_page(self, idx):
        """Show page at idx, hide and disable all others."""
        for i, page in enumerate(self.pages):
            active = (i == idx)
            page.Show(active)
            page.Enable(active)
        self.page_container.Layout()

    def _fit_to_pages(self):
        """Set page_container minimum size to the largest page, then Fit().

        All pages must be visible when this is called so their best sizes
        are correctly reported. After measuring, only page 0 is shown.
        """
        max_w, max_h = 0, 0
        for page in self.pages:
            best = page.GetBestSize()
            max_w = max(max_w, best.width)
            max_h = max(max_h, best.height)
        self.page_container.SetMinSize((max_w, max_h))
        self._show_page(0)
        self.Fit()

    def _create_ui(self):
        """Create the dialog UI with ListBox + page container."""
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        book_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Build page names list
        page_names = [_("Master Effects")]
        for deck in self.mixer.decks:
            if deck.effects:
                page_names.append(deck.name)

        wx.StaticText(panel, label=_("&Effect Chains"))
        self.category_list = wx.ListBox(panel, choices=page_names)
        self.category_list.SetName(_("Effect Chains"))
        self.category_list.SetLabel(_("Effect Chains"))
        self.category_list.SetSelection(0)
        book_sizer.Add(self.category_list, 0, wx.EXPAND | wx.ALL, 5)

        self.page_container = wx.Panel(panel)
        self.page_sizer = wx.BoxSizer(wx.VERTICAL)
        self.pages = []

        # Master effects page
        master_panel = self._create_effect_panel(
            self.page_container, self.mixer.master_effects, _("Master"))
        self.page_sizer.Add(master_panel, 1, wx.EXPAND)
        self.pages.append(master_panel)

        # Per-deck pages
        for deck in self.mixer.decks:
            if deck.effects:
                deck_panel = self._create_effect_panel(
                    self.page_container, deck.effects, deck.name)
                self.page_sizer.Add(deck_panel, 1, wx.EXPAND)
                self.pages.append(deck_panel)

        self.page_container.SetSizer(self.page_sizer)

        book_sizer.Add(self.page_container, 1, wx.EXPAND | wx.ALL, 5)

        self.category_list.Bind(wx.EVT_LISTBOX, self._on_page_changed)

        main_sizer.Add(book_sizer, 1, wx.EXPAND | wx.ALL, 5)

        # Close button
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.AddStretchSpacer()
        close_btn = wx.Button(panel, wx.ID_CLOSE, _("&Close"))
        close_btn.Bind(wx.EVT_BUTTON, lambda e: self.Close())
        button_sizer.Add(close_btn, 0, wx.ALL, 5)
        main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.BOTTOM | wx.RIGHT, 5)

        panel.SetSizer(main_sizer)

    def _create_effect_panel(self, parent, effect_chain, chain_name):
        """Create a scrolled panel with all effect controls for one chain."""
        panel = wx.ScrolledWindow(parent)
        panel.SetScrollRate(0, 10)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Global enable
        enable_cb = wx.CheckBox(panel, label=_("Enable effects for {}").format(chain_name))
        enable_cb.SetValue(effect_chain.enabled)
        enable_cb.Bind(wx.EVT_CHECKBOX,
                       lambda e: self._set_chain_enabled(effect_chain, e.IsChecked()))
        sizer.Add(enable_cb, 0, wx.ALL, 10)

        sizer.Add(wx.StaticLine(panel), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        # Reverb
        sizer.Add(self._create_reverb_section(panel, effect_chain, chain_name),
                  0, wx.EXPAND | wx.ALL, 5)
        # Delay
        sizer.Add(self._create_delay_section(panel, effect_chain, chain_name),
                  0, wx.EXPAND | wx.ALL, 5)
        # EQ
        sizer.Add(self._create_eq_section(panel, effect_chain, chain_name),
                  0, wx.EXPAND | wx.ALL, 5)
        # Chorus
        sizer.Add(self._create_chorus_section(panel, effect_chain, chain_name),
                  0, wx.EXPAND | wx.ALL, 5)
        # Compressor
        sizer.Add(self._create_compressor_section(panel, effect_chain, chain_name),
                  0, wx.EXPAND | wx.ALL, 5)
        # Limiter
        sizer.Add(self._create_limiter_section(panel, effect_chain, chain_name),
                  0, wx.EXPAND | wx.ALL, 5)
        # Gain
        sizer.Add(self._create_gain_section(panel, effect_chain, chain_name),
                  0, wx.EXPAND | wx.ALL, 5)
        panel.SetSizer(sizer)
        panel.FitInside()
        return panel

    def _set_chain_enabled(self, effect_chain, enabled):
        effect_chain.enabled = enabled

    # --- Reverb ---

    def _create_reverb_section(self, parent, chain, name):
        section_panel = wx.Panel(parent)
        section_sizer = wx.BoxSizer(wx.VERTICAL)
        box = wx.StaticBoxSizer(wx.VERTICAL, section_panel, _("Reverb"))
        sb = box.GetStaticBox()
        sliders = []

        cb = wx.CheckBox(sb, label=_("Enable"))
        cb.SetName(f"{name}: {_('Enable Reverb')}")
        cb.SetValue(chain.reverb_enabled)
        box.Add(cb, 0, wx.ALL, 5)

        if chain.reverb is not None:
            box.Add(self._make_slider(
                sb, _("Room Size"), name,
                int(chain.reverb.room_size * 100), 0, 100,
                lambda v: chain.set_reverb_param(room_size=v / 100.0),
                fmt_func=lambda v: f"{v}%", collect=sliders),
                0, wx.EXPAND | wx.ALL, 3)

            box.Add(self._make_slider(
                sb, _("Damping"), name,
                int(chain.reverb.damping * 100), 0, 100,
                lambda v: chain.set_reverb_param(damping=v / 100.0),
                fmt_func=lambda v: f"{v}%", collect=sliders),
                0, wx.EXPAND | wx.ALL, 3)

            box.Add(self._make_slider(
                sb, _("Wet Level"), name,
                int(chain.reverb.wet_level * 100), 0, 100,
                lambda v: chain.set_reverb_param(wet_level=v / 100.0),
                fmt_func=lambda v: f"{v}%", collect=sliders),
                0, wx.EXPAND | wx.ALL, 3)

            box.Add(self._make_slider(
                sb, _("Dry Level"), name,
                int(chain.reverb.dry_level * 100), 0, 100,
                lambda v: chain.set_reverb_param(dry_level=v / 100.0),
                fmt_func=lambda v: f"{v}%", collect=sliders),
                0, wx.EXPAND | wx.ALL, 3)

            box.Add(self._make_slider(
                sb, _("Width"), name,
                int(chain.reverb.width * 100), 0, 100,
                lambda v: chain.set_reverb_param(width=v / 100.0),
                fmt_func=lambda v: f"{v}%", collect=sliders),
                0, wx.EXPAND | wx.ALL, 3)

        self._set_sliders_enabled(sliders, chain.reverb_enabled)
        cb.Bind(wx.EVT_CHECKBOX, lambda e, s=sliders: (
            chain.enable_effect('reverb', e.IsChecked()),
            self._set_sliders_enabled(s, e.IsChecked())))

        section_sizer.Add(box, 1, wx.EXPAND)
        section_panel.SetSizer(section_sizer)
        return section_panel

    # --- Delay ---

    def _create_delay_section(self, parent, chain, name):
        section_panel = wx.Panel(parent)
        section_sizer = wx.BoxSizer(wx.VERTICAL)
        box = wx.StaticBoxSizer(wx.VERTICAL, section_panel, _("Delay"))
        sb = box.GetStaticBox()
        sliders = []

        cb = wx.CheckBox(sb, label=_("Enable"))
        cb.SetName(f"{name}: {_('Enable Delay')}")
        cb.SetValue(chain.delay_enabled)
        box.Add(cb, 0, wx.ALL, 5)

        if chain.delay is not None:
            # Delay time: 0 to 2000 ms (mapped to 0.0 - 2.0 s)
            box.Add(self._make_slider(
                sb, _("Delay Time"), name,
                int(chain.delay.delay_seconds * 1000), 0, 2000,
                lambda v: chain.set_delay_param(delay_seconds=v / 1000.0),
                fmt_func=lambda v: f"{v} ms", collect=sliders),
                0, wx.EXPAND | wx.ALL, 3)

            box.Add(self._make_slider(
                sb, _("Feedback"), name,
                int(chain.delay.feedback * 100), 0, 95,
                lambda v: chain.set_delay_param(feedback=v / 100.0),
                fmt_func=lambda v: f"{v}%", collect=sliders),
                0, wx.EXPAND | wx.ALL, 3)

            box.Add(self._make_slider(
                sb, _("Mix"), name,
                int(chain.delay.mix * 100), 0, 100,
                lambda v: chain.set_delay_param(mix=v / 100.0),
                fmt_func=lambda v: f"{v}%", collect=sliders),
                0, wx.EXPAND | wx.ALL, 3)

        self._set_sliders_enabled(sliders, chain.delay_enabled)
        cb.Bind(wx.EVT_CHECKBOX, lambda e, s=sliders: (
            chain.enable_effect('delay', e.IsChecked()),
            self._set_sliders_enabled(s, e.IsChecked())))

        section_sizer.Add(box, 1, wx.EXPAND)
        section_panel.SetSizer(section_sizer)
        return section_panel

    # --- EQ ---

    def _create_eq_section(self, parent, chain, name):
        section_panel = wx.Panel(parent)
        section_sizer = wx.BoxSizer(wx.VERTICAL)
        box = wx.StaticBoxSizer(wx.VERTICAL, section_panel, _("Equalizer"))
        sb = box.GetStaticBox()
        sliders = []

        cb = wx.CheckBox(sb, label=_("Enable"))
        cb.SetName(f"{name}: {_('Enable Equalizer')}")
        cb.SetValue(chain.eq_enabled)
        box.Add(cb, 0, wx.ALL, 5)

        if chain.eq_low is not None:
            # EQ gains: -12 to +12 dB
            box.Add(self._make_slider(
                sb, _("Bass (200 Hz)"), name,
                int(chain.eq_low.gain_db), -12, 12,
                lambda v: chain.set_eq_param('low', gain_db=float(v)),
                fmt_func=lambda v: f"{v:+d} dB", collect=sliders),
                0, wx.EXPAND | wx.ALL, 3)

            box.Add(self._make_slider(
                sb, _("Mid (1 kHz)"), name,
                int(chain.eq_mid.gain_db), -12, 12,
                lambda v: chain.set_eq_param('mid', gain_db=float(v)),
                fmt_func=lambda v: f"{v:+d} dB", collect=sliders),
                0, wx.EXPAND | wx.ALL, 3)

            box.Add(self._make_slider(
                sb, _("Treble (8 kHz)"), name,
                int(chain.eq_high.gain_db), -12, 12,
                lambda v: chain.set_eq_param('high', gain_db=float(v)),
                fmt_func=lambda v: f"{v:+d} dB", collect=sliders),
                0, wx.EXPAND | wx.ALL, 3)

        self._set_sliders_enabled(sliders, chain.eq_enabled)
        cb.Bind(wx.EVT_CHECKBOX, lambda e, s=sliders: (
            chain.enable_effect('eq', e.IsChecked()),
            self._set_sliders_enabled(s, e.IsChecked())))

        section_sizer.Add(box, 1, wx.EXPAND)
        section_panel.SetSizer(section_sizer)
        return section_panel

    # --- Chorus ---

    def _create_chorus_section(self, parent, chain, name):
        section_panel = wx.Panel(parent)
        section_sizer = wx.BoxSizer(wx.VERTICAL)
        box = wx.StaticBoxSizer(wx.VERTICAL, section_panel, _("Chorus"))
        sb = box.GetStaticBox()
        sliders = []

        cb = wx.CheckBox(sb, label=_("Enable"))
        cb.SetName(f"{name}: {_('Enable Chorus')}")
        cb.SetValue(chain.chorus_enabled)
        box.Add(cb, 0, wx.ALL, 5)

        if chain.chorus is not None:
            # Rate: 0.1 to 10 Hz (slider 1-100 mapped to 0.1-10.0)
            box.Add(self._make_slider(
                sb, _("Rate"), name,
                int(chain.chorus.rate_hz * 10), 1, 100,
                lambda v: chain.set_chorus_param(rate_hz=v / 10.0),
                fmt_func=lambda v: f"{v / 10.0:.1f} Hz", collect=sliders),
                0, wx.EXPAND | wx.ALL, 3)

            box.Add(self._make_slider(
                sb, _("Depth"), name,
                int(chain.chorus.depth * 100), 0, 100,
                lambda v: chain.set_chorus_param(depth=v / 100.0),
                fmt_func=lambda v: f"{v}%", collect=sliders),
                0, wx.EXPAND | wx.ALL, 3)

            box.Add(self._make_slider(
                sb, _("Mix"), name,
                int(chain.chorus.mix * 100), 0, 100,
                lambda v: chain.set_chorus_param(mix=v / 100.0),
                fmt_func=lambda v: f"{v}%", collect=sliders),
                0, wx.EXPAND | wx.ALL, 3)

        self._set_sliders_enabled(sliders, chain.chorus_enabled)
        cb.Bind(wx.EVT_CHECKBOX, lambda e, s=sliders: (
            chain.enable_effect('chorus', e.IsChecked()),
            self._set_sliders_enabled(s, e.IsChecked())))

        section_sizer.Add(box, 1, wx.EXPAND)
        section_panel.SetSizer(section_sizer)
        return section_panel

    # --- Compressor ---

    def _create_compressor_section(self, parent, chain, name):
        section_panel = wx.Panel(parent)
        section_sizer = wx.BoxSizer(wx.VERTICAL)
        box = wx.StaticBoxSizer(wx.VERTICAL, section_panel, _("Compressor"))
        sb = box.GetStaticBox()
        sliders = []

        cb = wx.CheckBox(sb, label=_("Enable"))
        cb.SetName(f"{name}: {_('Enable Compressor')}")
        cb.SetValue(chain.compressor_enabled)
        box.Add(cb, 0, wx.ALL, 5)

        if chain.compressor is not None:
            # Threshold: -60 to 0 dB
            box.Add(self._make_slider(
                sb, _("Threshold"), name,
                int(chain.compressor.threshold_db), -60, 0,
                lambda v: chain.set_compressor_param(threshold_db=float(v)),
                fmt_func=lambda v: f"{v} dB", collect=sliders),
                0, wx.EXPAND | wx.ALL, 3)

            # Ratio: 1 to 20 (slider 10-200, mapped to 1.0-20.0)
            box.Add(self._make_slider(
                sb, _("Ratio"), name,
                int(chain.compressor.ratio * 10), 10, 200,
                lambda v: chain.set_compressor_param(ratio=v / 10.0),
                fmt_func=lambda v: f"{v / 10.0:.1f}:1", collect=sliders),
                0, wx.EXPAND | wx.ALL, 3)

            # Attack: 0.1 to 100 ms (slider 1-1000, mapped to 0.1-100.0)
            box.Add(self._make_slider(
                sb, _("Attack"), name,
                int(chain.compressor.attack_ms * 10), 1, 1000,
                lambda v: chain.set_compressor_param(attack_ms=v / 10.0),
                fmt_func=lambda v: f"{v / 10.0:.1f} ms", collect=sliders),
                0, wx.EXPAND | wx.ALL, 3)

            # Release: 1 to 500 ms
            box.Add(self._make_slider(
                sb, _("Release"), name,
                int(chain.compressor.release_ms), 1, 500,
                lambda v: chain.set_compressor_param(release_ms=float(v)),
                fmt_func=lambda v: f"{v} ms", collect=sliders),
                0, wx.EXPAND | wx.ALL, 3)

        self._set_sliders_enabled(sliders, chain.compressor_enabled)
        cb.Bind(wx.EVT_CHECKBOX, lambda e, s=sliders: (
            chain.enable_effect('compressor', e.IsChecked()),
            self._set_sliders_enabled(s, e.IsChecked())))

        section_sizer.Add(box, 1, wx.EXPAND)
        section_panel.SetSizer(section_sizer)
        return section_panel

    # --- Limiter ---

    def _create_limiter_section(self, parent, chain, name):
        section_panel = wx.Panel(parent)
        section_sizer = wx.BoxSizer(wx.VERTICAL)
        box = wx.StaticBoxSizer(wx.VERTICAL, section_panel, _("Limiter"))
        sb = box.GetStaticBox()
        sliders = []

        cb = wx.CheckBox(sb, label=_("Enable"))
        cb.SetName(f"{name}: {_('Enable Limiter')}")
        cb.SetValue(chain.limiter_enabled)
        box.Add(cb, 0, wx.ALL, 5)

        if chain.limiter is not None:
            # Threshold: -30 to 0 dB
            box.Add(self._make_slider(
                sb, _("Threshold"), name,
                int(chain.limiter.threshold_db), -30, 0,
                lambda v: chain.set_limiter_param(threshold_db=float(v)),
                fmt_func=lambda v: f"{v} dB", collect=sliders),
                0, wx.EXPAND | wx.ALL, 3)

            # Release: 1 to 500 ms
            box.Add(self._make_slider(
                sb, _("Release"), name,
                int(chain.limiter.release_ms), 1, 500,
                lambda v: chain.set_limiter_param(release_ms=float(v)),
                fmt_func=lambda v: f"{v} ms", collect=sliders),
                0, wx.EXPAND | wx.ALL, 3)

        self._set_sliders_enabled(sliders, chain.limiter_enabled)
        cb.Bind(wx.EVT_CHECKBOX, lambda e, s=sliders: (
            chain.enable_effect('limiter', e.IsChecked()),
            self._set_sliders_enabled(s, e.IsChecked())))

        section_sizer.Add(box, 1, wx.EXPAND)
        section_panel.SetSizer(section_sizer)
        return section_panel

    # --- Gain ---

    def _create_gain_section(self, parent, chain, name):
        section_panel = wx.Panel(parent)
        section_sizer = wx.BoxSizer(wx.VERTICAL)
        box = wx.StaticBoxSizer(wx.VERTICAL, section_panel, _("Gain"))
        sb = box.GetStaticBox()
        sliders = []

        cb = wx.CheckBox(sb, label=_("Enable"))
        cb.SetName(f"{name}: {_('Enable Gain')}")
        cb.SetValue(chain.gain_enabled)
        box.Add(cb, 0, wx.ALL, 5)

        if chain.gain is not None:
            # Gain: -24 to +24 dB
            box.Add(self._make_slider(
                sb, _("Gain"), name,
                int(chain.gain.gain_db), -24, 24,
                lambda v: chain.set_gain_param(gain_db=float(v)),
                fmt_func=lambda v: f"{v:+d} dB", collect=sliders),
                0, wx.EXPAND | wx.ALL, 3)

        self._set_sliders_enabled(sliders, chain.gain_enabled)
        cb.Bind(wx.EVT_CHECKBOX, lambda e, s=sliders: (
            chain.enable_effect('gain', e.IsChecked()),
            self._set_sliders_enabled(s, e.IsChecked())))

        section_sizer.Add(box, 1, wx.EXPAND)
        section_panel.SetSizer(section_sizer)
        return section_panel

    # --- Slider helper ---

    @staticmethod
    def _set_sliders_enabled(sliders, enabled):
        """Enable or disable a list of sliders."""
        for s in sliders:
            s.Enable(enabled)

    def _make_slider(self, parent, label, chain_name, value, min_val, max_val,
                     callback, fmt_func=None, collect=None):
        """
        Create a labeled slider with value display.

        Args:
            parent: Parent window
            label: Parameter label text
            chain_name: Name of the effect chain (for accessibility)
            value: Initial slider value
            min_val: Minimum slider value
            max_val: Maximum slider value
            callback: Function called with slider value on change
            fmt_func: Optional function to format the display value
            collect: Optional list to append the slider widget to
        """
        sizer = wx.BoxSizer(wx.HORIZONTAL)

        lbl = wx.StaticText(parent, label=label + ":", size=(120, -1))
        sizer.Add(lbl, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)

        if fmt_func is None:
            fmt_func = lambda v: str(v)

        slider = wx.Slider(parent, value=value, minValue=min_val, maxValue=max_val,
                           style=wx.SL_HORIZONTAL)
        slider.SetName(f"{chain_name}: {label}")
        if sys.platform == 'win32':
            slider.SetAccessible(_FormattedSliderAccessible(slider, fmt_func))
        sizer.Add(slider, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 5)

        val_lbl = wx.StaticText(parent, label=fmt_func(value), size=(70, -1),
                                style=wx.ALIGN_RIGHT)
        if sys.platform == 'win32':
            val_lbl.SetAccessible(_ValueDisplayAccessible(val_lbl))
        sizer.Add(val_lbl, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)

        def on_slider(event):
            v = slider.GetValue()
            val_lbl.SetLabel(fmt_func(v))
            callback(v)

        slider.Bind(wx.EVT_SLIDER, on_slider)

        if collect is not None:
            collect.append(slider)

        return sizer
