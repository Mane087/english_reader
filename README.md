# English Reader

A desktop app for macOS and Linux for practicing English pronunciation. Paste any text, generate
natural speech with Microsoft Edge neural voices, follow the word-by-word highlight,
read the auto-generated IPA guide, and record yourself shadowing the reference audio.

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux-lightgrey)

---

## Purpose

Most TTS tools read text out loud and stop there. English Reader is built for
*studying* the audio:

- It shows **what** the sentence sounds like (IPA transcription per sentence).
- It shows **how** to say it (thought groups, linking, pauses, weak forms, intonation).
- It lets you **imitate it** (shadowing recorder with automatic A/B comparison).

The pause and chunk markers are not guesswork: they are derived from the real word
timings returned by the TTS engine, so the guide matches the audio you just heard.

---

## Features

### PDF source
- **📄 Open PDF** loads a document and drops the text of one page into the editor.
- **◀ / ▶** move to the previous or next page; the page counter shows where you are.
- Line breaks and hyphenated words split across lines are rejoined into paragraphs,
  so the sentence-level features (TTS, Reading Guide) work on clean text.
- The text stays editable: trim headers, footers or page numbers before generating audio.

### Speech generation
- Neural voices via `edge-tts` (no API key required, needs internet).
- **Accent**: American / British.
- **Voice**: Male / Female.
- **Speed**: Slow (-35%), Learning (-15%), Normal, Fast (+15%).

### Synchronized playback
- Karaoke-style highlight of the current word while the audio plays.
- Seekable progress bar, ±1s rewind/forward, replay and stop.
- **Click a word** → play from that word onward.
- **Double-click a word** → repeat only that word 3× using its real in-context audio
  (not a re-synthesis, so stress and intonation stay authentic).

### Reading Guide
A collapsible panel rendered next to the text:

| Section | What it shows |
|---|---|
| `PRONUNCIATION` | IPA transcription per sentence (eSpeak backend). |
| `CONNECTED SPEECH + PAUSES` | Linking (`‿`) and pause markers (`\|`, `\|\|`) inferred from actual TTS timings. |
| `CHUNKS / THOUGHT GROUPS` | Sentences split into 2–6 word breath groups separated by `/`. |
| `LEXICAL STRESS` | Per-word IPA with primary (`ˈ`) and secondary (`ˌ`) stress. |
| `POSSIBLE WEAK FORMS` | Unstressed variants for function words (`to → /tə/`, `of → /əv/`, …), accent-aware. |
| `INTONATION GUIDE` | Rising (`↗`) / falling (`↘`) contour per sentence, wh- vs yes/no aware. |
| `LEGEND` | Symbol reference. |

### Shadowing practice
1. Press **🎙 Shadowing** → 3-second countdown, then a cue beep.
2. Record yourself reading the full text (live timer, press again to stop).
3. The app automatically plays **your recording**, pauses, then plays the **reference**.
4. Replay either side on demand with **▶ Mine** / **▶ Reference**, or **↻ Retry**.

The recording is discarded whenever new audio is generated.

---

## Keyboard shortcuts & mouse

| Input | Action |
|---|---|
| `Space` | Play / Pause |
| `←` | Rewind 1 second |
| `→` | Forward 1 second |
| Click on a word | Play from that word |
| Double-click on a word | Repeat that word ×3 |
| Mouse wheel over the guide | Scroll the Reading Guide |

Shortcuts are ignored while you are typing in the text box and while a shadowing
attempt is in progress, so they never hijack normal editing.

---

## Requirements

- **macOS or Linux** — playback goes through PortAudio, so both are supported.
- **Python 3.11+** (declared as `requires-python` in `pyproject.toml`).
- **espeak-ng** — required by `phonemizer` to produce IPA.
- **Internet connection** — `edge-tts` synthesizes in the cloud.
- **Microphone access** for shadowing. macOS asks for permission on first run; on
  Linux the default input device must be available to your session.

System packages per platform:

| Dependency | macOS | Ubuntu |
|---|---|---|
| espeak-ng | `brew install espeak-ng` | `sudo apt install espeak-ng` |
| Tk (for `customtkinter`) | included in the python.org / Homebrew Python | `sudo apt install python3-tk` |
| PortAudio (for `sounddevice`) | bundled in the wheel | `sudo apt install libportaudio2` |
| libsndfile (for `soundfile`) | bundled in the wheel | bundled in the wheel |

The `sounddevice` wheels ship PortAudio only for macOS and Windows, which is why
Ubuntu needs `libportaudio2` explicitly.

