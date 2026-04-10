"""
Sound Card Input dialog
"""
import wx
from utils.i18n import _


class SoundCardInputDialog(wx.Dialog):
    """Dialog for selecting a sound card input device to load into a deck."""

    def __init__(self, parent):
        super().__init__(parent, title=_("Select Sound Card Input"))

        self._devices = []  # list of {id, name, channels}
        self._selected_device = None

        sizer = wx.BoxSizer(wx.VERTICAL)

        # Label
        label = wx.StaticText(self, label=_("Available input devices:"))
        sizer.Add(label, 0, wx.ALL, 10)

        # Device list
        self._listbox = wx.ListBox(self, style=wx.LB_SINGLE)
        self._listbox.SetName(_("Input device list"))
        sizer.Add(self._listbox, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        # Populate device list
        self._populate_devices()

        # Buttons
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        ok_button = wx.Button(self, wx.ID_OK, _("&OK"))
        cancel_button = wx.Button(self, wx.ID_CANCEL, _("&Cancel"))
        ok_button.SetDefault()
        button_sizer.Add(ok_button, 0, wx.ALL, 5)
        button_sizer.Add(cancel_button, 0, wx.ALL, 5)
        sizer.Add(button_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

        self.SetSizer(sizer)
        self.SetSize(400, 320)
        self.Center()

        # Bind events
        self._listbox.Bind(wx.EVT_LISTBOX_DCLICK, self._on_double_click)
        ok_button.Bind(wx.EVT_BUTTON, self._on_ok)

        if self._listbox.GetCount() > 0:
            self._listbox.SetSelection(0)
            self._listbox.SetFocus()
        else:
            ok_button.Enable(False)

    def _populate_devices(self):
        """Query sounddevice and fill the listbox with available input devices."""
        try:
            from audio.soundcard_input_handler import SoundCardInputHandler
            self._devices = SoundCardInputHandler.get_available_input_devices()
        except Exception:
            self._devices = []

        if not self._devices:
            self._listbox.Append(_("No input devices found"))
            return

        for dev in self._devices:
            n = dev['channels']
            ch_label = _("{n} channel").format(n=n) if n == 1 else _("{n} channels").format(n=n)
            hostapi = dev.get('hostapi_name', '')
            if hostapi:
                entry = f"{dev['name']}  [{hostapi}]  –  {ch_label}"
            else:
                entry = f"{dev['name']}  –  {ch_label}"
            self._listbox.Append(entry)

    def _on_double_click(self, event):
        """Double-click confirms selection."""
        if self._listbox.GetSelection() != wx.NOT_FOUND and self._devices:
            self.EndModal(wx.ID_OK)

    def _on_ok(self, event):
        """Confirm and store selected device."""
        idx = self._listbox.GetSelection()
        if idx != wx.NOT_FOUND and idx < len(self._devices):
            self._selected_device = self._devices[idx]
        self.EndModal(wx.ID_OK)

    def GetSelectedDevice(self):
        """
        Return the selected device dict or None.

        Returns:
            {'id': int, 'name': str, 'channels': int} or None
        """
        idx = self._listbox.GetSelection()
        if idx != wx.NOT_FOUND and idx < len(self._devices):
            return self._devices[idx]
        return self._selected_device
