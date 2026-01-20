"""
Logger - Centralized logging for MultiDeck Audio Player

Provides configurable logging with file and console output.
Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
"""

import logging
import os
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional


# Default log file name
LOG_FILENAME = 'multideck.log'

# Log format
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# Map string log levels to logging constants
LOG_LEVELS = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL,
}


def _get_log_directory() -> Path:
    """
    Get the directory for log files.
    Uses the same logic as config path - portable mode or user directory.

    Returns:
        Path to log directory
    """
    # Get program directory
    if getattr(sys, 'frozen', False):
        program_dir = Path(sys.executable).parent
    else:
        program_dir = Path(__file__).parent.parent.parent

    # Check for portable mode (config.ini in program directory)
    portable_config = program_dir / 'config.ini'
    if portable_config.exists():
        return program_dir

    # Use platform-specific user config directory
    if sys.platform == 'win32':
        log_dir = Path(os.environ.get('APPDATA', '~')) / 'MultiDeckAudioPlayer'
    elif sys.platform == 'darwin':
        log_dir = Path.home() / 'Library' / 'Application Support' / 'MultiDeckAudioPlayer'
    else:
        log_dir = Path.home() / '.config' / 'multideck-audio-player'

    # Create directory if needed
    log_dir.mkdir(parents=True, exist_ok=True)

    return log_dir


class MultiDeckLogger:
    """
    Centralized logger for MultiDeck Audio Player.
    Supports file and console logging with configurable levels.
    """

    _instance: Optional['MultiDeckLogger'] = None
    _initialized: bool = False

    def __new__(cls):
        """Singleton pattern - only one logger instance"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize logger (only once)"""
        if MultiDeckLogger._initialized:
            return

        self._loggers = {}
        self._file_handler: Optional[RotatingFileHandler] = None
        self._console_handler: Optional[logging.StreamHandler] = None
        self._log_level = logging.INFO
        self._file_logging_enabled = True
        self._console_logging_enabled = True

        # Set up root logger for the application
        self._setup_logging()

        MultiDeckLogger._initialized = True

    def _setup_logging(self):
        """Set up logging handlers"""
        # Create formatter
        formatter = logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT)

        # Set up file handler with rotation
        log_path = _get_log_directory() / LOG_FILENAME
        self._file_handler = RotatingFileHandler(
            log_path,
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=3,
            encoding='utf-8'
        )
        self._file_handler.setFormatter(formatter)
        self._file_handler.setLevel(self._log_level)

        # Set up console handler
        self._console_handler = logging.StreamHandler(sys.stdout)
        self._console_handler.setFormatter(formatter)
        self._console_handler.setLevel(self._log_level)

    def get_logger(self, name: str) -> logging.Logger:
        """
        Get a logger instance for a specific module.

        Args:
            name: Logger name (usually module name)

        Returns:
            Configured logger instance
        """
        if name not in self._loggers:
            logger = logging.getLogger(f'multideck.{name}')
            logger.setLevel(self._log_level)
            logger.propagate = False

            # Add handlers
            if self._file_logging_enabled and self._file_handler:
                logger.addHandler(self._file_handler)
            if self._console_logging_enabled and self._console_handler:
                logger.addHandler(self._console_handler)

            self._loggers[name] = logger

        return self._loggers[name]

    def set_level(self, level: str):
        """
        Set logging level for all loggers.

        Args:
            level: Log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        level_upper = level.upper()
        if level_upper not in LOG_LEVELS:
            print(f"Invalid log level: {level}. Using INFO.")
            level_upper = 'INFO'

        self._log_level = LOG_LEVELS[level_upper]

        # Update all existing loggers
        if self._file_handler:
            self._file_handler.setLevel(self._log_level)
        if self._console_handler:
            self._console_handler.setLevel(self._log_level)

        for logger in self._loggers.values():
            logger.setLevel(self._log_level)

    def enable_file_logging(self, enabled: bool):
        """Enable or disable file logging"""
        self._file_logging_enabled = enabled

        for logger in self._loggers.values():
            if enabled and self._file_handler not in logger.handlers:
                logger.addHandler(self._file_handler)
            elif not enabled and self._file_handler in logger.handlers:
                logger.removeHandler(self._file_handler)

    def enable_console_logging(self, enabled: bool):
        """Enable or disable console logging"""
        self._console_logging_enabled = enabled

        for logger in self._loggers.values():
            if enabled and self._console_handler not in logger.handlers:
                logger.addHandler(self._console_handler)
            elif not enabled and self._console_handler in logger.handlers:
                logger.removeHandler(self._console_handler)

    def get_log_path(self) -> Path:
        """Get the path to the log file"""
        return _get_log_directory() / LOG_FILENAME


# Global logger instance
_logger_instance: Optional[MultiDeckLogger] = None


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for a specific module.

    Args:
        name: Module name

    Returns:
        Configured logger
    """
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = MultiDeckLogger()
    return _logger_instance.get_logger(name)


def configure_logging(level: str = 'INFO', file_logging: bool = True, console_logging: bool = True):
    """
    Configure global logging settings.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        file_logging: Enable file logging
        console_logging: Enable console logging
    """
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = MultiDeckLogger()

    _logger_instance.set_level(level)
    _logger_instance.enable_file_logging(file_logging)
    _logger_instance.enable_console_logging(console_logging)


def get_log_path() -> Path:
    """Get the path to the log file"""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = MultiDeckLogger()
    return _logger_instance.get_log_path()
