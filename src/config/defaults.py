"""
Default configuration values for MultiDeck Audio Player
"""

DEFAULT_CONFIG = {
    'General': {
        'language': 'en',
        'theme': 'system',
        'deck_count': 10,
    },
    'Audio': {
        'output_device': 'default',
        'buffer_size': 2048,
        'sample_rate': 48000,
    },
    'Automation': {
        'switch_interval': 10,
        'crossfade_enabled': True,
        'crossfade_duration': 2.0,
    },
    'UI': {
        'show_statusbar': True,
        'window_width': 1200,
        'window_height': 800,
        'window_x': '',
        'window_y': '',
    },
    'Recorder': {
        'format': 'wav',
        'output_directory': '',
        'bit_depth': 16,
        'bitrate': 192,
        'pre_roll_seconds': 30,
    },
    'Streaming': {
        'auto_reconnect': True,
        'reconnect_wait': 5,
        'max_reconnect_attempts': 5,
        'connection_timeout': 10,
        'read_timeout': 30,
    },
    'Recent': {
        'max_recent_items': 10,
    },
    'Logging': {
        'level': 'INFO',
        'file_logging': True,
        'console_logging': False,
    },
}

# Operating modes
MODE_MIXER = 'mixer'
MODE_SOLO = 'solo'
MODE_AUTOMATIC = 'automatic'

# Deck states
DECK_STATE_EMPTY = 'empty'
DECK_STATE_LOADED = 'loaded'
DECK_STATE_PLAYING = 'playing'
DECK_STATE_PAUSED = 'paused'
DECK_STATE_ERROR = 'error'

# Audio file formats
SUPPORTED_FILE_FORMATS = [
    ('Audio Files', '*.mp3;*.wav;*.ogg;*.flac'),
    ('MP3 Files', '*.mp3'),
    ('WAV Files', '*.wav'),
    ('OGG Files', '*.ogg'),
    ('FLAC Files', '*.flac'),
    ('All Files', '*.*'),
]

# Recording formats
RECORDING_FORMATS = {
    'wav': {'extension': '.wav', 'name': 'WAV'},
    'mp3': {'extension': '.mp3', 'name': 'MP3'},
    'ogg': {'extension': '.ogg', 'name': 'OGG Vorbis'},
    'flac': {'extension': '.flac', 'name': 'FLAC'},
}

# Valid deck counts
VALID_DECK_COUNTS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

# Application info
APP_NAME = 'MultiDeck Audio Player'
APP_VERSION = '0.1.0'
APP_AUTHOR = 'Steffen Schultz'
PROJECT_FILE_EXT = '.mdap'
PROJECT_FILE_FILTER = 'MultiDeck Audio Project (*.mdap)|*.mdap'
