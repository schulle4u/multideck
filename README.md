# MultiDeck Audio Player

An accessible, cross-platform audio player that enables simultaneous playback of up to 10 audio files or internet streams. MultiDeck is perfect for users who need to monitor multiple audio sources in parallel or create complex soundscapes.

## Features

- **Up to 10 Independent Audio Decks**
  - Load local audio files (MP3, OGG, WAV, FLAC)
  - Stream from internet sources (Icecast/Shoutcast)
  - Individual play/pause, volume, balance, mute, and loop controls
  - Global play/pause control for all decks
  - Custom deck labels
- **Three Operating Modes**
  - **Mixer Mode**: All decks play simultaneously with overlap
  - **Solo Mode**: Only one deck audible at a time
  - **Automatic Mode**: Automatic switching between decks, supports crossfade
- **Project Management**
  - Save and load complete deck configurations (.mdap files)
  - Portable mode support
- **Master Output Recorder**
  - Record combined audio output to WAV, mp3, ogg or flac files
  - Real-time recording with status display and optional pre-roll buffer

## Installation

### Prerequisites

- Python 3.10 or higher (compatible with Python 3.14+)
- FFmpeg (for MP3 support and internet streaming)

#### Installing FFmpeg

**Windows:**
1. Download from e.g. https://www.gyan.dev/ffmpeg/builds/ (ffmpeg-release-essentials.zip)
2. Extract the archive
3. Add the `bin` folder to your system PATH

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install ffmpeg
```

**Linux (Fedora):**
```bash
sudo dnf install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

### Setup

1. Clone the repository:
```bash
git clone https://github.com/schulle4u/multideck.git
cd multideck
```

2. Create and activate a virtual environment:
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/macOS
python3 -m venv venv
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. (Optional) Install in development mode:
```bash
pip install -e .
```

## Usage

### Running the Application

```bash
python src/main.py
```

### Configuration

Copy `config.ini.example` to `config.ini` and adjust settings as needed:

```bash
cp config.ini.example config.ini
```

For portable mode, place `config.ini` in the program directory. Otherwise, configuration will be stored in platform-specific locations.

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+O` | Load project |
| `Ctrl+S` | Save project |
| `Ctrl+P` | Open options |
| `Ctrl+R` | Start/stop recorder |
| `Ctrl+1` to `Ctrl+0` | Jump to deck 1-10 (Solo/Auto mode) |
| `Ctrl+Tab` | Next deck (Solo/Auto mode) |
| `Ctrl+Shift+Tab` | Previous deck |
| `Space` | Play/pause active deck |
| `Ctrl+M` | Mute/unmute active deck |
| `Ctrl+L` | Toggle loop for active deck |
| `F1` | Show keyboard shortcuts |
| `Alt+F4` | Exit application |

See `docs/shortcuts.txt` for complete keyboard reference.

## Project Structure

```
src/
├── main.py                    # Entry point
├── gui/                       # User interface components
├── audio/                     # Audio engine and deck logic
├── config/                    # Configuration management
└── utils/                     # Utilities and i18n

locale/                        # Translations (German, English)
docs/                          # Documentation
```

## Requirements

- Python 3.10+ (compatible with Python 3.14+)
- wxPython 4.2.0+
- sounddevice 0.4.6+
- soundfile 0.12.1+
- numpy 1.24.0+
- FFmpeg (external tool, must be in PATH)

## License

MIT License - See LICENSE file for details

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

## Accessibility

MultiDeck Audio Player is designed with accessibility as a core principle. All features are fully accessible via keyboard and screen readers. If you encounter any accessibility issues, please report them in the issue tracker.

## Support

For bug reports and feature requests, please use the [GitHub issue tracker](https://github.com/schulle4u/multideck/issues)
