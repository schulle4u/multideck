"""
Icecast streaming support for the master output using FFmpeg.
"""

import subprocess
import threading
import time
import queue
from typing import Callable, Optional

import numpy as np

from utils.helpers import check_ffmpeg
from utils.logger import get_logger


logger = get_logger('icecast_streamer')
FFMPEG_AVAILABLE = check_ffmpeg()


class IcecastStreamer:
    """Streams master audio output to an Icecast server via FFmpeg."""

    CODECS = {
        'mp3': {
            'codec': 'libmp3lame',
            'format': 'mp3',
            'content_type': 'audio/mpeg',
        },
        'ogg': {
            'codec': 'libvorbis',
            'format': 'ogg',
            'content_type': 'application/ogg',
        },
    }

    def __init__(self, sample_rate: int = 44100, channels: int = 2, config: Optional[dict] = None):
        self.sample_rate = sample_rate
        self.channels = channels
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._writer_thread: Optional[threading.Thread] = None
        self._audio_queue: "queue.Queue[np.ndarray]" = queue.Queue(maxsize=64)

        self.is_streaming = False
        self._manual_stop = False
        self._reconnect_pending = False
        self._next_reconnect_time = 0.0
        self._ffmpeg_process: Optional[subprocess.Popen] = None
        self.streaming_start_time: Optional[float] = None
        self.frames_streamed = 0
        self.frames_dropped = 0
        self.last_error = ""
        self.config = self._normalize_config(config or {})

        self.on_streaming_started: Optional[Callable] = None
        self.on_streaming_stopped: Optional[Callable] = None
        self.on_error: Optional[Callable] = None

    def _normalize_config(self, config: dict) -> dict:
        codec = str(config.get('codec', 'mp3')).lower()
        if codec not in self.CODECS:
            codec = 'mp3'

        mountpoint = str(config.get('mountpoint', '/stream') or '/stream').strip()
        if not mountpoint.startswith('/'):
            mountpoint = f'/{mountpoint}'

        return {
            'server': str(config.get('server', '')).strip(),
            'port': int(config.get('port', 8000) or 8000),
            'mountpoint': mountpoint,
            'credentials': str(config.get('credentials', '')).strip(),
            'codec': codec,
            'bitrate': max(64, min(320, int(config.get('bitrate', 192) or 192))),
            'name': str(config.get('name', '')).strip(),
            'description': str(config.get('description', '')).strip(),
            'genre': str(config.get('genre', '')).strip(),
            'url': str(config.get('url', '')).strip(),
            'public': bool(config.get('public', False)),
            'auto_reconnect': bool(config.get('auto_reconnect', True)),
            'reconnect_wait': max(1, min(60, int(config.get('reconnect_wait', 5) or 5))),
            'queue_blocks': max(4, min(512, int(config.get('queue_blocks', 64) or 64))),
            'writer_poll_ms': max(10, min(1000, int(config.get('writer_poll_ms', 100) or 100))),
            'ffmpeg_close_timeout': max(0.5, min(30.0, float(config.get('ffmpeg_close_timeout', 5.0) or 5.0))),
            'ffmpeg_loglevel': str(config.get('ffmpeg_loglevel', 'error') or 'error').strip().lower(),
        }

    def update_config(self, config: dict):
        with self._lock:
            self.config = self._normalize_config(config)
            self._resize_queue(self.config['queue_blocks'])

    def _resize_queue(self, maxsize: int):
        current_queue = self._audio_queue
        if current_queue.maxsize == maxsize:
            return

        replacement: "queue.Queue[np.ndarray]" = queue.Queue(maxsize=maxsize)
        while True:
            try:
                replacement.put_nowait(current_queue.get_nowait())
            except queue.Empty:
                break
            except queue.Full:
                try:
                    replacement.get_nowait()
                    replacement.put_nowait(current_queue.get_nowait())
                except (queue.Empty, queue.Full):
                    break
        self._audio_queue = replacement

    def is_configured(self) -> bool:
        cfg = self.config
        return bool(cfg['server'] and cfg['mountpoint'] and cfg['credentials'])

    def get_public_stream_url(self) -> str:
        cfg = self.config
        if not cfg['server'] or not cfg['mountpoint']:
            return ""
        return f"http://{cfg['server']}:{cfg['port']}{cfg['mountpoint']}"

    def start_streaming(self) -> bool:
        with self._lock:
            if self.is_streaming:
                return True

            if not FFMPEG_AVAILABLE:
                self._report_error("FFmpeg not found. Please install FFmpeg.")
                return False

            if not self.is_configured():
                self._report_error("Streaming settings are incomplete.")
                return False

            try:
                self._start_ffmpeg_process()
                self.is_streaming = True
                self._manual_stop = False
                self._reconnect_pending = False
                self._stop_event.clear()
                self.streaming_start_time = time.time()
                self.frames_streamed = 0
                self.frames_dropped = 0
                self.last_error = ""
                self._next_reconnect_time = 0.0
                self._resize_queue(self.config['queue_blocks'])
                self._ensure_writer_thread()

                if self.on_streaming_started:
                    self.on_streaming_started(self.get_public_stream_url())

                return True
            except Exception as exc:
                self._cleanup_process()
                self._report_error(f"Failed to start livestream: {exc}")
                return False

    def _start_ffmpeg_process(self):
        cfg = self.config
        codec_info = self.CODECS[cfg['codec']]
        stream_url = f"icecast://{cfg['credentials']}@{cfg['server']}:{cfg['port']}{cfg['mountpoint']}"

        cmd = [
            'ffmpeg',
            '-f', 's16le',
            '-ar', str(self.sample_rate),
            '-ac', str(self.channels),
            '-i', 'pipe:0',
            '-vn',
            '-acodec', codec_info['codec'],
            '-b:a', f"{cfg['bitrate']}k",
            '-content_type', codec_info['content_type'],
            '-f', codec_info['format'],
            '-legacy_icecast', '1',
        ]

        if cfg['name']:
            cmd.extend(['-ice_name', cfg['name']])
        if cfg['description']:
            cmd.extend(['-ice_description', cfg['description']])
        if cfg['genre']:
            cmd.extend(['-ice_genre', cfg['genre']])
        if cfg['url']:
            cmd.extend(['-ice_url', cfg['url']])

        cmd.extend(['-ice_public', '1' if cfg['public'] else '0'])
        cmd.extend(['-loglevel', cfg['ffmpeg_loglevel'], stream_url])

        creationflags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
        self._ffmpeg_process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )

    def _ensure_writer_thread(self):
        if self._writer_thread is not None and self._writer_thread.is_alive():
            return
        self._writer_thread = threading.Thread(target=self._writer_loop, daemon=True)
        self._writer_thread.start()

    def _writer_loop(self):
        while not self._stop_event.is_set():
            try:
                audio_data = self._audio_queue.get(timeout=self.config['writer_poll_ms'] / 1000.0)
            except queue.Empty:
                continue

            try:
                with self._lock:
                    if not self.is_streaming:
                        self._try_reconnect_if_needed()
                        if not self.is_streaming:
                            continue

                    if not self._ffmpeg_process or not self._ffmpeg_process.stdin:
                        self._handle_connection_loss("Livestream process is not available.")
                        continue

                    audio_int = np.clip(audio_data * 32767.0, -32768, 32767).astype(np.int16)
                    self._ffmpeg_process.stdin.write(audio_int.tobytes())
                    self.frames_streamed += len(audio_data)
            except BrokenPipeError:
                with self._lock:
                    self._handle_connection_loss("Livestream connection lost.")
            except Exception as exc:
                with self._lock:
                    self._handle_connection_loss(f"Error during livestreaming: {exc}")

    def stop_streaming(self, notify: bool = True) -> bool:
        writer_thread = None
        with self._lock:
            if not self.is_streaming and not self._ffmpeg_process:
                return False

            self._manual_stop = True
            self._reconnect_pending = False
            self._next_reconnect_time = 0.0
            self._stop_event.set()
            self._cleanup_process()
            was_streaming = self.is_streaming
            self.is_streaming = False
            writer_thread = self._writer_thread
            self._writer_thread = None

            while True:
                try:
                    self._audio_queue.get_nowait()
                except queue.Empty:
                    break

            if notify and self.on_streaming_stopped:
                self.on_streaming_stopped(self.get_public_stream_url(), self.frames_streamed)

        if writer_thread is not None:
            writer_thread.join(timeout=1.0)
        return was_streaming

    def _cleanup_process(self):
        if not self._ffmpeg_process:
            return

        try:
            if self._ffmpeg_process.stdin:
                self._ffmpeg_process.stdin.close()
        except Exception:
            pass

        try:
            self._ffmpeg_process.wait(timeout=self.config.get('ffmpeg_close_timeout', 5.0))
        except Exception:
            try:
                self._ffmpeg_process.kill()
            except Exception:
                pass

        self._ffmpeg_process = None

    def _report_error(self, message: str):
        self.last_error = message
        logger.error(message)
        if self.on_error:
            self.on_error(message)

    def _handle_connection_loss(self, message: str):
        self.is_streaming = False
        self._cleanup_process()
        self._report_error(message)
        if not self._manual_stop and self.config.get('auto_reconnect', True):
            self._reconnect_pending = True
            self._next_reconnect_time = time.time() + self.config.get('reconnect_wait', 5)
        else:
            self._reconnect_pending = False
            self._next_reconnect_time = 0.0

    def _try_reconnect_if_needed(self):
        if self._manual_stop or self.is_streaming or not self.config.get('auto_reconnect', True):
            return
        if not self._reconnect_pending:
            return
        if time.time() < self._next_reconnect_time or not self.is_configured():
            return
        self.start_streaming()

    def write_frames(self, audio_data: np.ndarray):
        if not self.is_streaming:
            with self._lock:
                self._try_reconnect_if_needed()
                if not self.is_streaming:
                    return

        chunk = audio_data.astype(np.float32, copy=True)
        try:
            self._audio_queue.put_nowait(chunk)
        except queue.Full:
            try:
                self._audio_queue.get_nowait()
                self.frames_dropped += len(chunk)
            except queue.Empty:
                pass
            try:
                self._audio_queue.put_nowait(chunk)
            except queue.Full:
                self.frames_dropped += len(chunk)

    def get_stream_info(self) -> dict:
        return {
            'is_streaming': self.is_streaming,
            'stream_url': self.get_public_stream_url(),
            'codec': self.config.get('codec', 'mp3'),
            'bitrate': self.config.get('bitrate', 192),
            'frames_streamed': self.frames_streamed,
            'frames_dropped': self.frames_dropped,
            'auto_reconnect': self.config.get('auto_reconnect', True),
            'reconnect_wait': self.config.get('reconnect_wait', 5),
            'queue_blocks': self.config.get('queue_blocks', 64),
            'writer_poll_ms': self.config.get('writer_poll_ms', 100),
            'ffmpeg_close_timeout': self.config.get('ffmpeg_close_timeout', 5.0),
            'ffmpeg_loglevel': self.config.get('ffmpeg_loglevel', 'error'),
            'last_error': self.last_error,
        }

    def __del__(self):
        self.stop_streaming(notify=False)
