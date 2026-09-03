"""Color and shape tokens for the interface.

The app runs in dark mode only, so every color here is a single value
instead of the ``(light, dark)`` tuple CustomTkinter also accepts.

Blue is the primary color: it marks the main action, playback progress
and the selected option. Amber is reserved for one job only — the
current-word highlight inside the text — so it never competes with a
control for attention.
"""

# --- Surfaces -----------------------------------------------------
WINDOW = "#15171A"
SURFACE = "#1D2025"
SURFACE_INSET = "#252930"
SURFACE_SUNKEN = "#191C21"
SURFACE_SELECTED = "#2C3849"
SURFACE_SELECTED_HOVER = "#354357"
BORDER = "#2C313A"
BORDER_STRONG = "#39404B"

# --- Text ---------------------------------------------------------
TEXT = "#E8EAED"
TEXT_SECONDARY = "#9AA1AC"
TEXT_MUTED = "#6E7681"
TEXT_DISABLED = "#4A505A"

# --- Accent -------------------------------------------------------
ACCENT = "#3F7FE0"
ACCENT_HOVER = "#5A93EA"
ACCENT_SOFT = "#8FB6F5"
ON_ACCENT = "#F2F6FF"

# --- Recording ----------------------------------------------------
DANGER = "#D9523C"
DANGER_HOVER = "#E4664F"

# --- Current word -------------------------------------------------
HIGHLIGHT_BG = "#FACC15"
HIGHLIGHT_FG = "#111827"

# --- Shape --------------------------------------------------------
RADIUS_CARD = 12
RADIUS_PRIMARY = 10
RADIUS_CONTROL = 8
RADIUS_SMALL = 6

HEIGHT_PRIMARY = 44
HEIGHT_CONTROL = 38
HEIGHT_SEGMENT = 34
HEIGHT_COMPACT = 30
HEIGHT_TOPBAR = 64
HEIGHT_STATUSBAR = 34

PAD_WINDOW = 24
PAD_CARD_X = 20
PAD_CARD_Y = 16
GAP = 16

# --- Type ---------------------------------------------------------
FONT_READING = 18
FONT_TITLE = 17
FONT_PRIMARY = 15
FONT_GUIDE = 15
FONT_IPA = 14
FONT_CONTROL = 13
FONT_SMALL = 12
FONT_LABEL = 11