---

## Installation

**macOS**

```bash
# 1. System dependencies
brew install espeak-ng

# 2. Clone / enter the project
cd english_reader

# 3. Virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 4. Install the project
pip install -e .
```

**Ubuntu / Debian**

```bash
# 1. System dependencies
sudo apt update
sudo apt install espeak-ng python3-tk python3-venv libportaudio2

# 2. Clone / enter the project
cd english_reader

# 3. Virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 4. Install the project
pip install -e .
```

`pip install -e .` installs the `english_reader` package in editable mode — your edits
to `src/` take effect immediately, no reinstall needed. It also creates the
`english-reader` command inside the virtualenv.

> `pyproject.toml` holds the project metadata and the canonical dependency list;
> `requirements.txt` mirrors that list and is kept for tooling that expects it. Update
> both together. For a build: `pip install -e ".[build]"` pulls in PyInstaller.

---

## Running locally

```bash
source .venv/bin/activate
english-reader
```

`python -m english_reader` does the same thing and is handy when you have not
activated the virtualenv (`.venv/bin/python -m english_reader`).

Then:

1. Paste or type English text in the left panel.
2. Pick accent, voice and speed.
3. Press **▶ Generate & Play**.

Generation runs on a background thread — the UI stays responsive and the status bar
reports progress plus how many words were successfully synchronized
(e.g. `Playing · 42/44 words synchronized`).

Changing the text or any option after generating invalidates the audio; the app tells
you to generate again instead of playing stale audio.

---

## Building a distributable

A PyInstaller spec is already committed and adapts to the host platform:

```bash
pip install pyinstaller
pyinstaller "English Reader.spec"
```

| Host | Output | Icon |
|---|---|---|
| macOS | `dist/English Reader.app` | `assets/EnglishReader.icns` |
| Linux | `dist/English Reader/English Reader` | none (PyInstaller rejects `.icns` outside macOS) |

The spec is windowed (`console=False`) on both. PyInstaller builds for the platform
it runs on, so a Linux build must be produced on Linux.

Generated audio goes to the per-user data directory rather than next to the frozen
modules, so a read-only bundle is no longer a problem.

---

## Project structure

The project uses the standard `src` layout: the importable package lives under
`src/`, static files under `assets/`, and everything the app generates at runtime
stays out of the repository entirely.

```
english_reader/
├── src/
│   └── english_reader/
│       ├── __init__.py             # Package version
│       ├── __main__.py             # `python -m english_reader`
│       ├── app.py                  # CustomTkinter UI, playback state machine, shortcuts
│       ├── config.py               # Accent → voice map, speed rates, phonemizer languages
│       ├── paths.py                # Per-user data directory for generated audio
│       ├── pdf_service.py          # PDF loading and per-page text extraction
│       ├── audio_player.py         # Portable playback (sounddevice + soundfile)
│       ├── tts_service.py          # edge-tts synthesis, word-boundary alignment, playback API
│       ├── recording_service.py    # Microphone capture, WAV I/O, cue beep, playback
│       └── pronunciation_service.py  # IPA, chunking, linking, stress, weak forms, intonation
├── assets/
│   └── EnglishReader.icns          # App icon (used by the macOS bundle)
├── pyproject.toml                  # Metadata, dependencies, entry point, tool config
├── requirements.txt                # Pinned runtime dependencies (mirrors pyproject.toml)
├── English Reader.spec             # PyInstaller definition (macOS bundle / Linux dir)
├── LICENSE.md                      # PolyForm Noncommercial 1.0.0
└── README.md
```

The package is flat on purpose: seven modules with distinct responsibilities do not need
subpackages. `app.py` is the exception — at ~2900 lines it is by far the largest module
and the natural next thing to split, but that is a separate change.

### How the pieces fit

```
app.py  ──►  pdf_service.PdfDocument  (open once, one page of text per request)
   │
   ├──►  tts_service.generate_audio_sync()   ──►  output.mp3 + word boundaries
   │                        │
   │                        ├──►  align_word_boundaries()  (spoken word → char offset)
   │                        └──►  audio_player.AudioPlayer  (playback + seek)
   │
   ├──►  pronunciation_service.generate_reading_guide(text, boundaries, accent)
   │              └── espeak IPA + timing-derived pauses/chunks
   │
   └──►  recording_service  (shadowing capture + comparison playback)
                            └──►  audio_player.AudioPlayer
```

