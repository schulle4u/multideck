#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MultiDeck Audio Player - Main Entry Point
"""

import sys
import os
from pathlib import Path

# Add src directory to Python path
src_dir = Path(__file__).parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

import wx

from gui.main_frame import MainFrame
from config.config_manager import ConfigManager
from utils.i18n import initialize_i18n


class MultiDeckApp(wx.App):
    """Main application class"""

    def OnInit(self):
        """Initialize application"""
        # Load configuration
        config = ConfigManager()

        # Initialize internationalization
        language = config.get('General', 'language', 'en')
        initialize_i18n(language)

        # Create and show main frame
        self.frame = MainFrame()
        self.frame.Show()

        return True


def main():
    """Main entry point"""
    # Create application
    app = MultiDeckApp(False)

    # Run main loop
    app.MainLoop()

    return 0


if __name__ == '__main__':
    sys.exit(main())
