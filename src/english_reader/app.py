import sys
import threading
import time
from bisect import bisect_right

import customtkinter as ctk

from .config import ACCENTS, SPEEDS
from .pronunciation_service import generate_reading_guide
from .recording_service import (
    cancel_recording,
    clear_recording,
    get_recording_duration,
    has_recording,
    is_recording,
    is_recording_playing,
    play_beep,
    play_recording,
    start_recording,
    stop_recording,
    stop_recording_playback,
)
from .tts_service import (
    generate_audio_sync,
    get_current_time,
    get_duration,
    get_word_boundaries,
    is_playing,
    load_audio,
    pause_audio,
    replay_audio,
    resume_audio,
    seek_relative,
    seek_to,
    stop_audio,
    unload_audio,
)


ctk.set_appearance_mode("system")
ctk.set_default_color_theme("blue")


WORD_REPEAT_COUNT = 3
WORD_REPEAT_PAUSE_MS = 320
WORD_CLICK_DELAY_MS = 230
WORD_REPEAT_POLL_MS = 15

SHADOWING_COUNTDOWN_SECONDS = 3
SHADOWING_POLL_MS = 50
SHADOWING_RECORDING_TIMER_MS = 100
SHADOWING_COMPARE_PAUSE_MS = 450


class CollapsibleGuideSection(ctk.CTkFrame):
    """A collapsible section used inside the Reading Guide."""

    def __init__(
        self,
        master,
        title: str,
        expanded: bool = True,
        scroll_bind_callback=None,
    ):
        super().__init__(
            master,
            fg_color="transparent",
        )

        self.title = title
        self.expanded = expanded
        self.scroll_bind_callback = scroll_bind_callback

        self.grid_columnconfigure(
            0,
            weight=1,
        )

        self.header_button = ctk.CTkButton(
            self,
            text="",
            anchor="w",
            height=36,
            corner_radius=8,
            font=ctk.CTkFont(
                size=15,
                weight="bold",
            ),
            command=self.toggle,
        )
        self.header_button.grid(
            row=0,
            column=0,
            sticky="ew",
        )

        self.content_frame = ctk.CTkFrame(
            self,
            fg_color="transparent",
        )
        self.content_frame.grid_columnconfigure(
            0,
            weight=1,
        )

        self._update_visibility()
        self._bind_scroll(self)
        self._bind_scroll(self.header_button)
        self._bind_scroll(self.content_frame)

    def _bind_scroll(self, widget):
        if self.scroll_bind_callback is not None:
            self.scroll_bind_callback(widget)

    def _update_visibility(self):
        arrow = "▾" if self.expanded else "▸"

        self.header_button.configure(
            text=f"{arrow}  {self.title}"
        )

        if self.expanded:
            self.content_frame.grid(
                row=1,
                column=0,
                padx=(10, 4),
                pady=(6, 10),
                sticky="ew",
            )
        else:
            self.content_frame.grid_remove()

    def toggle(self):
        self.expanded = not self.expanded
        self._update_visibility()

    def add_text(
        self,
        text: str,
        size: int = 14,
        weight: str = "normal",
        pady=(0, 8),
    ):
        label = ctk.CTkLabel(
            self.content_frame,
            text=text,
            anchor="nw",
            justify="left",
            wraplength=500,
            font=ctk.CTkFont(
                size=size,
                weight=weight,
            ),
        )
        label.pack(
            fill="x",
            pady=pady,
        )

        self._bind_scroll(label)

        return label


class EnglishReaderApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("English Reader")
        self.geometry("1240x800")
        self.minsize(1000, 680)

        self.audio_loaded = False
        self.playback_state = "idle"
        self.progress_job = None

        self.pending_text = ""
        self.pending_config = None
        self.pending_guide_data = None

        self.generated_text = ""
        self.word_boundaries = []
        self.word_starts = []
        self.highlighted_word_index = None

        # Word interaction / repetition state
        self.word_click_job = None
        self.word_repeat_job = None
        self.word_repeat_boundary = None
        self.word_repeat_index = None
        self.word_repeat_current = 0
        self.word_repeat_total = WORD_REPEAT_COUNT

        # Shadowing state
        self.shadowing_state = "idle"
        self.shadowing_job = None
        self.shadowing_countdown_value = 0
        self.shadowing_recording_started_at = None
        self.shadowing_recording_duration = 0.0

        self.create_widgets()
        self.bind_media_shortcuts()

    # =========================================================
    # UI
    # =========================================================
    def create_widgets(self):
        self.title_label = ctk.CTkLabel(
            self,
            text="English Reader",
            font=ctk.CTkFont(
                size=28,
                weight="bold",
            ),
        )
        self.title_label.pack(
            pady=(24, 14)
        )

        # -----------------------------------------------------
        # Two-column reading area
        # -----------------------------------------------------
        self.content_frame = ctk.CTkFrame(
            self,
            fg_color="transparent",
        )
        self.content_frame.pack(
            padx=32,
            fill="both",
            expand=True,
        )

        self.content_frame.grid_columnconfigure(
            (0, 1),
            weight=1,
            uniform="reading_columns",
        )
        self.content_frame.grid_rowconfigure(
            1,
            weight=1,
        )

        self.text_label = ctk.CTkLabel(
            self.content_frame,
            text="Text",
            anchor="w",
            font=ctk.CTkFont(
                size=16,
                weight="bold",
            ),
        )
        self.text_label.grid(
            row=0,
            column=0,
            padx=(0, 10),
            pady=(0, 6),
            sticky="ew",
        )

        self.guide_label = ctk.CTkLabel(
            self.content_frame,
            text="Reading Guide",
            anchor="w",
            font=ctk.CTkFont(
                size=16,
                weight="bold",
            ),
        )
        self.guide_label.grid(
            row=0,
            column=1,
            padx=(10, 0),
            pady=(0, 6),
            sticky="ew",
        )

        # -----------------------------------------------------
        # Original text
        # -----------------------------------------------------
        self.textbox = ctk.CTkTextbox(
            self.content_frame,
            font=ctk.CTkFont(
                size=18,
            ),
            wrap="word",
        )
        self.textbox.grid(
            row=1,
            column=0,
            padx=(0, 10),
            sticky="nsew",
        )

        self.textbox.tag_config(
            "current_word",
            background="#FACC15",
            foreground="#111827",
        )

        self.textbox.edit_modified(False)

        self.textbox.bind(
            "<<Modified>>",
            self.on_text_modified,
        )

        self.textbox.bind(
            "<Button-1>",
            self.on_text_click,
        )

        self.textbox.bind(
            "<Double-Button-1>",
            self.on_text_double_click,
        )

        # -----------------------------------------------------
        # Reading Guide
        #
        # A scrollable frame is used instead of a CTkTextbox
        # because CTkTextbox intentionally forbids per-tag font
        # sizes. Labels let us render normal text at 16 and IPA
        # at 14 without relying on private widget internals.
        # -----------------------------------------------------
        self.guide_frame = ctk.CTkScrollableFrame(
            self.content_frame,
        )
        self.guide_frame.grid(
            row=1,
            column=1,
            padx=(10, 0),
            sticky="nsew",
        )
        self.guide_frame.grid_columnconfigure(
            0,
            weight=1,
        )

        self.bind_guide_mousewheel(
            self.guide_frame
        )

        self.render_guide_message(
            "Generate audio to create the pronunciation guide."
        )

        # -----------------------------------------------------
        # Options
        # -----------------------------------------------------
        self.options_frame = ctk.CTkFrame(
            self,
            fg_color="transparent",
        )
        self.options_frame.pack(
            padx=32,
            pady=(18, 0),
            fill="x",
        )
        self.options_frame.grid_columnconfigure(
            (0, 1, 2),
            weight=1,
        )

        self.accent_label = ctk.CTkLabel(
            self.options_frame,
            text="Accent",
        )
        self.accent_label.grid(
            row=0,
            column=0,
            padx=5,
            sticky="w",
        )

        self.accent_menu = ctk.CTkOptionMenu(
            self.options_frame,
            values=list(
                ACCENTS.keys()
            ),
            command=self.on_configuration_changed,
        )
        self.accent_menu.set("American")
        self.accent_menu.grid(
            row=1,
            column=0,
            padx=5,
            pady=(5, 0),
            sticky="ew",
        )

        self.voice_label = ctk.CTkLabel(
            self.options_frame,
            text="Voice",
        )
        self.voice_label.grid(
            row=0,
            column=1,
            padx=5,
            sticky="w",
        )

        self.voice_menu = ctk.CTkOptionMenu(
            self.options_frame,
            values=[
                "Male",
                "Female",
            ],
            command=self.on_configuration_changed,
        )
        self.voice_menu.set("Male")
        self.voice_menu.grid(
            row=1,
            column=1,
            padx=5,
            pady=(5, 0),
            sticky="ew",
        )

        self.speed_label = ctk.CTkLabel(
            self.options_frame,
            text="Speed",
        )
        self.speed_label.grid(
            row=0,
            column=2,
            padx=5,
            sticky="w",
        )

        self.speed_menu = ctk.CTkOptionMenu(
            self.options_frame,
            values=list(
                SPEEDS.keys()
            ),
            command=self.on_configuration_changed,
        )
        self.speed_menu.set("Learning")
        self.speed_menu.grid(
            row=1,
            column=2,
            padx=5,
            pady=(5, 0),
            sticky="ew",
        )

        # -----------------------------------------------------
        # Generate
        # -----------------------------------------------------
        self.read_button = ctk.CTkButton(
            self,
            text="▶ Generate & Play",
            height=44,
            font=ctk.CTkFont(
                size=16,
                weight="bold",
            ),
            command=self.on_read,
        )
        self.read_button.pack(
            padx=37,
            pady=(18, 14),
            fill="x",
        )

        # -----------------------------------------------------
        # Progress
        # -----------------------------------------------------
        self.progress_frame = ctk.CTkFrame(
            self,
            fg_color="transparent",
        )
        self.progress_frame.pack(
            padx=40,
            pady=(0, 12),
            fill="x",
        )
        self.progress_frame.grid_columnconfigure(
            1,
            weight=1,
        )

        self.current_time_label = ctk.CTkLabel(
            self.progress_frame,
            text="00:00",
            width=50,
        )
        self.current_time_label.grid(
            row=0,
            column=0,
            padx=(0, 10),
        )

        self.progress_slider = ctk.CTkSlider(
            self.progress_frame,
            from_=0,
            to=1,
            command=self.on_seek,
            state="disabled",
        )
        self.progress_slider.set(0)
        self.progress_slider.grid(
            row=0,
            column=1,
            sticky="ew",
        )

        self.duration_label = ctk.CTkLabel(
            self.progress_frame,
            text="00:00",
            width=50,
        )
        self.duration_label.grid(
            row=0,
            column=2,
            padx=(10, 0),
        )

        # -----------------------------------------------------
        # Media controls
        # -----------------------------------------------------
        self.media_frame = ctk.CTkFrame(
            self,
            fg_color="transparent",
        )
        self.media_frame.pack(
            padx=40,
            fill="x",
        )
        self.media_frame.grid_columnconfigure(
            (0, 1, 2, 3, 4),
            weight=1,
        )

        self.rewind_button = ctk.CTkButton(
            self.media_frame,
            text="↶ 1s",
            command=self.on_rewind,
            state="disabled",
        )
        self.rewind_button.grid(
            row=0,
            column=0,
            padx=5,
            sticky="ew",
        )

        self.replay_button = ctk.CTkButton(
            self.media_frame,
            text="↻ Replay",
            command=self.on_replay,
            state="disabled",
        )
        self.replay_button.grid(
            row=0,
            column=1,
            padx=5,
            sticky="ew",
        )

        self.pause_button = ctk.CTkButton(
            self.media_frame,
            text="⏸ Pause",
            command=self.on_play_pause,
            state="disabled",
        )
        self.pause_button.grid(
            row=0,
            column=2,
            padx=5,
            sticky="ew",
        )

        self.stop_button = ctk.CTkButton(
            self.media_frame,
            text="⏹ Stop",
            command=self.on_stop,
            state="disabled",
        )
        self.stop_button.grid(
            row=0,
            column=3,
            padx=5,
            sticky="ew",
        )

        self.forward_button = ctk.CTkButton(
            self.media_frame,
            text="1s ↷",
            command=self.on_forward,
            state="disabled",
        )
        self.forward_button.grid(
            row=0,
            column=4,
            padx=5,
            sticky="ew",
        )

        # -----------------------------------------------------
        # Shadowing practice
        # -----------------------------------------------------
        self.shadowing_frame = ctk.CTkFrame(
            self,
            fg_color="transparent",
        )
        self.shadowing_frame.pack(
            padx=40,
            pady=(12, 0),
            fill="x",
        )
        self.shadowing_frame.grid_columnconfigure(
            0,
            weight=2,
        )
        self.shadowing_frame.grid_columnconfigure(
            (1, 2),
            weight=1,
        )

        self.shadowing_button = ctk.CTkButton(
            self.shadowing_frame,
            text="🎙 Shadowing",
            height=38,
            command=self.on_shadowing_button,
            state="disabled",
        )
        self.shadowing_button.grid(
            row=0,
            column=0,
            padx=(0, 5),
            sticky="ew",
        )

        self.shadowing_mine_button = ctk.CTkButton(
            self.shadowing_frame,
            text="▶ Mine",
            height=38,
            command=self.play_shadowing_mine,
            state="disabled",
        )
        self.shadowing_mine_button.grid(
            row=0,
            column=1,
            padx=5,
            sticky="ew",
        )

        self.shadowing_reference_button = ctk.CTkButton(
            self.shadowing_frame,
            text="▶ Reference",
            height=38,
            command=self.play_shadowing_reference,
            state="disabled",
        )
        self.shadowing_reference_button.grid(
            row=0,
            column=2,
            padx=(5, 0),
            sticky="ew",
        )

        self.shadowing_info_label = ctk.CTkLabel(
            self,
            text="Generate audio before starting Shadowing.",
            font=ctk.CTkFont(
                size=12,
            ),
            text_color=(
                "gray45",
                "gray65",
            ),
        )
        self.shadowing_info_label.pack(
            pady=(6, 0)
        )

        self.shortcuts_label = ctk.CTkLabel(
            self,
            text=(
                "Space  Play/Pause    ·    "
                "←  -1s    ·    →  +1s    ·    "
                "Double-click word  Repeat ×3"
            ),
            font=ctk.CTkFont(
                size=12,
            ),
            text_color=(
                "gray45",
                "gray65",
            ),
        )
        self.shortcuts_label.pack(
            pady=(8, 0)
        )

        self.status_label = ctk.CTkLabel(
            self,
            text="Ready",
        )
        self.status_label.pack(
            pady=(12, 16)
        )

    # =========================================================
    # Generation
    # =========================================================
    def on_read(self):
        text = self.get_text()

        if not text.strip():
            self.status_label.configure(
                text="Enter some text first."
            )
            return

        accent = self.accent_menu.get()
        gender = self.voice_menu.get()
        speed = self.speed_menu.get()

        voice = ACCENTS[accent][gender]
        rate = SPEEDS[speed]

        self.invalidate_generated_audio(
            message=None,
        )

        self.pending_text = text
        self.pending_config = (
            accent,
            gender,
            speed,
        )
        self.pending_guide_data = None

        self.read_button.configure(
            state="disabled",
            text=(
                "Generating audio and "
                "pronunciation guide..."
            ),
        )

        self.disable_media_buttons()

        self.render_guide_message(
            "Analyzing pronunciation..."
        )

        self.status_label.configure(
            text="Generating..."
        )

        thread = threading.Thread(
            target=self.run_generation,
            args=(
                text,
                voice,
                rate,
                accent,
            ),
            daemon=True,
        )
        thread.start()

    def run_generation(
        self,
        text: str,
        voice: str,
        rate: str,
        accent: str,
    ):
        try:
            generate_audio_sync(
                text=text,
                voice=voice,
                rate=rate,
            )

            boundaries = get_word_boundaries()

            try:
                self.pending_guide_data = (
                    generate_reading_guide(
                        text=text,
                        boundaries=boundaries,
                        accent=accent,
                    )
                )

            except Exception as guide_error:
                self.pending_guide_data = {
                    "error": str(guide_error)
                }

            self.after(
                0,
                self.on_audio_generated,
            )

        except Exception as error:
            self.after(
                0,
                self.on_audio_error,
                str(error),
            )

    def on_audio_generated(self):
        current_config = (
            self.accent_menu.get(),
            self.voice_menu.get(),
            self.speed_menu.get(),
        )

        if (
            self.get_text() != self.pending_text
            or current_config != self.pending_config
        ):
            self.read_button.configure(
                state="normal",
                text="▶ Generate & Play",
            )

            self.disable_media_buttons()
            self.reset_progress()

            self.render_guide_message(
                "Text or settings changed — "
                "generate audio again."
            )

            self.status_label.configure(
                text=(
                    "Text or settings changed — "
                    "generate audio again."
                )
            )
            return

        try:
            load_audio()

            duration = get_duration()

            self.generated_text = self.pending_text
            self.word_boundaries = (
                get_word_boundaries()
            )
            self.word_starts = [
                boundary["start"]
                for boundary
                in self.word_boundaries
            ]
            self.highlighted_word_index = None

            self.audio_loaded = True
            self.playback_state = "playing"

            self.render_reading_guide(
                self.pending_guide_data
            )

            self.progress_slider.configure(
                from_=0,
                to=max(duration, 1.0),
                state="normal",
            )
            self.progress_slider.set(0)

            self.duration_label.configure(
                text=self.format_time(duration)
            )
            self.current_time_label.configure(
                text="00:00"
            )

            resume_audio()

            self.read_button.configure(
                state="normal",
                text="▶ Generate & Play",
            )

            self.enable_media_buttons()
            self.prepare_shadowing_for_audio(
                reference_duration=duration
            )

            self.pause_button.configure(
                text="⏸ Pause"
            )

            mapped_words = sum(
                1
                for boundary
                in self.word_boundaries
                if boundary["char_start"]
                is not None
            )

            self.status_label.configure(
                text=(
                    f"Playing · "
                    f"{mapped_words}/"
                    f"{len(self.word_boundaries)} "
                    f"words synchronized"
                )
            )

            self.start_progress_updates()

        except Exception as error:
            self.on_audio_error(
                str(error)
            )

    def on_audio_error(
        self,
        error: str,
    ):
        self.invalidate_generated_audio(
            message=None,
        )

        self.read_button.configure(
            state="normal",
            text="▶ Generate & Play",
        )

        self.render_guide_message(
            "Unable to generate the Reading Guide."
        )

        self.status_label.configure(
            text=f"Error: {error}"
        )

    # =========================================================
    # Reading Guide
    # =========================================================
    def clear_guide_widgets(self):
        for widget in self.guide_frame.winfo_children():
            widget.destroy()

    def bind_guide_mousewheel(self, widget):
        """
        Ensure that the mouse wheel scrolls the Reading Guide even
        when the pointer is over labels/buttons inside the frame.

        CTkScrollableFrame uses an internal Canvas and does not expose
        a public yview API, so this small adapter delegates to the
        canvas owned by the widget.
        """
        try:
            widget.bind(
                "<MouseWheel>",
                self.on_guide_mousewheel,
                add="+",
            )
            widget.bind(
                "<Button-4>",
                self.on_guide_mousewheel,
                add="+",
            )
            widget.bind(
                "<Button-5>",
                self.on_guide_mousewheel,
                add="+",
            )
        except (AttributeError, NotImplementedError):
            pass

    def on_guide_mousewheel(self, event):
        canvas = self.guide_frame._parent_canvas

        if canvas.yview() == (0.0, 1.0):
            return "break"

        if sys.platform == "darwin":
            units = -int(event.delta)

            if units == 0:
                units = -1 if event.delta > 0 else 1

        elif sys.platform.startswith("win"):
            units = -int(event.delta / 120)

            if units == 0:
                units = -1 if event.delta > 0 else 1

        else:
            units = -1 if event.num == 4 else 1

        canvas.yview_scroll(
            units,
            "units",
        )

        return "break"

    def render_guide_message(
        self,
        message: str,
    ):
        self.clear_guide_widgets()

        label = ctk.CTkLabel(
            self.guide_frame,
            text=message,
            anchor="nw",
            justify="left",
            wraplength=500,
            font=ctk.CTkFont(
                size=14,
            ),
        )
        label.grid(
            row=0,
            column=0,
            padx=8,
            pady=8,
            sticky="ew",
        )

        self.bind_guide_mousewheel(
            label
        )

    def create_guide_section(
        self,
        row: int,
        title: str,
        expanded: bool,
    ) -> CollapsibleGuideSection:
        section = CollapsibleGuideSection(
            self.guide_frame,
            title=title,
            expanded=expanded,
            scroll_bind_callback=(
                self.bind_guide_mousewheel
            ),
        )
        section.grid(
            row=row,
            column=0,
            padx=6,
            pady=(0, 8),
            sticky="ew",
        )

        self.bind_guide_mousewheel(
            section
        )

        return section

    def render_reading_guide(
        self,
        guide: dict | None,
    ):
        self.clear_guide_widgets()

        if not guide:
            self.render_guide_message(
                "No Reading Guide available."
            )
            return

        if "error" in guide:
            section = self.create_guide_section(
                row=0,
                title="READING GUIDE ERROR",
                expanded=True,
            )
            section.add_text(
                guide["error"],
                size=14,
            )
            return

        row = 0

        # Pronunciation is the primary study view, so it opens by default.
        pronunciation = self.create_guide_section(
            row=row,
            title=(
                "PRONUNCIATION · "
                f"{guide['accent']} English"
            ),
            expanded=True,
        )
        row += 1

        for sentence in guide["sentences"]:
            pronunciation.add_text(
                sentence["text"],
                size=16,
                pady=(4, 1),
            )

            pronunciation.add_text(
                f"/{sentence['ipa']}/",
                size=14,
                pady=(0, 12),
            )

        # Connected speech is also immediately useful while listening.
        connected = self.create_guide_section(
            row=row,
            title="CONNECTED SPEECH + PAUSES",
            expanded=True,
        )
        row += 1
        connected.add_text(
            guide["connected_speech"],
            size=14,
        )

        chunks = self.create_guide_section(
            row=row,
            title="CHUNKS / THOUGHT GROUPS",
            expanded=True,
        )
        row += 1
        chunks.add_text(
            guide["chunks"],
            size=14,
        )

        stress = self.create_guide_section(
            row=row,
            title="LEXICAL STRESS",
            expanded=False,
        )
        row += 1
        stress.add_text(
            guide["stress"],
            size=14,
        )

        weak_forms = self.create_guide_section(
            row=row,
            title="POSSIBLE WEAK FORMS",
            expanded=False,
        )
        row += 1
        weak_forms.add_text(
            guide["weak_forms"],
            size=14,
        )

        intonation = self.create_guide_section(
            row=row,
            title="INTONATION GUIDE",
            expanded=False,
        )
        row += 1
        intonation.add_text(
            guide["intonation"],
            size=14,
        )

        legend = self.create_guide_section(
            row=row,
            title="LEGEND",
            expanded=False,
        )

        legend.add_text(
            (
                "/   chunk / thought-group boundary\n"
                "‿   linking\n"
                "|   short pause\n"
                "||  long pause / phrase boundary\n"
                "↗   rising intonation\n"
                "↘   falling intonation\n"
                "→   continuing intonation\n"
                "ˈ   primary lexical stress\n"
                "ˌ   secondary lexical stress"
            ),
            size=14,
        )

        legend.add_text(
            (
                "IPA and lexical stress come from "
                "eSpeak. Pauses use the generated "
                "TTS timing when available. Linking, "
                "weak forms and intonation are a "
                "reading guide and can vary with "
                "speaker, speed, emphasis and context."
            ),
            size=12,
            pady=(4, 8),
        )

    # =========================================================
    # Shadowing practice
    # =========================================================
    def prepare_shadowing_for_audio(
        self,
        reference_duration: float,
    ):
        self.cancel_shadowing_sequence(
            restore_controls=False,
        )
        clear_recording()

        self.shadowing_state = "idle"
        self.shadowing_recording_duration = 0.0

        self.shadowing_button.configure(
            text="🎙 Shadowing",
            state="normal",
        )
        self.shadowing_mine_button.configure(
            state="disabled"
        )
        self.shadowing_reference_button.configure(
            state="disabled"
        )
        self.shadowing_info_label.configure(
            text=(
                "Reference: "
                f"{self.format_precise_duration(reference_duration)}"
                " · Record the complete text when ready."
            )
        )

    def on_shadowing_button(self):
        if not self.audio_loaded:
            return

        if self.shadowing_state == "recording":
            self.finish_shadowing_recording()
            return

        if self.shadowing_state in {
            "countdown",
            "beep",
        }:
            self.cancel_shadowing_sequence(
                restore_controls=True,
            )
            self.status_label.configure(
                text="Shadowing cancelled"
            )
            return

        # Retry is also available while the automatic comparison
        # or a manual comparison is still playing.
        self.start_shadowing_attempt()

    def start_shadowing_attempt(self):
        if not self.audio_loaded:
            return

        self.cancel_shadowing_sequence(
            restore_controls=False,
        )
        self.cancel_pending_word_click()
        self.cancel_word_repeat(
            pause_audio_now=True
        )
        self.stop_progress_updates()
        stop_recording_playback()

        if is_playing():
            pause_audio()

        self.playback_state = "paused"
        self.shadowing_state = "countdown"
        self.shadowing_countdown_value = (
            SHADOWING_COUNTDOWN_SECONDS
        )
        self.shadowing_recording_started_at = None

        self.set_non_shadowing_controls_enabled(
            False
        )

        # The primary button remains active so the attempt can be
        # cancelled during the countdown and becomes Stop while recording.
        self.shadowing_button.configure(
            state="normal"
        )
        self.shadowing_mine_button.configure(
            state="disabled"
        )
        self.shadowing_reference_button.configure(
            state="disabled"
        )

        self.run_shadowing_countdown()

    def run_shadowing_countdown(self):
        self.shadowing_job = None

        if self.shadowing_state != "countdown":
            return

        if self.shadowing_countdown_value <= 0:
            self.start_shadowing_beep()
            return

        value = self.shadowing_countdown_value

        self.shadowing_button.configure(
            text=f"Cancel · {value}"
        )
        self.shadowing_info_label.configure(
            text=(
                f"Recording starts in {value}..."
            )
        )
        self.status_label.configure(
            text=f"Shadowing · {value}"
        )

        self.shadowing_countdown_value -= 1

        self.shadowing_job = self.after(
            1000,
            self.run_shadowing_countdown,
        )

    def start_shadowing_beep(self):
        self.shadowing_state = "beep"
        self.shadowing_button.configure(
            text="Cancel · ♪"
        )
        self.shadowing_info_label.configure(
            text="Get ready..."
        )
        self.status_label.configure(
            text="Shadowing · Get ready"
        )

        thread = threading.Thread(
            target=self.shadowing_beep_worker,
            daemon=True,
        )
        thread.start()

    def shadowing_beep_worker(self):
        beep_error = None

        try:
            play_beep()
        except Exception as error:
            # A missing output device should not prevent recording.
            beep_error = str(error)

        self.after(
            0,
            self.begin_shadowing_recording,
            beep_error,
        )

    def begin_shadowing_recording(
        self,
        beep_error: str | None = None,
    ):
        if self.shadowing_state != "beep":
            return

        try:
            start_recording()
        except Exception as error:
            self.on_shadowing_error(
                str(error)
            )
            return

        self.shadowing_state = "recording"
        self.shadowing_recording_started_at = (
            time.monotonic()
        )

        self.shadowing_button.configure(
            text="■ Stop Recording",
            state="normal",
        )

        if beep_error:
            self.shadowing_info_label.configure(
                text=(
                    "● Recording · cue sound unavailable"
                )
            )
        else:
            self.shadowing_info_label.configure(
                text="● Recording · 00:00.0"
            )

        self.status_label.configure(
            text="● Recording"
        )

        self.update_shadowing_recording_timer()

    def update_shadowing_recording_timer(self):
        self.shadowing_job = None

        if (
            self.shadowing_state != "recording"
            or self.shadowing_recording_started_at is None
        ):
            return

        elapsed = (
            time.monotonic()
            - self.shadowing_recording_started_at
        )

        self.shadowing_info_label.configure(
            text=(
                "● Recording · "
                f"{self.format_precise_duration(elapsed)}"
            )
        )

        self.shadowing_job = self.after(
            SHADOWING_RECORDING_TIMER_MS,
            self.update_shadowing_recording_timer,
        )

    def finish_shadowing_recording(self):
        if self.shadowing_state != "recording":
            return

        self.cancel_shadowing_job()

        try:
            duration = stop_recording()
        except Exception as error:
            self.on_shadowing_error(
                str(error)
            )
            return

        self.shadowing_recording_duration = duration
        self.shadowing_recording_started_at = None

        self.shadowing_button.configure(
            text="↻ Retry",
            state="normal",
        )
        self.shadowing_mine_button.configure(
            state="disabled"
        )
        self.shadowing_reference_button.configure(
            state="disabled"
        )

        self.update_shadowing_duration_label()
        self.status_label.configure(
            text="Shadowing · Preparing comparison"
        )

        self.shadowing_state = "comparison_wait"
        self.shadowing_job = self.after(
            250,
            self.start_shadowing_mine_auto,
        )

    def start_shadowing_mine_auto(self):
        self.shadowing_job = None

        if self.shadowing_state != "comparison_wait":
            return

        try:
            if is_playing():
                pause_audio()

            play_recording()
        except Exception as error:
            self.on_shadowing_error(
                str(error)
            )
            return

        self.shadowing_state = "playing_mine_auto"
        self.status_label.configure(
            text="Shadowing · Playing your recording"
        )

        self.shadowing_job = self.after(
            SHADOWING_POLL_MS,
            self.poll_shadowing_mine_auto,
        )

    def poll_shadowing_mine_auto(self):
        self.shadowing_job = None

        if self.shadowing_state != "playing_mine_auto":
            return

        if is_recording_playing():
            self.shadowing_job = self.after(
                SHADOWING_POLL_MS,
                self.poll_shadowing_mine_auto,
            )
            return

        self.shadowing_state = "between_comparison"
        self.status_label.configure(
            text="Shadowing · Reference next"
        )

        self.shadowing_job = self.after(
            SHADOWING_COMPARE_PAUSE_MS,
            self.start_shadowing_reference_auto,
        )

    def start_shadowing_reference_auto(self):
        self.shadowing_job = None

        if self.shadowing_state != "between_comparison":
            return

        stop_recording_playback()
        replay_audio()

        self.shadowing_state = "playing_reference_auto"
        self.playback_state = "shadowing_reference"

        self.status_label.configure(
            text="Shadowing · Playing reference"
        )

        self.shadowing_job = self.after(
            60,
            self.poll_shadowing_reference_auto,
        )

    def poll_shadowing_reference_auto(self):
        self.shadowing_job = None

        if self.shadowing_state != "playing_reference_auto":
            return

        self.update_progress_display()

        if is_playing():
            self.shadowing_job = self.after(
                60,
                self.poll_shadowing_reference_auto,
            )
            return

        self.finish_shadowing_comparison()

    def finish_shadowing_comparison(self):
        self.shadowing_state = "ready"
        self.playback_state = "finished"
        self.clear_word_highlight()

        self.shadowing_button.configure(
            text="↻ Retry",
            state="normal",
        )
        self.restore_after_shadowing()
        self.update_shadowing_duration_label()

        self.status_label.configure(
            text="Shadowing comparison complete"
        )

    def play_shadowing_mine(self):
        if (
            not self.audio_loaded
            or not has_recording()
        ):
            return

        self.cancel_shadowing_job()
        stop_recording_playback()
        self.stop_progress_updates()

        if is_playing():
            pause_audio()

        try:
            play_recording()
        except Exception as error:
            self.on_shadowing_error(
                str(error)
            )
            return

        self.shadowing_state = "playing_mine_manual"
        self.playback_state = "paused"
        self.set_non_shadowing_controls_enabled(
            False
        )
        self.shadowing_button.configure(
            text="↻ Retry",
            state="normal",
        )
        self.shadowing_reference_button.configure(
            state="normal"
        )

        self.status_label.configure(
            text="Shadowing · Playing your recording"
        )

        self.shadowing_job = self.after(
            SHADOWING_POLL_MS,
            self.poll_shadowing_mine_manual,
        )

    def poll_shadowing_mine_manual(self):
        self.shadowing_job = None

        if self.shadowing_state != "playing_mine_manual":
            return

        if is_recording_playing():
            self.shadowing_job = self.after(
                SHADOWING_POLL_MS,
                self.poll_shadowing_mine_manual,
            )
            return

        self.shadowing_state = "ready"
        self.restore_after_shadowing()
        self.status_label.configure(
            text="Shadowing · Ready"
        )

    def play_shadowing_reference(self):
        if not self.audio_loaded:
            return

        self.cancel_shadowing_job()
        stop_recording_playback()
        self.stop_progress_updates()

        replay_audio()

        self.shadowing_state = "playing_reference_manual"
        self.playback_state = "shadowing_reference"

        self.set_non_shadowing_controls_enabled(
            False
        )
        self.shadowing_button.configure(
            text="↻ Retry",
            state="normal",
        )
        self.shadowing_mine_button.configure(
            state=(
                "normal"
                if has_recording()
                else "disabled"
            )
        )

        self.status_label.configure(
            text="Shadowing · Playing reference"
        )

        self.shadowing_job = self.after(
            60,
            self.poll_shadowing_reference_manual,
        )

    def poll_shadowing_reference_manual(self):
        self.shadowing_job = None

        if self.shadowing_state != "playing_reference_manual":
            return

        self.update_progress_display()

        if is_playing():
            self.shadowing_job = self.after(
                60,
                self.poll_shadowing_reference_manual,
            )
            return

        self.shadowing_state = "ready"
        self.playback_state = "finished"
        self.restore_after_shadowing()
        self.status_label.configure(
            text="Shadowing · Ready"
        )

    def update_shadowing_duration_label(self):
        reference = (
            get_duration()
            if self.audio_loaded
            else 0.0
        )

        mine = (
            get_recording_duration()
            if has_recording()
            else self.shadowing_recording_duration
        )

        self.shadowing_info_label.configure(
            text=(
                "Mine: "
                f"{self.format_precise_duration(mine)}"
                "    ·    Reference: "
                f"{self.format_precise_duration(reference)}"
            )
        )

    def cancel_shadowing_job(self):
        if self.shadowing_job is None:
            return

        try:
            self.after_cancel(
                self.shadowing_job
            )
        except Exception:
            pass

        self.shadowing_job = None

    def cancel_shadowing_sequence(
        self,
        restore_controls: bool,
    ):
        self.cancel_shadowing_job()

        if is_recording():
            cancel_recording()

        stop_recording_playback()

        if (
            self.audio_loaded
            and self.shadowing_state in {
                "playing_reference_auto",
                "playing_reference_manual",
            }
            and is_playing()
        ):
            pause_audio()

        self.shadowing_recording_started_at = None
        self.shadowing_countdown_value = 0

        if self.shadowing_state not in {
            "idle",
            "ready",
        }:
            self.shadowing_state = (
                "ready"
                if has_recording()
                else "idle"
            )

        if restore_controls:
            self.restore_after_shadowing()

            self.shadowing_button.configure(
                text=(
                    "↻ Retry"
                    if has_recording()
                    else "🎙 Shadowing"
                ),
                state=(
                    "normal"
                    if self.audio_loaded
                    else "disabled"
                ),
            )

            if self.audio_loaded:
                self.update_shadowing_duration_label()

    def restore_after_shadowing(self):
        if not self.audio_loaded:
            return

        self.read_button.configure(
            state="normal",
            text="▶ Generate & Play",
        )
        self.accent_menu.configure(
            state="normal"
        )
        self.voice_menu.configure(
            state="normal"
        )
        self.speed_menu.configure(
            state="normal"
        )
        self.textbox.configure(
            state="normal"
        )

        self.enable_media_buttons()

        self.shadowing_button.configure(
            state="normal"
        )
        self.shadowing_mine_button.configure(
            state=(
                "normal"
                if has_recording()
                else "disabled"
            )
        )
        self.shadowing_reference_button.configure(
            state="normal"
        )

    def set_non_shadowing_controls_enabled(
        self,
        enabled: bool,
    ):
        state = (
            "normal"
            if enabled
            else "disabled"
        )

        self.read_button.configure(
            state=state
        )
        self.accent_menu.configure(
            state=state
        )
        self.voice_menu.configure(
            state=state
        )
        self.speed_menu.configure(
            state=state
        )
        self.textbox.configure(
            state=state
        )

        if enabled and self.audio_loaded:
            self.enable_media_buttons()
        else:
            self.disable_media_buttons()

        if not enabled:
            self.shadowing_mine_button.configure(
                state="disabled"
            )
            self.shadowing_reference_button.configure(
                state="disabled"
            )

    def on_shadowing_error(
        self,
        error: str,
    ):
        self.cancel_shadowing_sequence(
            restore_controls=True,
        )

        self.shadowing_state = (
            "ready"
            if has_recording()
            else "idle"
        )

        self.shadowing_button.configure(
            text=(
                "↻ Retry"
                if has_recording()
                else "🎙 Shadowing"
            ),
            state=(
                "normal"
                if self.audio_loaded
                else "disabled"
            ),
        )

        self.status_label.configure(
            text=f"Shadowing error: {error}"
        )
        self.shadowing_info_label.configure(
            text=(
                "Microphone error. On macOS, verify Microphone "
                "permission for your terminal or IDE. On Linux, verify "
                "that an input device is available and not in use."
            )
        )

    def format_precise_duration(
        self,
        seconds: float,
    ) -> str:
        seconds = max(
            0.0,
            float(seconds),
        )

        minutes = int(seconds // 60)
        remaining = seconds % 60

        return (
            f"{minutes:02d}:"
            f"{remaining:04.1f}"
        )

    # =========================================================
    # Keyboard shortcuts
    # =========================================================
    def bind_media_shortcuts(self):
        self.bind(
            "<space>",
            self.on_spacebar_shortcut,
        )
        self.bind(
            "<Left>",
            self.on_left_shortcut,
        )
        self.bind(
            "<Right>",
            self.on_right_shortcut,
        )

    def should_ignore_media_shortcut(
        self,
        event,
    ) -> bool:
        """
        Do not hijack typing/navigation keys while the user is editing
        text. The event bubbles to the window, so inspect its source.
        """
        if self.shadowing_state not in {
            "idle",
            "ready",
        }:
            return True

        try:
            widget_class = event.widget.winfo_class()
        except Exception:
            return False

        return widget_class in {
            "Text",
            "Entry",
            "TEntry",
            "Spinbox",
        }

    def on_spacebar_shortcut(
        self,
        event,
    ):
        if self.should_ignore_media_shortcut(event):
            return None

        if not self.audio_loaded:
            return None

        self.on_play_pause()
        return "break"

    def on_left_shortcut(
        self,
        event,
    ):
        if self.should_ignore_media_shortcut(event):
            return None

        if not self.audio_loaded:
            return None

        self.on_rewind()
        return "break"

    def on_right_shortcut(
        self,
        event,
    ):
        if self.should_ignore_media_shortcut(event):
            return None

        if not self.audio_loaded:
            return None

        self.on_forward()
        return "break"

    # =========================================================
    # Playback
    # =========================================================
    def on_play_pause(self):
        if not self.audio_loaded:
            return

        # Any manual media action exits the word-repeat loop.
        if self.playback_state == "word_repeat":
            self.cancel_word_repeat(
                pause_audio_now=True
            )
            self.playback_state = "paused"
            self.pause_button.configure(
                text="▶ Resume"
            )
            self.status_label.configure(
                text="Word repetition paused"
            )
            return

        if self.playback_state == "playing":
            pause_audio()
            self.playback_state = "paused"

            self.pause_button.configure(
                text="▶ Resume"
            )
            self.status_label.configure(
                text="Paused"
            )

            self.stop_progress_updates()
            return

        if self.playback_state == "finished":
            seek_to(0)

            self.progress_slider.set(0)
            self.current_time_label.configure(
                text="00:00"
            )
            self.clear_word_highlight()

        resume_audio()
        self.playback_state = "playing"

        self.pause_button.configure(
            text="⏸ Pause"
        )
        self.status_label.configure(
            text="Playing"
        )

        self.start_progress_updates()

    def on_stop(self):
        if not self.audio_loaded:
            return

        self.cancel_word_repeat()
        self.cancel_pending_word_click()

        stop_audio()
        self.stop_progress_updates()

        self.playback_state = "stopped"

        self.pause_button.configure(
            text="▶ Play"
        )
        self.progress_slider.set(0)
        self.current_time_label.configure(
            text="00:00"
        )
        self.status_label.configure(
            text="Stopped"
        )

        self.clear_word_highlight()

    def on_replay(self):
        if not self.audio_loaded:
            return

        self.cancel_word_repeat()
        self.cancel_pending_word_click()

        replay_audio()
        self.playback_state = "playing"

        self.progress_slider.set(0)
        self.current_time_label.configure(
            text="00:00"
        )

        self.clear_word_highlight()

        self.pause_button.configure(
            text="⏸ Pause"
        )
        self.status_label.configure(
            text="Playing"
        )

        self.start_progress_updates()

    def on_rewind(self):
        if not self.audio_loaded:
            return

        self.cancel_word_repeat(
            pause_audio_now=(
                self.playback_state == "word_repeat"
            )
        )
        self.cancel_pending_word_click()

        seek_relative(-1.0)
        self.handle_manual_seek()

    def on_forward(self):
        if not self.audio_loaded:
            return

        self.cancel_word_repeat(
            pause_audio_now=(
                self.playback_state == "word_repeat"
            )
        )
        self.cancel_pending_word_click()

        seek_relative(1.0)
        self.handle_manual_seek()

    def on_seek(self, value):
        if not self.audio_loaded:
            return

        self.cancel_word_repeat(
            pause_audio_now=(
                self.playback_state == "word_repeat"
            )
        )
        self.cancel_pending_word_click()

        seek_to(float(value))
        self.handle_manual_seek()

    def handle_manual_seek(self):
        current = get_current_time()

        self.update_progress_display()

        if self.playback_state in (
            "stopped",
            "finished",
            "word_repeat",
        ):
            self.playback_state = "paused"

            self.pause_button.configure(
                text="▶ Play"
            )

            self.status_label.configure(
                text=(
                    "Ready at "
                    f"{self.format_time(current)}"
                )
            )

    # =========================================================
    # Progress
    # =========================================================
    def start_progress_updates(self):
        self.stop_progress_updates()
        self.update_progress()

    def stop_progress_updates(self):
        if self.progress_job is None:
            return

        try:
            self.after_cancel(
                self.progress_job
            )
        except Exception:
            pass

        self.progress_job = None

    def update_progress(self):
        self.progress_job = None

        if not self.audio_loaded:
            return

        self.update_progress_display()

        if self.playback_state != "playing":
            return

        if is_playing():
            self.progress_job = self.after(
                60,
                self.update_progress,
            )
            return

        duration = get_duration()

        self.progress_slider.set(
            duration
        )

        self.current_time_label.configure(
            text=self.format_time(
                duration
            )
        )

        self.playback_state = "finished"

        self.pause_button.configure(
            text="▶ Play"
        )

        self.status_label.configure(
            text="Finished"
        )

        self.clear_word_highlight()

    def update_progress_display(self):
        if not self.audio_loaded:
            return

        current = get_current_time()

        self.progress_slider.set(
            current
        )

        self.current_time_label.configure(
            text=self.format_time(
                current
            )
        )

        self.update_word_highlight(
            current
        )

    # =========================================================
    # Word tracking
    # =========================================================
    def update_word_highlight(
        self,
        current_time: float,
    ):
        if (
            not self.word_boundaries
            or self.get_text()
            != self.generated_text
        ):
            self.clear_word_highlight()
            return

        index = (
            bisect_right(
                self.word_starts,
                current_time,
            )
            - 1
        )

        if not (
            0 <= index
            < len(self.word_boundaries)
        ):
            self.clear_word_highlight()
            return

        boundary = self.word_boundaries[
            index
        ]

        # Avoid holding the previous word through a real pause.
        if (
            current_time
            > boundary["end"] + 0.08
        ):
            self.clear_word_highlight()
            return

        char_start = boundary[
            "char_start"
        ]
        char_end = boundary[
            "char_end"
        ]

        if (
            char_start is None
            or char_end is None
        ):
            self.clear_word_highlight()
            return

        if (
            self.highlighted_word_index
            == index
        ):
            return

        self.highlight_word(
            index=index,
            char_start=char_start,
            char_end=char_end,
        )

    def highlight_word(
        self,
        index: int,
        char_start: int,
        char_end: int,
    ):
        self.textbox.tag_remove(
            "current_word",
            "1.0",
            "end",
        )

        start_index = (
            f"1.0+{char_start}c"
        )
        end_index = (
            f"1.0+{char_end}c"
        )

        self.textbox.tag_add(
            "current_word",
            start_index,
            end_index,
        )

        self.textbox.see(
            start_index
        )

        self.highlighted_word_index = index

    def clear_word_highlight(self):
        self.textbox.tag_remove(
            "current_word",
            "1.0",
            "end",
        )

        self.highlighted_word_index = None

    # =========================================================
    # Word interaction
    # =========================================================
    def get_boundary_from_text_event(self, event):
        if (
            not self.audio_loaded
            or self.get_text() != self.generated_text
            or self.shadowing_state not in {
                "idle",
                "ready",
            }
        ):
            return None

        try:
            text_widget = event.widget

            clicked_index = text_widget.index(
                f"@{event.x},{event.y}"
            )

            count_result = text_widget.count(
                "1.0",
                clicked_index,
                "chars",
            )

            if not count_result:
                return None

            char_offset = int(
                count_result[0]
            )

        except Exception:
            return None

        return self.find_word_boundary_by_char(
            char_offset
        )

    def on_text_click(self, event):
        """
        Single click keeps the existing behavior: play from the
        selected word onward. The action is delayed briefly so a
        double click can be recognized without first starting normal
        playback.
        """
        boundary = self.get_boundary_from_text_event(
            event
        )

        if boundary is None:
            return

        self.cancel_pending_word_click()

        self.word_click_job = self.after(
            WORD_CLICK_DELAY_MS,
            lambda selected=boundary: (
                self.play_from_word(selected)
            ),
        )

    def on_text_double_click(self, event):
        """Double click repeats only the selected spoken word."""
        boundary = self.get_boundary_from_text_event(
            event
        )

        if boundary is None:
            return "break"

        self.cancel_pending_word_click()
        self.start_word_repeat(
            boundary,
            repeats=WORD_REPEAT_COUNT,
        )

        return "break"

    def play_from_word(self, boundary):
        self.word_click_job = None

        if not self.audio_loaded:
            return

        self.cancel_word_repeat(
            pause_audio_now=(
                self.playback_state == "word_repeat"
            )
        )

        seek_to(
            boundary["start"]
        )

        if not is_playing():
            resume_audio()

        self.playback_state = "playing"

        self.pause_button.configure(
            text="⏸ Pause"
        )

        self.status_label.configure(
            text=(
                "Playing from "
                f"“{boundary['text']}”"
            )
        )

        self.update_progress_display()
        self.start_progress_updates()

    # ---------------------------------------------------------
    # Repeat one word using its existing contextual TTS audio
    # ---------------------------------------------------------
    def start_word_repeat(
        self,
        boundary,
        repeats: int = WORD_REPEAT_COUNT,
    ):
        if not self.audio_loaded:
            return

        self.cancel_word_repeat(
            pause_audio_now=True
        )
        self.stop_progress_updates()

        self.word_repeat_boundary = boundary
        self.word_repeat_index = (
            self.word_boundaries.index(boundary)
        )
        self.word_repeat_total = max(
            1,
            int(repeats),
        )
        self.word_repeat_current = 0
        self.playback_state = "word_repeat"

        self.pause_button.configure(
            text="⏸ Pause"
        )

        self.play_word_repeat_once()

    def play_word_repeat_once(self):
        self.word_repeat_job = None

        if (
            not self.audio_loaded
            or self.word_repeat_boundary is None
        ):
            return

        boundary = self.word_repeat_boundary
        self.word_repeat_current += 1

        seek_to(
            boundary["start"]
        )
        resume_audio()

        char_start = boundary.get(
            "char_start"
        )
        char_end = boundary.get(
            "char_end"
        )

        if (
            char_start is not None
            and char_end is not None
            and self.word_repeat_index is not None
        ):
            self.highlight_word(
                index=self.word_repeat_index,
                char_start=char_start,
                char_end=char_end,
            )

        self.status_label.configure(
            text=(
                f"Repeating “{boundary['text']}” · "
                f"{self.word_repeat_current}/"
                f"{self.word_repeat_total}"
            )
        )

        self.update_progress_display()

        self.word_repeat_job = self.after(
            WORD_REPEAT_POLL_MS,
            self.monitor_word_repeat,
        )

    def monitor_word_repeat(self):
        self.word_repeat_job = None

        if (
            not self.audio_loaded
            or self.playback_state != "word_repeat"
            or self.word_repeat_boundary is None
        ):
            return

        boundary = self.word_repeat_boundary
        current = get_current_time()

        self.progress_slider.set(current)
        self.current_time_label.configure(
            text=self.format_time(current)
        )

        if (
            current >= boundary["end"]
            or not is_playing()
        ):
            pause_audio()
            seek_to(boundary["end"])
            self.update_progress_display()

            if (
                self.word_repeat_current
                < self.word_repeat_total
            ):
                self.word_repeat_job = self.after(
                    WORD_REPEAT_PAUSE_MS,
                    self.play_word_repeat_once,
                )
                return

            repeated_word = boundary["text"]
            repeat_count = self.word_repeat_total

            self.word_repeat_job = None
            self.word_repeat_boundary = None
            self.word_repeat_index = None
            self.playback_state = "paused"

            self.pause_button.configure(
                text="▶ Play"
            )
            self.status_label.configure(
                text=(
                    f"Repeated “{repeated_word}” "
                    f"×{repeat_count}"
                )
            )
            return

        self.word_repeat_job = self.after(
            WORD_REPEAT_POLL_MS,
            self.monitor_word_repeat,
        )

    def cancel_word_repeat(
        self,
        pause_audio_now: bool = False,
    ):
        if self.word_repeat_job is not None:
            try:
                self.after_cancel(
                    self.word_repeat_job
                )
            except Exception:
                pass

            self.word_repeat_job = None

        if (
            pause_audio_now
            and self.audio_loaded
            and is_playing()
        ):
            pause_audio()

        self.word_repeat_boundary = None
        self.word_repeat_index = None
        self.word_repeat_current = 0

    def cancel_pending_word_click(self):
        if self.word_click_job is None:
            return

        try:
            self.after_cancel(
                self.word_click_job
            )
        except Exception:
            pass

        self.word_click_job = None

    def find_word_boundary_by_char(
        self,
        char_offset: int,
    ):
        for boundary in self.word_boundaries:
            char_start = boundary[
                "char_start"
            ]
            char_end = boundary[
                "char_end"
            ]

            if (
                char_start is None
                or char_end is None
            ):
                continue

            if (
                char_start
                <= char_offset
                < char_end
            ):
                return boundary

        return None

    # =========================================================
    # Invalidation
    # =========================================================
    def on_text_modified(
        self,
        event=None,
    ):
        if not self.textbox.edit_modified():
            return

        self.textbox.edit_modified(
            False
        )

        if not self.audio_loaded:
            return

        if self.get_text() == self.generated_text:
            return

        self.invalidate_generated_audio(
            message=(
                "Text changed — "
                "generate audio again."
            )
        )

    def on_configuration_changed(
        self,
        _value=None,
    ):
        if not self.audio_loaded:
            return

        self.invalidate_generated_audio(
            message=(
                "Settings changed — "
                "generate audio again."
            )
        )

    def invalidate_generated_audio(
        self,
        message: str | None,
    ):
        self.cancel_shadowing_sequence(
            restore_controls=False,
        )
        clear_recording()
        self.shadowing_state = "idle"
        self.shadowing_recording_duration = 0.0

        if hasattr(self, "shadowing_button"):
            self.shadowing_button.configure(
                text="🎙 Shadowing",
                state="disabled",
            )
            self.shadowing_mine_button.configure(
                state="disabled"
            )
            self.shadowing_reference_button.configure(
                state="disabled"
            )
            self.shadowing_info_label.configure(
                text="Generate audio before starting Shadowing."
            )

        self.cancel_pending_word_click()
        self.cancel_word_repeat(
            pause_audio_now=True
        )
        self.stop_progress_updates()

        if self.audio_loaded:
            unload_audio()

        self.audio_loaded = False
        self.playback_state = "idle"

        self.generated_text = ""
        self.word_boundaries = []
        self.word_starts = []

        self.clear_word_highlight()
        self.disable_media_buttons()
        self.reset_progress()

        if message is not None:
            self.render_guide_message(
                message
            )
            self.status_label.configure(
                text=message
            )

    # =========================================================
    # Helpers
    # =========================================================
    def get_text(self) -> str:
        return self.textbox.get(
            "1.0",
            "end-1c",
        )

    def reset_progress(self):
        self.progress_slider.configure(
            state="disabled",
            from_=0,
            to=1,
        )

        self.progress_slider.set(0)

        self.current_time_label.configure(
            text="00:00"
        )

        self.duration_label.configure(
            text="00:00"
        )

    def format_time(
        self,
        seconds: float,
    ) -> str:
        seconds = max(
            0,
            int(seconds),
        )

        minutes = seconds // 60
        remaining_seconds = seconds % 60

        return (
            f"{minutes:02d}:"
            f"{remaining_seconds:02d}"
        )

    def enable_media_buttons(self):
        self.rewind_button.configure(
            state="normal"
        )
        self.replay_button.configure(
            state="normal"
        )
        self.pause_button.configure(
            state="normal"
        )
        self.stop_button.configure(
            state="normal"
        )
        self.forward_button.configure(
            state="normal"
        )
        self.progress_slider.configure(
            state="normal"
        )

    def disable_media_buttons(self):
        self.rewind_button.configure(
            state="disabled"
        )
        self.replay_button.configure(
            state="disabled"
        )
        self.pause_button.configure(
            state="disabled"
        )
        self.stop_button.configure(
            state="disabled"
        )
        self.forward_button.configure(
            state="disabled"
        )
        self.progress_slider.configure(
            state="disabled"
        )

    def on_close(self):
        self.cancel_shadowing_sequence(
            restore_controls=False,
        )
        self.cancel_pending_word_click()
        self.cancel_word_repeat(
            pause_audio_now=True
        )
        self.stop_progress_updates()

        if self.audio_loaded:
            unload_audio()

        self.destroy()


def main():
    app = EnglishReaderApp()

    app.protocol(
        "WM_DELETE_WINDOW",
        app.on_close,
    )

    app.mainloop()

