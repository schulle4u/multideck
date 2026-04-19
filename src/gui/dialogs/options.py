"""
Options dialog for MultiDeck Audio Player
"""

import wx
import sys
import sounddevice as sd
from utils.i18n import _, LANGUAGE_NAMES
from config.defaults import VALID_DECK_RANGE
from utils.helpers import check_ffmpeg
from gui.dialogs.custom import AccessibleSpinCtrl


FFMPEG_AVAILABLE = check_ffmpeg()


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
        self.SetMinSize(self.GetSize())
        self.Center()

        # Apply theme to dialog if theme manager is available
        if self.theme_manager:
            self.theme_manager.apply_theme(self)

        # Focus category list on dialog open
        self.category_list.SetFocus()

        if sys.platform != 'win32':
            self.Bind(wx.EVT_SHOW, self._on_first_show)

    # Tab name constants matching book page order
    TAB_NAMES = ['general', 'audio', 'automation', 'recorder', 'streaming', 'tts']

    def _on_first_show(self, event):
        """Pre-size hidden pages after realization to avoid layout warnings on Linux."""
        event.Skip()
        if not event.IsShown():
            return
        self.Unbind(wx.EVT_SHOW)
        sz = self.page_container.GetClientSize()
        if sz.width > 0 and sz.height > 0:
            for page in self.pages:
                if not page.IsShown():
                    page.SetSize(0, 0, sz.width, sz.height)
                    page.Layout()

    def _create_ui(self):
        """Create dialog UI"""
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # ListBox (left) + page container (right) for option categories.
        # Uses manual Show/Hide instead of wx.Simplebook/Listbook/Notebook
        # to avoid focus-stealing and double screen reader announcements.
        book_sizer = wx.BoxSizer(wx.HORIZONTAL)

        page_names = [_("General"), _("Audio"), _("Automation"),
                      _("Recorder"), _("Streaming"), _("Text-to-Speech")]
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

        # Remaining pages hidden at creation; shown on demand via _show_page()
        audio_panel = self._create_audio_tab(self.page_container)
        audio_panel.Show(False)
        self.page_sizer.Add(audio_panel, 1, wx.EXPAND)
        self.pages.append(audio_panel)

        # Automation page (hidden at creation)
        automation_panel = self._create_automation_tab(self.page_container)
        automation_panel.Show(False)
        self.page_sizer.Add(automation_panel, 1, wx.EXPAND)
        self.pages.append(automation_panel)

        # Recorder page (hidden at creation)
        recorder_panel = self._create_recorder_tab(self.page_container)
        recorder_panel.Show(False)
        self.page_sizer.Add(recorder_panel, 1, wx.EXPAND)
        self.pages.append(recorder_panel)

        # Streaming page (hidden at creation)
        streaming_panel = self._create_streaming_tab(self.page_container)
        streaming_panel.Show(False)
        self.page_sizer.Add(streaming_panel, 1, wx.EXPAND)
        self.pages.append(streaming_panel)

        # Text-to-Speech page (hidden at creation)
        tts_panel = self._create_tts_tab(self.page_container)
        tts_panel.Show(False)
        self.page_sizer.Add(tts_panel, 1, wx.EXPAND)
        self.pages.append(tts_panel)

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
        for ctrl in (self.language_choice, self.list_style_choice,
                     self.device_choice, self.buffer_choice, self.rate_choice,
                     self.format_choice, self.bitrate_choice, self.depth_choice):
            ctrl.Bind(wx.EVT_CHOICE, self._on_control_changed)

        for ctrl in (self.deck_count_spin, self.interval_spin,
                     self.threshold_spin, self.hysteresis_spin, self.hold_time_spin,
                     self.preroll_spin, self.wait_spin):
            ctrl.Bind(wx.EVT_SPINCTRL, self._on_control_changed)

        self.crossfade_ctrl.Bind(wx.EVT_SPINCTRLDOUBLE, self._on_control_changed)
        self.crossfade_check.Bind(wx.EVT_CHECKBOX, self._on_control_changed)
        self.level_switch_check.Bind(wx.EVT_CHECKBOX, self._on_control_changed)
        self.auto_reconnect_check.Bind(wx.EVT_CHECKBOX, self._on_control_changed)
        self.output_dir_text.Bind(wx.EVT_TEXT, self._on_control_changed)

        self.tts_enabled_check.Bind(wx.EVT_CHECKBOX, self._on_control_changed)
        self.tts_engine_choice.Bind(wx.EVT_CHOICE, self._on_tts_engine_changed)
        self.tts_voice_choice.Bind(wx.EVT_CHOICE, self._on_control_changed)
        self.tts_rate_spin.Bind(wx.EVT_SPINCTRL, self._on_control_changed)
        self.tts_volume_spin.Bind(wx.EVT_SPINCTRL, self._on_control_changed)

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

        current_deck_count = self.config_manager.getint('General', 'deck_count', 10)

        self.deck_count_spin = wx.SpinCtrl(panel, value=str(current_deck_count),
                                         min=min(VALID_DECK_RANGE), max=max(VALID_DECK_RANGE), initial=current_deck_count)
        self.deck_count_spin.SetName(_("Number of decks"))
        deck_sizer.Add(self.deck_count_spin, 1, wx.EXPAND | wx.ALL, 5)

        sizer.Add(deck_sizer, 0, wx.EXPAND | wx.ALL, 5)

        # Deck list style
        list_style_sizer = wx.BoxSizer(wx.HORIZONTAL)
        list_style_label = wx.StaticText(panel, label=_("Deck list style") + ":")
        list_style_sizer.Add(list_style_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)

        current_list_style = self.config_manager.get('General', 'deck_list_style', 'compact')
        list_style_choices = [_("Compact"), _("Detailed")]
        list_style_values = ['compact', 'detailed']

        self.list_style_choice = wx.Choice(panel, choices=list_style_choices)
        self.list_style_choice.SetName(_("Deck list style"))
        if current_list_style in list_style_values:
            self.list_style_choice.SetSelection(list_style_values.index(current_list_style))
        self.list_style_values = list_style_values
        list_style_sizer.Add(self.list_style_choice, 1, wx.EXPAND | wx.ALL, 5)

        sizer.Add(list_style_sizer, 0, wx.EXPAND | wx.ALL, 5)

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

        # Crossfade duration (in seconds)
        label_text = _("Crossfade Duration (seconds)")
        current_duration = self.config_manager.getfloat('Automation', 'crossfade_duration', 2.0)

        # Create the custom control (it's a sizer)
        self.crossfade_ctrl = AccessibleSpinCtrl(
            panel, 
            label_text=label_text + ":", 
            initial_val=current_duration, 
            min_val=0.5, 
            max_val=10.0, 
            inc=0.1
        )

        sizer.Add(self.crossfade_ctrl, 0, wx.EXPAND | wx.ALL, 5)

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

    def _create_tts_tab(self, parent):
        """Create text-to-speech options tab"""
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)

        tts_mgr = self.main_frame.tts_manager

        # Enable TTS
        self.tts_enabled_check = wx.CheckBox(panel, label=_("Enable text-to-speech announcements"))
        self.tts_enabled_check.SetName(_("Enable text-to-speech announcements"))
        self.tts_enabled_check.SetValue(
            self.config_manager.getboolean('TTS', 'tts_enabled', False)
        )
        sizer.Add(self.tts_enabled_check, 0, wx.ALL, 10)

        # Engine
        engine_sizer = wx.BoxSizer(wx.HORIZONTAL)
        engine_label = wx.StaticText(panel, label=_("Engine") + ":")
        engine_sizer.Add(engine_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)

        engine_entries = tts_mgr.get_available_engines()
        self._tts_engine_values = [e[1] for e in engine_entries]
        engine_labels = [e[0] for e in engine_entries]

        self.tts_engine_choice = wx.Choice(panel, choices=engine_labels)
        self.tts_engine_choice.SetName(_("Engine"))
        current_engine = self.config_manager.get('TTS', 'tts_engine', '')
        if current_engine in self._tts_engine_values:
            self.tts_engine_choice.SetSelection(self._tts_engine_values.index(current_engine))
        else:
            self.tts_engine_choice.SetSelection(0)
        engine_sizer.Add(self.tts_engine_choice, 1, wx.EXPAND | wx.ALL, 5)
        sizer.Add(engine_sizer, 0, wx.EXPAND | wx.ALL, 5)

        # Voice
        voice_sizer = wx.BoxSizer(wx.HORIZONTAL)
        voice_label = wx.StaticText(panel, label=_("Voice") + ":")
        voice_sizer.Add(voice_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)

        selected_engine = self._tts_engine_values[self.tts_engine_choice.GetSelection()]
        voices = tts_mgr.get_available_voices(selected_engine)
        self._tts_voice_names = [v[0] for v in voices]
        if not self._tts_voice_names:
            self._tts_voice_names = [_("(default)")]

        self.tts_voice_choice = wx.Choice(panel, choices=self._tts_voice_names)
        self.tts_voice_choice.SetName(_("Voice"))
        current_voice = self.config_manager.get('TTS', 'tts_voice', '')
        if current_voice in self._tts_voice_names:
            self.tts_voice_choice.SetSelection(self._tts_voice_names.index(current_voice))
        else:
            self.tts_voice_choice.SetSelection(0)
        voice_sizer.Add(self.tts_voice_choice, 1, wx.EXPAND | wx.ALL, 5)
        sizer.Add(voice_sizer, 0, wx.EXPAND | wx.ALL, 5)

        # Rate
        rate_sizer = wx.BoxSizer(wx.HORIZONTAL)
        rate_label = wx.StaticText(panel, label=_("Rate (WPM, 0=default)") + ":")
        rate_sizer.Add(rate_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)

        current_rate = self.config_manager.getint('TTS', 'tts_rate', 0)
        self.tts_rate_spin = wx.SpinCtrl(panel, value=str(current_rate),
                                         min=0, max=400, initial=current_rate)
        self.tts_rate_spin.SetName(_("Rate (WPM, 0=default)"))
        rate_sizer.Add(self.tts_rate_spin, 1, wx.EXPAND | wx.ALL, 5)
        sizer.Add(rate_sizer, 0, wx.EXPAND | wx.ALL, 5)

        # Volume
        vol_sizer = wx.BoxSizer(wx.HORIZONTAL)
        vol_label = wx.StaticText(panel, label=_("Volume (%, -1=default)") + ":")
        vol_sizer.Add(vol_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)

        current_vol = self.config_manager.getint('TTS', 'tts_volume', -1)
        self.tts_volume_spin = wx.SpinCtrl(panel, value=str(current_vol),
                                           min=-1, max=100, initial=current_vol)
        self.tts_volume_spin.SetName(_("Volume (%, -1=default)"))
        vol_sizer.Add(self.tts_volume_spin, 1, wx.EXPAND | wx.ALL, 5)
        sizer.Add(vol_sizer, 0, wx.EXPAND | wx.ALL, 5)

        # Test button
        test_btn = wx.Button(panel, label=_("Test voice"))
        test_btn.SetName(_("Test voice"))
        test_btn.Bind(wx.EVT_BUTTON, self._on_tts_test)
        sizer.Add(test_btn, 0, wx.ALL, 10)

        panel.SetSizer(sizer)
        return panel

    def _on_tts_engine_changed(self, event):
        """Reload voice list when engine selection changes"""
        engine_idx = self.tts_engine_choice.GetSelection()
        if 0 <= engine_idx < len(self._tts_engine_values):
            engine_name = self._tts_engine_values[engine_idx]
        else:
            engine_name = ''
        voices = self.main_frame.tts_manager.get_available_voices(engine_name)
        self._tts_voice_names = [v[0] for v in voices]
        if not self._tts_voice_names:
            self._tts_voice_names = [_("(default)")]
        self.tts_voice_choice.Set(self._tts_voice_names)
        self.tts_voice_choice.SetSelection(0)
        self._on_control_changed(event)

    def _on_tts_test(self, event):
        """Speak a short test phrase using current settings"""
        tts_mgr = self.main_frame.tts_manager
        engine_idx = self.tts_engine_choice.GetSelection()
        engine_name = self._tts_engine_values[engine_idx] if 0 <= engine_idx < len(self._tts_engine_values) else ''
        voice_idx = self.tts_voice_choice.GetSelection()
        voice_name = self._tts_voice_names[voice_idx] if 0 <= voice_idx < len(self._tts_voice_names) else ''
        if voice_name == _("(default)"):
            voice_name = ''
        rate = self.tts_rate_spin.GetValue()
        volume = self.tts_volume_spin.GetValue()

        tts_mgr.configure(engine_name, voice_name, rate, volume)
        old_enabled = tts_mgr.tts_enabled
        tts_mgr.tts_enabled = True
        tts_mgr.speak(_("Test announcement: Deck 1"))
        tts_mgr.tts_enabled = old_enabled

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
                self.deck_count_spin.GetValue(),
                self.theme_choice.GetSelection(),
                self.list_style_choice.GetSelection(),
            ),
            'audio': (
                self.device_choice.GetSelection(),
                self.buffer_choice.GetSelection(),
                self.rate_choice.GetSelection(),
            ),
            'automation': (
                self.interval_spin.GetValue(),
                self.crossfade_check.GetValue(),
                self.crossfade_ctrl.GetValue(),
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
            'tts': (
                self.tts_enabled_check.GetValue(),
                self.tts_engine_choice.GetSelection(),
                self.tts_voice_choice.GetSelection(),
                self.tts_rate_spin.GetValue(),
                self.tts_volume_spin.GetValue(),
            ),
        }

    def _get_current_values(self, tab_name):
        """Get current control values for a given tab"""
        if tab_name == 'general':
            return (
                self.language_choice.GetSelection(),
                self.deck_count_spin.GetValue(),
                self.theme_choice.GetSelection(),
                self.list_style_choice.GetSelection(),
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
                self.crossfade_ctrl.GetValue(),
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
        elif tab_name == 'tts':
            return (
                self.tts_enabled_check.GetValue(),
                self.tts_engine_choice.GetSelection(),
                self.tts_voice_choice.GetSelection(),
                self.tts_rate_spin.GetValue(),
                self.tts_volume_spin.GetValue(),
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
        """Show page at idx, hide all others."""
        target = self.pages[idx]
        for i, page in enumerate(self.pages):
            page.Show(i == idx)
        self.page_container.Layout()
        target.Layout()

    def _fit_to_pages(self):
        """Fit the dialog to its initial content with minimum size constraints."""
        self.Fit()
        size = self.GetSize()
        if size.width < 700 or size.height < 600:
            self.SetSize(max(size.width, 700), max(size.height, 600))

    def _on_control_changed(self, event):
        """Handle any control value change - update Apply button state"""
        event.Skip()
        self._update_apply_state()

    # --- Per-section save methods ---

    def _save_general(self):
        """Save general settings to config and return restart reasons"""
        old_language = self.config_manager.get('General', 'language', 'en')
        old_deck_count = self.config_manager.get('General', 'deck_count', '10')
        old_list_style = self.config_manager.get('General', 'deck_list_style', 'compact')

        languages = ['en', 'de']
        self.config_manager.set('General', 'language', languages[self.language_choice.GetSelection()])
        self.config_manager.set('General', 'deck_count', self.deck_count_spin.GetValue())
        self.config_manager.set('General', 'theme',
                               self.theme_values[self.theme_choice.GetSelection()])
        self.config_manager.set('General', 'deck_list_style',
                               self.list_style_values[self.list_style_choice.GetSelection()])

        restart_reasons = []
        if self.config_manager.get('General', 'language', 'en') != old_language:
            restart_reasons.append(_("Language"))
        if self.config_manager.get('General', 'deck_count', '10') != old_deck_count:
            restart_reasons.append(_("Number of decks"))
        if self.config_manager.get('General', 'deck_list_style', 'compact') != old_deck_count:
            restart_reasons.append(_("Deck list style"))
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
        self.config_manager.set('Automation', 'crossfade_duration', self.crossfade_ctrl.GetValue())
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

    def _save_tts(self):
        """Save TTS settings to config"""
        self.config_manager.set('TTS', 'tts_enabled', self.tts_enabled_check.GetValue())
        engine_idx = self.tts_engine_choice.GetSelection()
        engine_name = self._tts_engine_values[engine_idx] if 0 <= engine_idx < len(self._tts_engine_values) else ''
        self.config_manager.set('TTS', 'tts_engine', engine_name)
        voice_idx = self.tts_voice_choice.GetSelection()
        voice_name = self._tts_voice_names[voice_idx] if 0 <= voice_idx < len(self._tts_voice_names) else ''
        if voice_name == _("(default)"):
            voice_name = ''
        self.config_manager.set('TTS', 'tts_voice', voice_name)
        self.config_manager.set('TTS', 'tts_rate', self.tts_rate_spin.GetValue())
        self.config_manager.set('TTS', 'tts_volume', self.tts_volume_spin.GetValue())

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
        elif tab_name == 'tts':
            self._save_tts()
            self.config_manager.save()
            self.main_frame.apply_tts_settings()

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
        if 'tts' not in self._applied_sections:
            self._save_tts()

        self.config_manager.save()
        self._show_restart_message(restart_reasons)
        self.EndModal(wx.ID_OK)

