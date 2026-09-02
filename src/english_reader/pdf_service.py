"""PDF loading and page-by-page text extraction.

The app reads one page at a time: the document stays open and each page
is extracted on demand, so a long PDF never has to be parsed in full.

Raw PDF extraction is not reading material. Words arrive separated by
whatever whitespace the producer used (tabs are common), every visual
line ends in a line break, and paragraph breaks are not marked at all.
`normalize_page_text` turns that back into paragraphs before the text
reaches the textbox, because the TTS service and the reading guide both
work on sentences.
"""

import re
from statistics import median

from pypdf import PdfReader


LINE_ENDINGS = re.compile(r"\r\n?")
HYPHEN_BREAK = re.compile(r"(?<=\w)-\n(?=\w)")

# Every whitespace run except the line breaks: tabs, non-breaking and
# typographic spaces all collapse into a single ordinary space.
HORIZONTAL_SPACE = re.compile(r"[^\S\n]+")

SENTENCE_END = (
    ".",
    "!",
    "?",
    ":",
    ";",
    '"',
    "\u201d",
    "\u2019",
    ")",
)

# A short line followed by one of these starts something new — a title,
# a caption or a fresh paragraph — rather than continuing a sentence.
OPENING_MARKS = (
    "(",
    "[",
    '"',
    "\u201c",
    "\u2018",
)

# Glued to the previous fragment instead of being spaced away from it.
LEADING_PUNCTUATION = (
    ".",
    ",",
    ";",
    ":",
    "!",
    "?",
    ")",
    "]",
    "\u201d",
    "\u2019",
)

# A line shorter than this fraction of the typical line is a candidate
# for ending a paragraph. Justified text keeps every inner line at
# nearly the same width, so the last one stands out.
PARAGRAPH_WIDTH_RATIO = 0.85


class PdfError(Exception):
    """Raised when a PDF cannot be opened or a page cannot be read."""


def normalize_page_text(
    raw: str,
) -> str:
    """Turn raw page text into paragraphs separated by blank lines."""
    text = LINE_ENDINGS.sub(
        "\n",
        raw,
    )

    # A word split across two lines ("read-\ning") is joined back.
    text = HYPHEN_BREAK.sub(
        "",
        text,
    )

    lines = [
        HORIZONTAL_SPACE.sub(
            " ",
            line,
        )
        for line in text.split("\n")
    ]

    paragraphs = []
    current = []
    width = paragraph_width(lines)

    for index, line in enumerate(lines):
        if line.strip():
            current.append(line)

        following = (
            lines[index + 1]
            if index + 1 < len(lines)
            else ""
        )

        if current and ends_paragraph(
            line,
            following,
            width,
        ):
            paragraphs.append(
                join_lines(current)
            )
            current = []

    if current:
        paragraphs.append(
            join_lines(current)
        )

    return "\n\n".join(
        paragraph
        for paragraph in paragraphs
        if paragraph
    )


def paragraph_width(
    lines: list[str],
) -> float:
    """Width below which a line looks like the end of a paragraph."""
    widths = [
        len(line)
        for line in lines
        if line.strip()
    ]

    if not widths:
        return 0.0

    return median(widths) * PARAGRAPH_WIDTH_RATIO


def ends_paragraph(
    line: str,
    following: str,
    width: float,
) -> bool:
    """Decide whether a paragraph ends at `line`.

    PDFs mark no paragraph breaks, so the decision rests on the shape of
    the page: a full-width line always continues, a short line that
    closes a sentence ends the paragraph, and a line left hanging on a
    separator is an extraction artifact that continues.
    """
    stripped = line.rstrip()

    if not stripped:
        return True

    # A fragment with no letters or digits ("." left over from a link)
    # belongs to the line before it.
    if not any(
        character.isalnum()
        for character in stripped
    ):
        return False

    if stripped.endswith(SENTENCE_END):
        return len(stripped) < width

    # The extraction cut the line mid-sentence and left the separator.
    if stripped != line:
        return False

    if len(stripped) >= width:
        return False

    opening = following.lstrip()[:1]

    return bool(opening) and (
        opening.isupper()
        or opening in OPENING_MARKS
    )


def join_lines(
    lines: list[str],
) -> str:
    """Join the lines of one paragraph into a single line of text."""
    paragraph = ""

    for line in lines:
        piece = line.strip()

        if not piece:
            continue

        if not paragraph:
            paragraph = piece
        elif piece[0] in LEADING_PUNCTUATION:
            paragraph += piece
        else:
            paragraph += f" {piece}"

    return paragraph


class PdfDocument:
    """An open PDF ready for page-by-page text extraction."""

    def __init__(
        self,
        path: str,
        stream,
        reader: PdfReader,
    ):
        self.path = path
        self.stream = stream
        self.reader = reader

    @classmethod
    def open(
        cls,
        path: str,
    ) -> "PdfDocument":
        try:
            stream = open(
                path,
                "rb",
            )
        except OSError as error:
            raise PdfError(
                f"the file could not be opened ({error.strerror})."
            ) from error

        try:
            reader = PdfReader(stream)

            if reader.is_encrypted:
                cls.unlock(reader)

            page_count = len(reader.pages)
        except PdfError:
            stream.close()
            raise
        except Exception as error:
            stream.close()
            raise PdfError(
                "the file is not a readable PDF."
            ) from error

        if page_count == 0:
            stream.close()
            raise PdfError(
                "the PDF has no pages."
            )

        return cls(
            path,
            stream,
            reader,
        )

    @staticmethod
    def unlock(
        reader: PdfReader,
    ):
        """Open an encrypted PDF that uses an empty password.

        Many PDFs are encrypted only to restrict printing or copying and
        still open without a password. One that needs a real password is
        rejected: the app has no place to ask for it.
        """
        try:
            unlocked = reader.decrypt("")
        except Exception as error:
            raise PdfError(
                "the PDF is password protected."
            ) from error

        if not unlocked:
            raise PdfError(
                "the PDF is password protected."
            )

    @property
    def page_count(self) -> int:
        return len(self.reader.pages)

    def text_for_page(
        self,
        index: int,
    ) -> str:
        """Return the normalized text of a 0-based page index.

        An empty string means the page carries no text layer, which is
        what a scanned page looks like. That is not an error here — the
        caller decides how to report it.
        """
        if index < 0 or index >= self.page_count:
            raise PdfError(
                f"page {index + 1} is out of range."
            )

        try:
            raw = self.reader.pages[index].extract_text() or ""
        except Exception as error:
            raise PdfError(
                f"page {index + 1} could not be read."
            ) from error

        return normalize_page_text(raw)

    def close(self):
        try:
            self.stream.close()
        except OSError:
            pass
