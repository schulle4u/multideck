import wx



class CustomTextEntryDialog(wx.Dialog):
    """
    Custom text entry dialog with translatable button labels.

    The dialog mirrors the simple wx.TextEntryDialog workflow while allowing
    callers to provide localized OK and Cancel labels.
    """

    def __init__(self, parent, message, caption, default_value="", ok_label="&OK", cancel_label="&Cancel"):
        """
        Initialize custom text entry dialog.

        Args:
            parent: Parent window (MainFrame)
            message: text input message
            caption: text input caption
            default_value: optional default value
            ok_label: optional OK button label
            cancel_label: optional cancel button label
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
        ok_button = wx.Button(self, wx.ID_OK, ok_label)
        cancel_button = wx.Button(self, wx.ID_CANCEL, cancel_label)

        ok_button.SetDefault()  # OK as default button

        button_sizer.Add(ok_button, 0, wx.ALL, 5)
        button_sizer.Add(cancel_button, 0, wx.ALL, 5)

        sizer.Add(button_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

        self.SetSizer(sizer)
        self.Fit()
        self.Center()

        self.text_ctrl.SetFocus()

    def GetValue(self):
        """
        Return value from custom text entry dialog.

        Returns:
            str: Current text entered by the user.
        """
        return self.text_ctrl.GetValue()
