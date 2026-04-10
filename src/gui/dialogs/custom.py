"""
Various Custom dialogs to workaround some wx limitations
"""
import wx
from utils.i18n import _

class AccessibleSpinCtrl(wx.BoxSizer):
    def __init__(self, parent, label_text, initial_val, min_val, max_val, inc):
        super().__init__(wx.HORIZONTAL)
        
        self.min_val = min_val
        self.max_val = max_val
        self.inc = inc
        
        # 1. The Label
        self.label = wx.StaticText(parent, label=label_text)
        self.Add(self.label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        
        # 2. The TextCtrl (The primary interaction point)
        self.text_ctrl = wx.TextCtrl(parent, value=f"{initial_val:.1f}")
        self.text_ctrl.SetName(label_text)
        self.Add(self.text_ctrl, 1, wx.EXPAND | wx.ALL, 5)
        
        # 3. The SpinButton (Visible for mouse users)
        self.spin_btn = wx.SpinButton(parent, style=wx.SP_VERTICAL)
        self.spin_btn.SetRange(int(min_val / inc), int(max_val / inc))
        self.spin_btn.SetValue(int(initial_val / inc))
        self.Add(self.spin_btn, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        
        # Bindings
        self.spin_btn.Bind(wx.EVT_SPIN, self.on_spin)
        self.text_ctrl.Bind(wx.EVT_TEXT, self.on_text_entry)
        
        # Accessibility: Allow Up/Down arrow keys directly in the TextCtrl
        self.text_ctrl.Bind(wx.EVT_KEY_DOWN, self.on_key_down)

    def Bind(self, event_type, handler, *args, **kwargs):
        """
        Proxy method to allow the dialog to bind to changes.
        We map any binding attempt to our internal controls.
        """
        # We bind to both text changes and spin changes
        self.text_ctrl.Bind(wx.EVT_TEXT, handler, *args, **kwargs)
        self.spin_btn.Bind(wx.EVT_SPIN, handler, *args, **kwargs)

    def _adjust_value(self, steps):
        """Internal helper to increment/decrement the value."""
        try:
            current = float(self.text_ctrl.GetValue())
            new_val = current + (steps * self.inc)
            # Clamp value
            new_val = max(self.min_val, min(self.max_val, new_val))
            
            # Update both controls
            formatted_val = f"{new_val:.1f}"
            self.text_ctrl.SetValue(formatted_val) 
            # Note: SetValue triggers NVDA to read the new content
            
            self.spin_btn.SetValue(int(new_val / self.inc))
        except ValueError:
            pass

    def on_spin(self, event):
        new_val = event.GetPosition() * self.inc
        self.text_ctrl.ChangeValue(f"{new_val:.1f}")
        event.Skip() # CRITICAL: Allows the event to propagate to the dialog

    def on_text_entry(self, event):
        try:
            val = float(self.text_ctrl.GetValue())
            self.spin_btn.SetValue(int(val / self.inc))
        except ValueError:
            pass
        event.Skip() # CRITICAL: Allows the event to propagate to the dialog

    def on_key_down(self, event):
        key = event.GetKeyCode()
        if key in (wx.WXK_UP, wx.WXK_DOWN):
            steps = 1 if key == wx.WXK_UP else -1
            self._adjust_value(steps)
            
            # Manually fire a text event so the dialog knows something changed
            # since _adjust_value uses SetValue/ChangeValue
            cmd_event = wx.CommandEvent(wx.wxEVT_TEXT, self.text_ctrl.GetId())
            cmd_event.SetString(self.text_ctrl.GetValue())
            self.text_ctrl.GetEventHandler().ProcessEvent(cmd_event)
        else:
            event.Skip()

    def GetValue(self):
        try:
            return float(self.text_ctrl.GetValue())
        except ValueError:
            return 2.0


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

