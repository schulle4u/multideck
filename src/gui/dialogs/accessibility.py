"""
Various accessibility fixes for WX
"""
import wx


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

