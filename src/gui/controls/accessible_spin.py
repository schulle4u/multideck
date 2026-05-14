"""
Accessible spinbutton class
"""
import wx


class AccessibleSpinCtrl(wx.BoxSizer):
    """
    Accessible floating-point spin control composed of wx widgets.

    The control exposes a labeled text field as the primary interaction point
    and keeps a wx.SpinButton in sync for mouse users. Arrow keys on the text
    field adjust the value directly, which makes the widget easier to use with
    screen readers.
    """

    def __init__(self, parent, label_text, initial_val, min_val, max_val, inc):
        """
        Initialize accessible spin control.

        Args:
            parent: Parent wx window that owns the child controls.
            label_text: Label shown next to the text field and used as its
                accessible name.
            initial_val: Initial numeric value displayed in the control.
            min_val: Minimum allowed value.
            max_val: Maximum allowed value.
            inc: Increment used by the spin button and Up/Down arrow keys.
        """
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
        self.spin_btn.SetCanFocus(False)
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

        Args:
            event_type: Ignored wx event binder supplied by the caller.
            handler: Callable to bind to text and spin changes.
            *args: Additional positional arguments forwarded to wx.Bind.
            **kwargs: Additional keyword arguments forwarded to wx.Bind.
        """
        # We bind to both text changes and spin changes
        self.text_ctrl.Bind(wx.EVT_TEXT, handler, *args, **kwargs)
        self.spin_btn.Bind(wx.EVT_SPIN, handler, *args, **kwargs)

    def _adjust_value(self, steps):
        """
        Internal helper to increment/decrement the value.

        Args:
            steps: Number of increments to apply. Negative values decrement.
        """
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
        """
        Handle spin button changes and mirror the value into the text field.

        Args:
            event: wx spin event containing the current spin position.
        """
        new_val = event.GetPosition() * self.inc
        self.text_ctrl.ChangeValue(f"{new_val:.1f}")
        event.Skip() # CRITICAL: Allows the event to propagate to the dialog

    def on_text_entry(self, event):
        """
        Handle manual text edits and keep the spin button position in sync.

        Args:
            event: wx text event emitted by the internal text control.
        """
        try:
            val = float(self.text_ctrl.GetValue())
            self.spin_btn.SetValue(int(val / self.inc))
        except ValueError:
            pass
        event.Skip() # CRITICAL: Allows the event to propagate to the dialog

    def on_key_down(self, event):
        """
        Handle keyboard increments from the internal text control.

        Args:
            event: wx key event. Up and Down adjust the value; all other keys
                are passed through.
        """
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
        """
        Return the current numeric value.

        Returns:
            float: Parsed text control value, or 2.0 if the text is not a
            valid number.
        """
        try:
            return float(self.text_ctrl.GetValue())
        except ValueError:
            return 2.0
