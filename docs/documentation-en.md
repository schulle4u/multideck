# MultiDeck Audio Player

An accessible, cross-platform audio player that enables simultaneous playback of up to 10 audio files or internet streams. MultiDeck is perfect for users who need to monitor multiple audio sources in parallel or create complex soundscapes.

[![Main window, german interface shown](./multideck-screenshot.png)](./multideck-screenshot.png)

## Features

- **Up to 10 Independent Audio Decks**
  - Load local audio files (MP3, OGG, WAV, FLAC)
  - Stream from internet sources (Icecast/Shoutcast)
  - Monitor sound card inputs (microphone, line)
  - Individual play/pause, volume, balance, mute, and loop controls
  - Global play/pause control for all decks
  - Custom deck labels
- **Three Operating Modes**
  - **Mixer Mode**: All decks play simultaneously with overlap
  - **Solo Mode**: Only one deck audible at a time
  - **Automatic Mode**: Automatic switching between decks, supports crossfade
- **Project Management**
  - Save and load complete deck configurations (.mdap files)
  - Import/export M3U files
- **Master Output Recorder**
  - Record combined audio output to WAV, mp3, ogg or flac files
  - Real-time recording with status display and optional pre-roll buffer
- **Live audio effects powered by Spotify's Pedalboard library**
  - Use standard effects such as delay, chorus, equalizer, compressor and limiter
  - Load and configure VST3 effect plugins
  - Apply effects per deck or to the master output.
- **Commandline interface**
  - Load project files and play them in your server environment or on embedded computers.
  - Optional silent mode for usage in scripts.

---
