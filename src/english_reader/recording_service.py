import threading

import numpy as np
import sounddevice as sd
import soundfile as sf

from .audio_player import AudioPlayer
from .paths import data_file


RECORDING_FILE = data_file("shadowing_recording.wav")

_recording_stream = None
_recording_frames = []
_recording_lock = threading.Lock()
_recording_sample_rate = 44_100
_recording_active = False
_recording_paused = False
_recording_player = AudioPlayer()


def _recording_callback(indata, frames, time_info, status):
    del frames, time_info, status

    with _recording_lock:
        if _recording_paused:
            return

        _recording_frames.append(indata.copy())


def start_recording() -> int:
    global _recording_stream
    global _recording_frames
    global _recording_sample_rate
    global _recording_active
    global _recording_paused

    if _recording_active:
        raise RuntimeError("A recording is already in progress.")

    stop_recording_playback()

    device = sd.query_devices(kind="input")
    sample_rate = int(
        device.get("default_samplerate")
        or 44_100
    )

    with _recording_lock:
        _recording_frames = []

    stream = sd.InputStream(
        samplerate=sample_rate,
        channels=1,
        dtype="float32",
        callback=_recording_callback,
    )

    try:
        stream.start()
    except Exception:
        stream.close()
        raise

    _recording_stream = stream
    _recording_sample_rate = sample_rate
    _recording_active = True

    with _recording_lock:
        _recording_paused = False

    return sample_rate


def stop_recording() -> float:
    global _recording_stream
    global _recording_active
    global _recording_frames
    global _recording_paused

    if not _recording_active or _recording_stream is None:
        raise RuntimeError("No recording is currently in progress.")

    stream = _recording_stream

    _recording_active = False
    _recording_stream = None

    try:
        stream.stop()
    finally:
        stream.close()

    with _recording_lock:
        chunks = list(_recording_frames)
        _recording_frames = []
        _recording_paused = False

    if not chunks:
        raise RuntimeError(
            "No microphone audio was captured. "
            "Check the selected input device and microphone permission."
        )

    audio = np.concatenate(chunks, axis=0)

    if audio.size == 0:
        raise RuntimeError("The recording is empty.")

    sf.write(
        RECORDING_FILE,
        audio,
        _recording_sample_rate,
        subtype="PCM_16",
    )

    return float(
        len(audio) / _recording_sample_rate
    )


def cancel_recording() -> None:
    global _recording_stream
    global _recording_active
    global _recording_frames
    global _recording_paused

    stream = _recording_stream

    _recording_active = False
    _recording_stream = None

    if stream is not None:
        try:
            stream.stop()
        except Exception:
            pass

        try:
            stream.close()
        except Exception:
            pass

    with _recording_lock:
        _recording_frames = []
        _recording_paused = False


def is_recording() -> bool:
    return _recording_active


def pause_recording() -> None:
    """Stop accumulating microphone frames without closing the stream.

    The PortAudio input stream stays open on purpose: reopening a capture
    device mid-session is the fragile part on ALSA, and the saved duration
    already excludes the paused span because it is derived from the frames
    that were kept.
    """
    global _recording_paused

    if not _recording_active:
        return

    with _recording_lock:
        _recording_paused = True


def resume_recording() -> None:
    global _recording_paused

    if not _recording_active:
        return

    with _recording_lock:
        _recording_paused = False


def is_recording_paused() -> bool:
    return _recording_active and _recording_paused


def has_recording() -> bool:
    return RECORDING_FILE.exists()


def clear_recording() -> None:
    stop_recording_playback()
    RECORDING_FILE.unlink(missing_ok=True)


def get_recording_duration() -> float:
    if not RECORDING_FILE.exists():
        return 0.0

    return float(
        sf.info(RECORDING_FILE).duration
    )


def play_recording() -> None:
    if not RECORDING_FILE.exists():
        raise FileNotFoundError(
            f"Recording not found: {RECORDING_FILE}"
        )

    stop_recording_playback()

    _recording_player.load(RECORDING_FILE)
    _recording_player.play()


def stop_recording_playback() -> None:
    _recording_player.unload()


def is_recording_playing() -> bool:
    return _recording_player.is_playing()


def pause_recording_playback() -> None:
    _recording_player.pause()


def resume_recording_playback() -> None:
    _recording_player.resume()


def is_recording_playback_paused() -> bool:
    return _recording_player.is_paused()


def play_beep(
    frequency: float = 880.0,
    duration: float = 0.14,
    volume: float = 0.18,
) -> None:
    """Play a short cue before opening the microphone stream."""
    sample_rate = 44_100

    samples = int(
        sample_rate * duration
    )

    timeline = (
        np.arange(samples, dtype=np.float32)
        / sample_rate
    )

    tone = (
        volume
        * np.sin(
            2.0
            * np.pi
            * frequency
            * timeline
        )
    ).astype(np.float32)

    # Small fade in/out to avoid clicks.
    fade_samples = min(
        int(sample_rate * 0.01),
        samples // 2,
    )

    if fade_samples > 0:
        fade = np.linspace(
            0.0,
            1.0,
            fade_samples,
            dtype=np.float32,
        )

        tone[:fade_samples] *= fade
        tone[-fade_samples:] *= fade[::-1]

    sd.play(
        tone,
        samplerate=sample_rate,
        blocking=True,
    )
