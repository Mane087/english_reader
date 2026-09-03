"""Cross-platform audio playback backed by PortAudio.

The player decodes the whole file into memory with ``soundfile`` and feeds it
to a ``sounddevice`` output stream, keeping a frame cursor so the caller can
pause, resume and seek. This replaces the previous ``AVAudioPlayer`` backend
so the same code runs on macOS and Linux.

Reported positions subtract the stream output latency: the callback fills the
device buffer ahead of what the speakers are playing, so the raw cursor runs
early by that amount.
"""

import threading
from pathlib import Path

import sounddevice as sd
import soundfile as sf


class AudioPlayer:
    """Play a single audio file with pause, resume and seek support."""

    def __init__(self):
        self._lock = threading.Lock()
        self._stream = None
        self._data = None
        self._sample_rate = 0
        self._cursor = 0
        self._paused = False

    # -----------------------------------------------------------------
    # Loading
    # -----------------------------------------------------------------
    def load(self, path: Path) -> None:
        path = Path(path)

        if not path.exists():
            raise FileNotFoundError(
                f"Audio file not found: {path}"
            )

        self.unload()

        try:
            data, sample_rate = sf.read(
                str(path),
                dtype="float32",
                always_2d=True,
            )

        except Exception as error:
            raise RuntimeError(
                f"Unable to load audio: {error}"
            ) from error

        if data.shape[0] == 0:
            raise RuntimeError(
                f"Audio file is empty: {path}"
            )

        stream = sd.OutputStream(
            samplerate=sample_rate,
            channels=data.shape[1],
            dtype="float32",
            callback=self._callback,
        )

        with self._lock:
            self._data = data
            self._sample_rate = int(sample_rate)
            self._cursor = 0
            self._paused = False

        self._stream = stream

    def unload(self) -> None:
        stream = self._stream
        self._stream = None

        if stream is not None:
            try:
                stream.abort()
            except Exception:
                pass

            try:
                stream.close()
            except Exception:
                pass

        with self._lock:
            self._data = None
            self._sample_rate = 0
            self._cursor = 0
            self._paused = False

    # -----------------------------------------------------------------
    # Stream callback
    # -----------------------------------------------------------------
    def _callback(self, outdata, frames, time_info, status):
        del time_info, status

        with self._lock:
            data = self._data

            if data is None:
                available = 0

            else:
                start = self._cursor

                available = max(
                    0,
                    min(
                        frames,
                        len(data) - start,
                    ),
                )

                if available > 0:
                    outdata[:available] = data[
                        start:
                        start + available
                    ]

                    self._cursor = start + available

        if available < frames:
            outdata[available:].fill(0)
            raise sd.CallbackStop

    # -----------------------------------------------------------------
    # Transport
    # -----------------------------------------------------------------
    def play(self) -> None:
        stream = self._stream

        if stream is None:
            return

        with self._lock:
            total = self._total_frames()

            # A finished stream restarts from the beginning, matching the
            # behaviour the UI expects after playback ends.
            if self._cursor >= total:
                self._cursor = 0

            self._paused = False

        self._restart_stream()

    # ``AVAudioPlayer.play`` resumed from the current position, so resuming
    # and starting are the same operation here.
    resume = play

    def pause(self) -> None:
        stream = self._stream

        if stream is None or not stream.active:
            return

        latency_frames = self._latency_frames()

        try:
            stream.abort()
        except Exception:
            pass

        # ``abort`` discards frames that were queued but never heard, so
        # rewind the cursor to the position the listener actually reached.
        with self._lock:
            self._cursor = max(
                0,
                self._cursor - latency_frames,
            )
            self._paused = True

    def stop(self) -> None:
        stream = self._stream

        if stream is None:
            return

        try:
            stream.abort()
        except Exception:
            pass

        with self._lock:
            self._cursor = 0
            self._paused = False

    def replay(self) -> None:
        if self._stream is None:
            return

        with self._lock:
            self._cursor = 0
            self._paused = False

        self._restart_stream()

    def seek_to(self, seconds: float) -> None:
        stream = self._stream

        if stream is None:
            return

        was_playing = stream.active

        if was_playing:
            try:
                stream.abort()
            except Exception:
                pass

        with self._lock:
            sample_rate = self._sample_rate

            if sample_rate > 0:
                position = int(
                    max(0.0, float(seconds))
                    * sample_rate
                )

                self._cursor = min(
                    position,
                    self._total_frames(),
                )

        if was_playing:
            self._restart_stream()

    def seek_relative(self, seconds: float) -> None:
        self.seek_to(
            self.current_time() + seconds
        )

    # -----------------------------------------------------------------
    # State
    # -----------------------------------------------------------------
    def current_time(self) -> float:
        latency_frames = self._latency_frames()

        with self._lock:
            if self._sample_rate <= 0:
                return 0.0

            position = max(
                0,
                self._cursor - latency_frames,
            )

            return position / self._sample_rate

    def duration(self) -> float:
        with self._lock:
            if self._sample_rate <= 0:
                return 0.0

            return (
                self._total_frames()
                / self._sample_rate
            )

    def is_playing(self) -> bool:
        stream = self._stream

        if stream is None:
            return False

        return bool(stream.active)

    def is_paused(self) -> bool:
        """True while playback is held at a position the caller can resume.

        ``is_playing`` cannot tell a pause from the end of the file, because
        the stream is inactive in both cases. Callers that poll for the end
        of playback need this flag to avoid treating a pause as completion.
        """
        if self._stream is None:
            return False

        with self._lock:
            return (
                self._paused
                and self._data is not None
            )

    # -----------------------------------------------------------------
    # Internals
    # -----------------------------------------------------------------
    def _total_frames(self) -> int:
        """Frame count of the loaded audio. Caller must hold the lock."""
        if self._data is None:
            return 0

        return len(self._data)

    def _latency_frames(self) -> int:
        """Frames buffered by the device, or 0 while the stream is idle."""
        stream = self._stream

        if stream is None or not stream.active:
            return 0

        with self._lock:
            sample_rate = self._sample_rate

        if sample_rate <= 0:
            return 0

        try:
            latency = float(stream.latency)
        except (TypeError, ValueError):
            return 0

        return int(
            max(0.0, latency) * sample_rate
        )

    def _restart_stream(self) -> None:
        stream = self._stream

        if stream is None:
            return

        # PortAudio rejects starting a stream that is not stopped, which is
        # the state left behind by ``CallbackStop`` at the end of playback.
        if not stream.stopped:
            try:
                stream.abort()
            except Exception:
                pass

        stream.start()
