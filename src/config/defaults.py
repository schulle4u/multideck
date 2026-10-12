"""
Default configuration values for MultiDeck Audio Player
"""

DEFAULT_CONFIG = {
    'General': {
        'language': 'system',
        'theme': 'system',
        'deck_count': 10,
        'remember_last_project': False,
        'last_project_file': '',
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
        'level_switch_enabled': False,
        'level_threshold_db': -30,
        'level_hysteresis_db': 3,
        'level_hold_time': 3,
    },
    'UI': {
        'show_statusbar': True,
        'show_level_meter': True,
        'deck_list_focus': True,
        'force_dataview': False,
        'window_width': 1200,
        'window_height': 800,
    },
    'Recorder': {
        'format': 'wav',
        'output_directory': '',
        'bit_depth': 16,
        'bitrate': 192,
        'pre_roll_seconds': 30,
    },
    'Streaming': {
        'server': '',
        'port': 8000,
        'mountpoint': '/stream',
        'credentials': '',
        'codec': 'mp3',
        'bitrate': 192,
        'name': 'MultiDeck Live',
        'description': '',
        'genre': '',
        'url': '',
        'public': False,
        'connect_at_startup': False,
        'auto_reconnect': True,
        'reconnect_wait': 5,
        'queue_blocks': 128,
        'writer_poll_ms': 100,
        'ffmpeg_close_timeout': 5.0,
        'ffmpeg_loglevel': 'error',
        'max_reconnect_attempts': 5,
        'connection_timeout': 10,
        'read_timeout': 30,
    },
    'TTS': {
        'tts_enabled': False,
        'tts_engine': "",
        'tts_voice': "",
        'tts_rate': "0",
        'tts_volume': "-1",
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
MODE_MULTIROOM = 'multiroom'

# Deck source types (used in project file serialisation)
SOURCE_TYPE_FILE = 'file'
SOURCE_TYPE_STREAM = 'stream'
SOURCE_TYPE_SOUNDCARD_INPUT = 'soundcard_input'

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
    'wav': {
        'extension': '.wav',
        'name': 'WAV',
        'codec': None,
        'native': True,
    },
    'mp3': {
        'extension': '.mp3',
        'name': 'MP3',
        'codec': 'libmp3lame',
        'native': False,
        'uses_bitrate': True,
    },
    'ogg': {
        'extension': '.ogg',
        'name': 'OGG Vorbis',
        'codec': 'libvorbis',
        'native': False,
        'uses_bitrate': True,
    },
    'opus': {
        'extension': '.opus',
        'name': 'Opus',
        'codec': 'libopus',
        'native': False,
        'uses_bitrate': True,
    },
    'flac': {
        'extension': '.flac',
        'name': 'FLAC',
        'codec': 'flac',
        'native': False,
        'ffmpeg_options': ['-compression_level', '5'],
    },
}

# Language names for UI
LANGUAGE_NAMES = {
    'en': 'English',
    'de': 'Deutsch',
    'fr': 'Français',
}

# Valid deck range
VALID_DECK_RANGE = [1, 128]

# Application info
APP_NAME = 'MultiDeck Audio Player'
APP_VERSION = '0.9.1'
APP_BUNDLE_ID = 'dev.m45.multideck'
APP_CODE_NAME = 'Kartoffelsalat'
APP_AUTHOR = 'Steffen Schultz'
APP_WEBSITE = 'https://m45.dev'
APP_LICENSE = '''MIT License

Copyright (c) 2026 Steffen Schultz

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.'''

PROJECT_FILE_EXT = '.mdap'
PROJECT_FILE_FILTER = 'MultiDeck Audio Project (*.mdap)|*.mdap'