`tts_service` requests `WordBoundary` events from `edge-tts` and maps each spoken word
back to a character range in the original text. That mapping is what powers the
highlight, the click-to-play, the single-word repeat, and the pause detection in the
Reading Guide.

### Audio playback

Playback is isolated in `audio_player.py` behind a single `AudioPlayer` class, used by
both `tts_service` (reference audio) and `recording_service` (your shadowing take).
`app.py` never touches it directly — it calls the module-level functions those two
services expose.

`AudioPlayer` decodes the whole file into memory with `soundfile` and feeds it to a
`sounddevice` output stream, keeping a frame cursor so it can pause, resume and seek.
Both libraries sit on portable C libraries (libsndfile and PortAudio), which is what
makes the same code run on macOS and Linux.

Three details are worth knowing before changing that file:

- **Reported positions subtract the stream latency.** The callback fills the device
  buffer ahead of what the speakers are playing, so the raw cursor runs early. Without
  the correction the karaoke highlight would lead the audio by roughly 50–100 ms.
- **`pause()` rewinds the cursor by that same latency**, because aborting the stream
  discards frames that were queued but never heard.
- **A finished stream must be stopped before it can start again.** PortAudio refuses to
  start a stream that is not stopped, which is exactly the state left behind when
  playback reaches the end of the buffer.

> Earlier versions used `AVAudioPlayer` through PyObjC, which made the app macOS-only.
> That backend and the `pyobjc-*` dependencies are gone; there is now one playback
> implementation for both platforms.

---

## Generated files

These live in the per-user data directory, outside the repository, and are safe to
delete at any time:

| Platform | Location |
|---|---|
| Linux | `$XDG_DATA_HOME/english-reader/` or `~/.local/share/english-reader/` |
| macOS | `~/Library/Application Support/english-reader/` |

| File | Purpose |
|---|---|
| `output.mp3` | Latest generated reference audio. |
| `output.tmp.mp3` | Partial download; removed automatically on failure. |
| `shadowing_recording.wav` | Your last shadowing take (mono, PCM 16-bit). |

`english_reader/paths.py` resolves the directory and creates it on first use. Keeping
these out of the source tree is what lets the app run from an installed package or a
read-only bundle.

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `RuntimeError: espeak not installed` or empty IPA | Install espeak-ng: `brew install espeak-ng` (macOS) or `sudo apt install espeak-ng` (Ubuntu). |
| `OSError: PortAudio library not found` | Ubuntu only: `sudo apt install libportaudio2`. |
| `ModuleNotFoundError: No module named 'tkinter'` | Ubuntu only: `sudo apt install python3-tk`. |
| `No audio was received from edge-tts.` | No internet, or the Edge TTS endpoint rejected the request. Retry. |
| `No microphone audio was captured.` | macOS: grant permission in *System Settings → Privacy & Security → Microphone*. Linux: check the default input in your sound settings and that no other app holds the device. |
| Some words are not highlighted | Numbers, symbols and abbreviations are spoken differently than written, so their boundary cannot be mapped. The status bar shows the synchronized ratio. |
| British IPA fails | `phonemizer` falls back from `en-gb` to `en` automatically; if it still fails, check your espeak-ng voice data. |
| Shortcuts do nothing | Click outside the text box first — shortcuts are suppressed while editing. |

---

## Notes & limitations

- Windows is untested. Nothing in the code is macOS- or Linux-specific any more, but
  it has only been exercised on those two platforms.
- The Reading Guide is a *study aid*, not a phonetic ground truth. Linking, weak forms
  and intonation vary with speaker, speed, emphasis and context.
- There is no pronunciation scoring — shadowing is A/B comparison by ear, by design.
- Scanned PDFs (images without a text layer) yield nothing: the app reports the empty
  page instead of running OCR.
- `edge-tts` is an unofficial client for Microsoft Edge's read-aloud service.

---

## License

**Source-available, not open source.** Licensed under the
[PolyForm Noncommercial License 1.0.0](LICENSE.md).

You are free to read, study, run, modify and share this code for any
**noncommercial** purpose — personal study, hobby projects, research, and use by
schools, universities, NGOs and public institutions.

**Any commercial use requires written permission.** That includes selling it,
bundling it into a paid product, running it inside a for-profit company, or
offering it as a paid or ad-supported service.

> ⚠️ `phonemizer` and `espeak-ng` are GPL-3.0. See the *Scope* section of
> [LICENSE.md](LICENSE.md) before redistributing any prebuilt binary.
