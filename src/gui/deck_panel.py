"""
Deck Panel - UI for individual audio deck
"""

import wx
from typing import Optional, Callable

from audio.deck import Deck
from config.defaults import DECK_STATE_EMPTY, DECK_STATE_PLAYING, DECK_STATE_PAUSED
from utils.i18n import _
from utils.helpers import format_volume_percent


class DeckPanel(wx.Panel):
    """UI panel for a single audio deck with controls"""

    def __init__(self, parent, deck: Deck):
        """
        Initialize deck panel.

        Args:
            parent: Parent window
            deck: Deck instance
        """
        super().__init__(parent)
        self.deck = deck

        # Callbacks
        self.on_load_file: Optional[Callable] = None
        self.on_load_url: Optional[Callable] = None
        self.on_play: Optional[Callable] = None  # Called before play to preload audio

        self._create_ui()
        self._update_ui()

    def _create_ui(self):
        """Create UI elements"""
        # Use StaticBox for better grouping with screen readers
        self.static_box = wx.StaticBox(self, label=self.deck.name)
        main_sizer = wx.StaticBoxSizer(self.static_box, wx.VERTICAL)

        # Status indicator
        status_sizer = wx.BoxSizer(wx.HORIZONTAL)
        status_text = wx.StaticText(self, label=_("Status:"))
        status_sizer.Add(status_text, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        self.status_label = wx.StaticText(self, label=_("Empty"))
        self.status_label.SetForegroundColour(wx.Colour(128, 128, 128))
        status_sizer.Add(self.status_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        main_sizer.Add(status_sizer, 0, wx.EXPAND | wx.ALL, 5)

        # File/URL display
        self.file_label = wx.StaticText(self, label=_("No file loaded"))
        self.file_label.SetForegroundColour(wx.Colour(100, 100, 100))
        main_sizer.Add(self.file_label, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        # Playback controls
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.play_button = wx.Button(self, label=_("Play"))
        self.play_button.SetName(f"{self.deck.name} - {_('Play')}")
        self.play_button.Bind(wx.EVT_BUTTON, self._on_play_pause)
        button_sizer.Add(self.play_button, 1, wx.ALL, 5)

        self.stop_button = wx.Button(self, label=_("Stop"))
        self.stop_button.SetName(f"{self.deck.name} - {_('Stop')}")
        self.stop_button.Bind(wx.EVT_BUTTON, self._on_stop)
        button_sizer.Add(self.stop_button, 1, wx.ALL, 5)

        self.load_button = wx.Button(self, label=_("Menu..."))
        self.load_button.SetName(f"{self.deck.name} - {_('Menu...')}")
        self.load_button.Bind(wx.EVT_BUTTON, self._on_deck_menu)
        button_sizer.Add(self.load_button, 1, wx.ALL, 5)

        main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 5)

        # Volume control
        volume_sizer = wx.BoxSizer(wx.HORIZONTAL)
        volume_label = wx.StaticText(self, label=_("Volume:"))
        volume_sizer.Add(volume_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        self.volume_slider = wx.Slider(
            self, value=100, minValue=0, maxValue=100,
            style=wx.SL_HORIZONTAL
        )
        self.volume_slider.SetName(f"{self.deck.name} - {_('Volume:')}")
        self.volume_slider.Bind(wx.EVT_SLIDER, self._on_volume_change)
        volume_sizer.Add(self.volume_slider, 1, wx.ALL | wx.EXPAND, 5)

        main_sizer.Add(volume_sizer, 0, wx.EXPAND | wx.ALL, 5)

        # Balance control
        balance_sizer = wx.BoxSizer(wx.HORIZONTAL)
        balance_label = wx.StaticText(self, label=_("Balance:"))
        balance_sizer.Add(balance_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        self.balance_slider = wx.Slider(
            self, value=0, minValue=-100, maxValue=100,
            style=wx.SL_HORIZONTAL
        )
        self.balance_slider.SetName(f"{self.deck.name} - {_('Balance:')}")
        self.balance_slider.Bind(wx.EVT_SLIDER, self._on_balance_change)
        balance_sizer.Add(self.balance_slider, 1, wx.ALL | wx.EXPAND, 5)

        main_sizer.Add(balance_sizer, 0, wx.EXPAND | wx.ALL, 5)

        # Mute and Loop checkboxes
        checkbox_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.mute_checkbox = wx.CheckBox(self, label=_("Mute"))
        self.mute_checkbox.SetName(f"{self.deck.name} - {_('Mute')}")
        self.mute_checkbox.Bind(wx.EVT_CHECKBOX, self._on_mute_change)
        checkbox_sizer.Add(self.mute_checkbox, 0, wx.ALL, 5)

        self.loop_checkbox = wx.CheckBox(self, label=_("Loop"))
        self.loop_checkbox.SetName(f"{self.deck.name} - {_('Loop')}")
        self.loop_checkbox.Bind(wx.EVT_CHECKBOX, self._on_loop_change)
        checkbox_sizer.Add(self.loop_checkbox, 0, wx.ALL, 5)

        main_sizer.Add(checkbox_sizer, 0, wx.ALL, 5)

        # Separator
        main_sizer.Add(wx.StaticLine(self), 0, wx.EXPAND | wx.ALL, 5)

        self.SetSizer(main_sizer)

        # Context menu
        self.Bind(wx.EVT_CONTEXT_MENU, self._on_context_menu)

    def _on_play_pause(self, event):
        """Handle play/pause button"""
        if self.deck.state == DECK_STATE_EMPTY:
            return

        # Preload audio before starting playback
        if not self.deck.is_playing and self.on_play:
            self.on_play(self.deck)

        self.deck.toggle_play_pause()
        self._update_ui()

    def _on_stop(self, event):
        """Handle stop button"""
        self.deck.stop()
        self._update_ui()

    def _on_deck_menu(self, event):
        """Handle menu button"""
        menu = wx.Menu()
        load_file_item = menu.Append(wx.ID_ANY, _("Load File..."))
        load_url_item = menu.Append(wx.ID_ANY, _("Load URL..."))

        menu.AppendSeparator()

        rename_item = menu.Append(wx.ID_ANY, _("Rename Deck..."))
        menu.AppendSeparator()

        toggle_loop_item = menu.Append(wx.ID_ANY, _("Toggle Loop"))
        menu.AppendSeparator()

        unload_item = menu.Append(wx.ID_ANY, _("Unload Deck"))
        unload_item.Enable(self.deck.state != DECK_STATE_EMPTY)

        self.Bind(wx.EVT_MENU, lambda e: self._load_file(), load_file_item)
        self.Bind(wx.EVT_MENU, lambda e: self._load_url(), load_url_item)
        self.Bind(wx.EVT_MENU, self._on_rename, rename_item)
        self.Bind(wx.EVT_MENU, lambda e: self.deck.toggle_loop() or self._update_ui(), toggle_loop_item)
        self.Bind(wx.EVT_MENU, lambda e: self.deck.unload() or self._update_ui(), unload_item)

        self.PopupMenu(menu)
        menu.Destroy()

    def _load_file(self):
        """Show file dialog and load file"""
        if self.on_load_file:
            self.on_load_file(self.deck)

    def _load_url(self):
        """Show URL dialog and load stream"""
        if self.on_load_url:
            self.on_load_url(self.deck)

    def _on_volume_change(self, event):
        """Handle volume slider change"""
        volume = self.volume_slider.GetValue() / 100.0
        self.deck.set_volume(volume)

    def _on_balance_change(self, event):
        """Handle balance slider change"""
        balance = self.balance_slider.GetValue() / 100.0
        self.deck.set_balance(balance)

    def _on_mute_change(self, event):
        """Handle mute checkbox change"""
        self.deck.set_mute(self.mute_checkbox.GetValue())

    def _on_loop_change(self, event):
        """Handle loop checkbox change"""
        self.deck.set_loop(self.loop_checkbox.GetValue())

    def _on_context_menu(self, event):
        """Show context menu"""
        menu = wx.Menu()

        load_file_item = menu.Append(wx.ID_ANY, _("Load File..."))
        load_url_item = menu.Append(wx.ID_ANY, _("Load URL..."))
        menu.AppendSeparator()

        rename_item = menu.Append(wx.ID_ANY, _("Rename Deck..."))
        menu.AppendSeparator()

        toggle_loop_item = menu.Append(wx.ID_ANY, _("Toggle Loop"))
        menu.AppendSeparator()

        unload_item = menu.Append(wx.ID_ANY, _("Unload Deck"))
        unload_item.Enable(self.deck.state != DECK_STATE_EMPTY)

        self.Bind(wx.EVT_MENU, lambda e: self._load_file(), load_file_item)
        self.Bind(wx.EVT_MENU, lambda e: self._load_url(), load_url_item)
        self.Bind(wx.EVT_MENU, self._on_rename, rename_item)
        self.Bind(wx.EVT_MENU, lambda e: self.deck.toggle_loop() or self._update_ui(), toggle_loop_item)
        self.Bind(wx.EVT_MENU, lambda e: self.deck.unload() or self._update_ui(), unload_item)

        self.PopupMenu(menu)
        menu.Destroy()

    def _on_rename(self, event):
        """Show rename dialog"""
        dlg = wx.TextEntryDialog(self, _("Enter new deck name:"), _("Rename Deck"), self.deck.name)
        if dlg.ShowModal() == wx.ID_OK:
            new_name = dlg.GetValue().strip()
            if new_name:
                self.deck.set_name(new_name)
                self._update_ui()
        dlg.Destroy()

    def _update_ui(self):
        """Update UI based on deck state"""
        # Update deck name in StaticBox
        self.static_box.SetLabel(self.deck.name)

        # Update accessibility names for all controls
        self.play_button.SetName(f"{self.deck.name} - {_('Play') if not self.deck.is_playing else _('Pause')}")
        self.stop_button.SetName(f"{self.deck.name} - {_('Stop')}")
        self.load_button.SetName(f"{self.deck.name} - {_('Menu...')}")
        self.volume_slider.SetName(f"{self.deck.name} - {_('Volume:')}")
        self.balance_slider.SetName(f"{self.deck.name} - {_('Balance:')}")
        self.mute_checkbox.SetName(f"{self.deck.name} - {_('Mute')}")
        self.loop_checkbox.SetName(f"{self.deck.name} - {_('Loop')}")

        # Update status
        status_text = {
            DECK_STATE_EMPTY: _("Empty"),
            "loaded": _("Loaded"),
            DECK_STATE_PLAYING: _("Playing"),
            DECK_STATE_PAUSED: _("Paused"),
            "error": _("Error"),
        }.get(self.deck.state, self.deck.state)

        status_color = {
            DECK_STATE_EMPTY: wx.Colour(128, 128, 128),
            "loaded": wx.Colour(0, 0, 255),
            DECK_STATE_PLAYING: wx.Colour(0, 128, 0),
            DECK_STATE_PAUSED: wx.Colour(255, 128, 0),
            "error": wx.Colour(255, 0, 0),
        }.get(self.deck.state, wx.Colour(0, 0, 0))

        self.status_label.SetLabel(status_text)
        self.status_label.SetForegroundColour(status_color)

        # Update file label
        if self.deck.file_path:
            import os
            filename = os.path.basename(self.deck.file_path) if not self.deck.is_stream else self.deck.file_path
            self.file_label.SetLabel(filename)
        else:
            self.file_label.SetLabel(_("No file loaded"))

        # Update play button
        if self.deck.is_playing:
            self.play_button.SetLabel(_("Pause"))
        else:
            self.play_button.SetLabel(_("Play"))

        # Enable/disable controls
        is_loaded = self.deck.state != DECK_STATE_EMPTY
        self.play_button.Enable(is_loaded)
        self.stop_button.Enable(is_loaded)

        # Update sliders
        self.volume_slider.SetValue(int(self.deck.volume * 100))
        self.balance_slider.SetValue(int(self.deck.balance * 100))

        # Update checkboxes
        self.mute_checkbox.SetValue(self.deck.mute)
        self.loop_checkbox.SetValue(self.deck.loop)

        self.Layout()

    def update(self):
        """Public method to update UI"""
        self._update_ui()
