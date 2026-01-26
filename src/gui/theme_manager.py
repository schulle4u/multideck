"""
Theme Manager - Light and Dark theme support for MultiDeck Audio Player
"""

import wx
import sys


# Theme color definitions
THEMES = {
    'light': {
        'bg': wx.Colour(240, 240, 240),           # Light gray background
        'bg_alt': wx.Colour(255, 255, 255),       # White alternate background
        'fg': wx.Colour(0, 0, 0),                 # Black text
        'fg_secondary': wx.Colour(80, 80, 80),    # Dark gray secondary text
        'border': wx.Colour(200, 200, 200),       # Light border
        'button_bg': wx.Colour(225, 225, 225),    # Button background
        'button_fg': wx.Colour(0, 0, 0),          # Button text
        'input_bg': wx.Colour(255, 255, 255),     # Input field background
        'input_fg': wx.Colour(0, 0, 0),           # Input field text
        'highlight': wx.Colour(0, 120, 215),      # Highlight/accent color
        'playing': wx.Colour(0, 150, 0),          # Playing state color
        'paused': wx.Colour(200, 150, 0),         # Paused state color
        'error': wx.Colour(200, 0, 0),            # Error state color
    },
    'dark': {
        'bg': wx.Colour(30, 30, 30),              # Darker background for more depth
        'bg_alt': wx.Colour(45, 45, 45),          # Slightly lighter alternate
        'fg': wx.Colour(255, 255, 255),           # Pure white for maximum contrast
        'fg_secondary': wx.Colour(200, 200, 200), # Brighter secondary text
        'border': wx.Colour(100, 100, 100),          # Dark border
        'button_bg': wx.Colour(60, 60, 60),       # Button background
        'button_fg': wx.Colour(255, 255, 255),    # White button text
        'input_bg': wx.Colour(20, 20, 20),        # Input field background
        'input_fg': wx.Colour(255, 255, 255),     # White input field text
        'highlight': wx.Colour(100, 180, 255),    # Highlight/accent color
        'playing': wx.Colour(120, 255, 120),      # Playing state color
        'paused': wx.Colour(255, 200, 100),        # Paused state color
        'error': wx.Colour(255, 120, 120),        # Error state color
    }
}


