import asyncio
from pathlib import Path

import edge_tts

from audio_player import AudioPlayer


OUTPUT_FILE = Path(__file__).parent / "output.mp3"
TEMP_OUTPUT_FILE = Path(__file__).parent / "output.tmp.mp3"

TICKS_PER_SECOND = 10_000_000

_player = AudioPlayer()
_word_boundaries = []


def normalize_text(text: str) -> str:
    translation_table = str.maketrans({
        "’": "'",
        "‘": "'",
        "“": '"',
        "”": '"',
        "–": "-",
        "—": "-",
        "\u00A0": " ",
    })
    return text.translate(translation_table).lower()


def align_word_boundaries(
    original_text: str,
    boundaries: list,
) -> list:
    normalized_original = normalize_text(original_text)
    cursor = 0
    aligned = []
    punctuation = ' \t\r\n.,!?;:"“”()[]{}<>'

    for boundary in boundaries:
        normalized_spoken = normalize_text(
            boundary["text"]
        ).strip()

        candidates = []

        if normalized_spoken:
            candidates.append(normalized_spoken)

            relaxed = normalized_spoken.strip(punctuation)

            if relaxed and relaxed != normalized_spoken:
                candidates.append(relaxed)

        char_start = None
        char_end = None

        for candidate in candidates:
            position = normalized_original.find(
                candidate,
                cursor,
            )

            if position == -1:
                continue

            char_start = position
            char_end = position + len(candidate)
            cursor = char_end
            break

        aligned.append({
            **boundary,
            "char_start": char_start,
            "char_end": char_end,
        })

    return aligned


async def generate_audio(
    text: str,
    voice: str,
    rate: str,
) -> None:
    global _word_boundaries

    _word_boundaries = []

    communicate = edge_tts.Communicate(
        text=text,
        voice=voice,
        rate=rate,
        boundary="WordBoundary",
    )

    boundaries = []
    received_audio = False

    try:
        with open(TEMP_OUTPUT_FILE, "wb") as audio_file:
            async for message in communicate.stream():
                message_type = message["type"]

                if message_type == "audio":
                    audio_file.write(message["data"])
                    received_audio = True

                elif message_type == "WordBoundary":
                    offset = message["offset"]
                    duration = message["duration"]

                    boundaries.append({
                        "text": message["text"],
                        "start": float(
                            offset / TICKS_PER_SECOND
                        ),
                        "end": float(
                            (offset + duration)
                            / TICKS_PER_SECOND
                        ),
                    })

        if not received_audio:
            raise RuntimeError(
                "No audio was received from edge-tts."
            )

        TEMP_OUTPUT_FILE.replace(OUTPUT_FILE)

        _word_boundaries = align_word_boundaries(
            original_text=text,
            boundaries=boundaries,
        )

    except Exception:
        TEMP_OUTPUT_FILE.unlink(missing_ok=True)
        _word_boundaries = []
        raise


def generate_audio_sync(
    text: str,
    voice: str,
    rate: str,
) -> None:
    asyncio.run(
        generate_audio(
            text=text,
            voice=voice,
            rate=rate,
        )
    )


def get_word_boundaries() -> list:
    return [
        boundary.copy()
        for boundary in _word_boundaries
    ]


def load_audio() -> None:
    _player.load(OUTPUT_FILE)


def play_audio() -> None:
    _player.play()


def pause_audio() -> None:
    _player.pause()


def resume_audio() -> None:
    _player.resume()


def stop_audio() -> None:
    _player.stop()


def replay_audio() -> None:
    _player.replay()


def seek_relative(seconds: float) -> None:
    _player.seek_relative(seconds)


def seek_to(seconds: float) -> None:
    _player.seek_to(seconds)


def get_current_time() -> float:
    return _player.current_time()


def get_duration() -> float:
    return _player.duration()


def is_playing() -> bool:
    return _player.is_playing()


def unload_audio() -> None:
    _player.unload()
