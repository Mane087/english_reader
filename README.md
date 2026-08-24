# English Reader

A macOS desktop app for practicing English pronunciation. Paste any text, generate
natural speech with Microsoft Edge neural voices, follow the word-by-word highlight,
read the auto-generated IPA guide, and record yourself shadowing the reference audio.

![Python](https://img.shields.io/badge/python-3.14-blue)
![Platform](https://img.shields.io/badge/platform-macOS-lightgrey)

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

- **macOS** — playback uses `AVFoundation` through PyObjC, so the app is macOS-only.
- **Python 3.14** (any 3.11+ should work; the bundled venv uses 3.14).
- **espeak-ng** — required by `phonemizer` to produce IPA.
- **Internet connection** — `edge-tts` synthesizes in the cloud.
- Microphone permission (for shadowing) and, on first run, macOS will ask for it.

PortAudio ships inside the `sounddevice` wheel, so no extra audio library is needed.

---

## Installation

```bash
# 1. System dependency
brew install espeak-ng

# 2. Clone / enter the project
cd english_reader

# 3. Virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 4. Python dependencies
pip install -r requirements.txt
```

> `requirements.txt` pins runtime dependencies only. Add `pyinstaller` separately if
> you plan to build the `.app`.

---

## Running locally

```bash
source .venv/bin/activate
python app.py
```

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

## Building the macOS app

A PyInstaller spec is already committed:

```bash
pip install pyinstaller
pyinstaller "English Reader.spec"
```

Output lands in `dist/English Reader.app`. The spec is windowed (`console=False`) and
uses `EnglishReader.icns` as the bundle icon.

---

## Project structure

```
english_reader/
├── app.py                     # CustomTkinter UI, playback state machine, shortcuts
├── config.py                  # Accent → voice map, speed rates, phonemizer languages
├── tts_service.py             # edge-tts synthesis, word-boundary alignment, AVAudioPlayer
├── recording_service.py       # Microphone capture, WAV I/O, cue beep, playback
├── pronunciation_service.py   # IPA, chunking, linking, stress, weak forms, intonation
├── requirements.txt           # Pinned runtime dependencies
├── LICENSE.md                 # PolyForm Noncommercial 1.0.0
├── English Reader.spec        # PyInstaller bundle definition
├── EnglishReader.icns         # App icon
└── output.mp3                 # Generated audio (regenerated on every run)
```

### How the pieces fit

```
app.py  ──►  tts_service.generate_audio_sync()   ──►  output.mp3 + word boundaries
   │                        │
   │                        └──►  align_word_boundaries()  (spoken word → char offset)
   │
   ├──►  pronunciation_service.generate_reading_guide(text, boundaries, accent)
   │              └── espeak IPA + timing-derived pauses/chunks
   │
   └──►  recording_service  (shadowing capture + comparison playback)
```

`tts_service` requests `WordBoundary` events from `edge-tts` and maps each spoken word
back to a character range in the original text. That mapping is what powers the
highlight, the click-to-play, the single-word repeat, and the pause detection in the
Reading Guide.

---

## Generated files

These are written next to the source and are safe to delete:

| File | Purpose |
|---|---|
| `output.mp3` | Latest generated reference audio. |
| `output.tmp.mp3` | Partial download; removed automatically on failure. |
| `shadowing_recording.wav` | Your last shadowing take (mono, PCM 16-bit). |

All three are listed in `.gitignore`.

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `RuntimeError: espeak not installed` or empty IPA | `brew install espeak-ng`. |
| `No audio was received from edge-tts.` | No internet, or the Edge TTS endpoint rejected the request. Retry. |
| `No microphone audio was captured.` | Grant microphone permission in *System Settings → Privacy & Security → Microphone*, and check the selected input device. |
| Some words are not highlighted | Numbers, symbols and abbreviations are spoken differently than written, so their boundary cannot be mapped. The status bar shows the synchronized ratio. |
| British IPA fails | `phonemizer` falls back from `en-gb` to `en` automatically; if it still fails, check your espeak-ng voice data. |
| Shortcuts do nothing | Click outside the text box first — shortcuts are suppressed while editing. |

---

## Notes & limitations

- macOS only. Playback (`AVAudioPlayer`) and the PyObjC dependencies are Apple-specific.
- The Reading Guide is a *study aid*, not a phonetic ground truth. Linking, weak forms
  and intonation vary with speaker, speed, emphasis and context.
- There is no pronunciation scoring — shadowing is A/B comparison by ear, by design.
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
