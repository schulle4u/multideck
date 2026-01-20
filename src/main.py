#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MultiDeck Audio Player - Main Entry Point
"""

import sys
import os
import argparse
from pathlib import Path

# Add src directory to Python path
src_dir = Path(__file__).parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

import wx

from gui.main_frame import MainFrame
from config.config_manager import ConfigManager
from utils.i18n import initialize_i18n, _
from utils.logger import configure_logging, get_logger


class MultiDeckApp(wx.App):
    """Main application class"""

    def __init__(self, project_file=None, *args, **kwargs):
        """Initialize application with optional project file"""
        self.project_file = project_file
        super().__init__(*args, **kwargs)

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

        # Load project file if specified
        if self.project_file:
            wx.CallAfter(self._load_project_file)

        return True

    def _load_project_file(self):
        """Load the project file specified on command line"""
        from config.config_manager import ProjectManager

        filepath = Path(self.project_file)
        if not filepath.exists():
            wx.MessageBox(
                _("Project file not found: {}").format(self.project_file),
                _("Error"),
                wx.OK | wx.ICON_ERROR
            )
            return

        if not filepath.suffix.lower() == '.mdap':
            wx.MessageBox(
                _("Invalid project file format: {}\nExpected .mdap file.").format(filepath.suffix),
                _("Error"),
                wx.OK | wx.ICON_ERROR
            )
            return

        try:
            project_data = ProjectManager.load_project(str(filepath))
            self.frame._load_project_data(project_data)
            self.frame.current_project_file = str(filepath)
            self.frame.SetStatusText(_("Opened: {}").format(filepath.name), 0)
        except Exception as e:
            wx.MessageBox(
                _("Failed to open project: {}").format(e),
                _("Error"),
                wx.OK | wx.ICON_ERROR
            )


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="MultiDeck Audio Player - Accessible cross-platform audio player",
        prog="multideck"
    )
    parser.add_argument(
        'project',
        nargs='?',
        help='Path to a .mdap project file to open on startup'
    )
    return parser.parse_args()


def main():
    """Main entry point"""
    # Parse command line arguments
    args = parse_arguments()

    # Initialize configuration early to get logging settings
    config = ConfigManager()

    # Configure logging based on settings
    log_level = config.get('Logging', 'level', 'INFO')
    file_logging = config.getboolean('Logging', 'file_logging', True)
    console_logging = config.getboolean('Logging', 'console_logging', False)
    configure_logging(level=log_level, file_logging=file_logging, console_logging=console_logging)

    # Get logger for main module
    logger = get_logger('main')
    logger.info("MultiDeck Audio Player starting...")

    # Create application with optional project file
    app = MultiDeckApp(project_file=args.project, redirect=False)

    # Run main loop
    app.MainLoop()

    return 0


if __name__ == '__main__':
    sys.exit(main())