class ThemeManager:
    """
    Manages application themes (light/dark mode).
    """

    def __init__(self, config_manager=None):
        """
        Initialize theme manager.

        Args:
            config_manager: ConfigManager instance for storing theme preference
        """
        self.config_manager = config_manager
        self._current_theme = 'light'
        self._callbacks = []

        # Load saved theme
        if config_manager:
            saved_theme = config_manager.get('General', 'theme', 'system')
            if saved_theme == 'system':
                self._current_theme = self._detect_system_theme()
            else:
                self._current_theme = saved_theme

    def _detect_system_theme(self) -> str:
        """
        Detect system theme preference.

        Returns:
            'dark' or 'light'
        """
        # Try to detect system dark mode
        if sys.platform == 'win32':
            try:
                import winreg
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
                )
                value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                winreg.CloseKey(key)
                return 'light' if value == 1 else 'dark'
            except Exception:
                pass
        elif sys.platform == 'darwin':
            try:
                import subprocess
                result = subprocess.run(
                    ['defaults', 'read', '-g', 'AppleInterfaceStyle'],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0 and 'Dark' in result.stdout:
                    return 'dark'
            except Exception:
                pass

        # Default to light theme
        return 'light'

    @property
    def current_theme(self) -> str:
        """Get current theme name"""
        return self._current_theme

    @property
    def colors(self) -> dict:
        """Get current theme colors"""
        return THEMES.get(self._current_theme, THEMES['light'])

    def set_theme(self, theme: str, save: bool = True):
        """
        Set the application theme.

        Args:
            theme: 'light', 'dark', or 'system'
            save: Whether to save the preference
        """
        if theme == 'system':
            actual_theme = self._detect_system_theme()
        else:
            actual_theme = theme if theme in THEMES else 'light'

        self._current_theme = actual_theme

        # Save preference
        if save and self.config_manager:
            self.config_manager.set('General', 'theme', theme)
            self.config_manager.save()

        # Notify callbacks
        for callback in self._callbacks:
            try:
                callback(actual_theme)
            except Exception as e:
                print(f"Error in theme callback: {e}")

    def toggle_theme(self):
        """Toggle between light and dark theme"""
        new_theme = 'dark' if self._current_theme == 'light' else 'light'
        self.set_theme(new_theme)

    def register_callback(self, callback):
        """
        Register a callback for theme changes.

        Args:
            callback: Function to call when theme changes, receives theme name
        """
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def unregister_callback(self, callback):
        """Unregister a theme change callback"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def apply_theme(self, window: wx.Window, recursive: bool = True):
        """
        Apply current theme to a window and optionally its children.

        Args:
            window: wxPython window to theme
            recursive: Whether to apply to child windows
        """
        colors = self.colors

        # Apply to main window
        self._apply_to_widget(window, colors)

        # Recursively apply to children
        if recursive:
            self._apply_recursive(window, colors)

        # Refresh the window
        window.Refresh()

    def _apply_recursive(self, parent: wx.Window, colors: dict):
        """Recursively apply theme to all children"""
        for child in parent.GetChildren():
            self._apply_to_widget(child, colors)
            self._apply_recursive(child, colors)

    def _apply_to_widget(self, widget: wx.Window, colors: dict):
        """Apply theme colors to a single widget"""
        try:
            widget_type = type(widget).__name__

            # Skip native controls that should keep their system appearance
            # for accessibility (screen readers, keyboard navigation)
            # These controls work best with native theming
            native_controls = [
                'MenuBar', 'Menu', 'MenuItem', 'StatusBar',
                'CheckBox', 'RadioButton', 'RadioBox',
                'ToggleButton', 'CheckListBox',
            ]
            if widget_type in native_controls or isinstance(widget, (wx.CheckBox, wx.RadioButton)):
                return

            # Bind focus events for better keyboard accessibility
            widget.Bind(wx.EVT_SET_FOCUS, lambda evt: self._handle_focus(evt, True))
            widget.Bind(wx.EVT_KILL_FOCUS, lambda evt: self._handle_focus(evt, False))

            # StaticBox - only set foreground for label visibility
            if isinstance(widget, wx.StaticBox):
                widget.SetForegroundColour(colors['fg'])
                return

            # Panels and frames
            if isinstance(widget, (wx.Panel, wx.Frame, wx.Dialog)):
                widget.SetBackgroundColour(colors['bg'])
                widget.SetForegroundColour(colors['fg'])

            # Buttons (but not toggle/radio buttons)
            elif isinstance(widget, wx.Button) and not isinstance(widget, wx.ToggleButton):
                widget.SetBackgroundColour(colors['button_bg'])
                widget.SetForegroundColour(colors['button_fg'])

            # Text controls
            elif isinstance(widget, (wx.TextCtrl, wx.SpinCtrl, wx.SpinCtrlDouble)):
                widget.SetBackgroundColour(colors['input_bg'])
                widget.SetForegroundColour(colors['input_fg'])

            # Static text
            elif isinstance(widget, wx.StaticText):
                widget.SetForegroundColour(colors['fg'])

            # Choice/ComboBox
            elif isinstance(widget, (wx.Choice, wx.ComboBox)):
                widget.SetBackgroundColour(colors['input_bg'])
                widget.SetForegroundColour(colors['input_fg'])

            # Sliders - only set if not causing issues
            elif isinstance(widget, wx.Slider):
                # Uncomment to skip slider theming on Windows to preserve accessibility
                # pass
                # On some systems, sliders need a slightly different background to remain visible
                if self._current_theme == 'dark':
                    widget.SetBackgroundColour(colors['bg_alt']) # Give it a bit of contrast
                else:
                    widget.SetBackgroundColour(colors['bg'])

            # Notebooks
            elif isinstance(widget, wx.Notebook):
                widget.SetBackgroundColour(colors['bg'])
                widget.SetForegroundColour(colors['fg'])

            # List controls
            elif isinstance(widget, (wx.ListCtrl, wx.ListBox)):
                widget.SetBackgroundColour(colors['input_bg'])
                widget.SetForegroundColour(colors['input_fg'])

            # ScrolledWindow
            elif isinstance(widget, wx.ScrolledWindow):
                widget.SetBackgroundColour(colors['bg'])
                widget.SetForegroundColour(colors['fg'])

            # StaticLine - skip, keep native appearance
            elif isinstance(widget, wx.StaticLine):
                pass

            # No generic fallback - only theme explicitly listed widgets
            # This prevents accidentally breaking accessibility of unknown controls

        except Exception:
            # Silently ignore widgets that don't support theming
            pass

    def _handle_focus(self, event, has_focus: bool):
        """
        Handle visual feedback when a widget gains or loses focus.
        
        Args:
            event: The wx.FocusEvent
            has_focus: Boolean indicating if the widget gained focus
        """
        widget = event.GetEventObject()
        colors = self.colors
        
        if has_focus:
            # Check if widget supports SetBorderColour (mostly custom or specific native)
            if hasattr(widget, "SetBorderColour"):
                widget.SetBorderColour(colors['highlight'])
            # Alternative: slight background shift for text controls if border isn't supported
            elif isinstance(widget, wx.TextCtrl):
                widget.SetBackgroundColour(wx.Colour(40, 40, 40) if self._current_theme == 'dark' else wx.Colour(245, 245, 255))
        else:
            if hasattr(widget, "SetBorderColour"):
                widget.SetBorderColour(colors['border'])
            elif isinstance(widget, wx.TextCtrl):
                widget.SetBackgroundColour(colors['input_bg'])
            # Highlight border or background on focus (only win32 for the moment)
            if sys.platform == 'win32':
                if isinstance(widget, (wx.TextCtrl, wx.ComboBox, wx.Choice)):
                    widget.SetBorderColour(colors['highlight']) # Note: Support varies by OS

        widget.Refresh()
        event.Skip() # Ensure the event propagates further

    def get_status_color(self, status: str) -> wx.Colour:
        """
        Get color for a status indicator.

        Args:
            status: 'playing', 'paused', 'error', or other

        Returns:
            Appropriate wx.Colour
        """
        colors = self.colors
        if status == 'playing':
            return colors['playing']
        elif status == 'paused':
            return colors['paused']
        elif status == 'error':
            return colors['error']
        else:
            return colors['fg']
