import re

from phonemizer import phonemize
from phonemizer.separator import Separator

from .config import PHONEMIZER_LANGUAGES


WORD_PATTERN = re.compile(
    r"[A-Za-z]+(?:['’][A-Za-z]+)*(?:-[A-Za-z]+)*"
)

IPA_VOWELS = set(
    "aeiou"
    "ɑæɐɒɔ"
    "əɛɜɞ"
    "ɪʊʌ"
    "ɚɝ"
    "ɵœø"
    "ɨɯy"
)

WEAK_FORMS_COMMON = {
    "a": "/ə/",
    "an": "/ən/",
    "the": "/ðə/ · /ði/ before vowel/emphasis",
    "to": "/tə/",
    "and": "/ən/ · /n/",
    "of": "/əv/",
    "can": "/kən/",
    "could": "/kəd/",
    "should": "/ʃəd/",
    "would": "/wəd/",
    "have": "/həv/ · /əv/",
    "has": "/həz/ · /əz/",
    "was": "/wəz/",
}

YES_NO_AUXILIARIES = {
    "am",
    "is",
    "are",
    "was",
    "were",
    "do",
    "does",
    "did",
    "have",
    "has",
    "had",
    "can",
    "could",
    "will",
    "would",
    "shall",
    "should",
    "may",
    "might",
    "must",
}

WH_WORDS = {
    "what",
    "when",
    "where",
    "why",
    "who",
    "whom",
    "whose",
    "which",
    "how",
}


def generate_reading_guide(
    text: str,
    boundaries: list,
    accent: str,
) -> dict:
    language = get_language(accent)

    return {
        "accent": accent,
        "sentences": build_sentence_pronunciations(
            text=text,
            language=language,
        ),
        "connected_speech": build_connected_speech(
            text=text,
            boundaries=boundaries,
            language=language,
        ),
        "chunks": build_chunk_guide(
            text=text,
            boundaries=boundaries,
        ),
        "stress": build_stress_guide(
            text=text,
            language=language,
        ),
        "weak_forms": build_weak_forms(
            text=text,
            accent=accent,
        ),
        "intonation": build_intonation_guide(
            text
        ),
    }


def get_language(accent: str) -> str:
    return PHONEMIZER_LANGUAGES.get(
        accent,
        "en-us",
    )


def split_sentences(text: str) -> list[str]:
    return [
        match.group().strip()
        for match in re.finditer(
            r"[^.!?]+(?:[.!?]+|$)",
            text,
        )
        if match.group().strip()
    ]


def build_sentence_pronunciations(
    text: str,
    language: str,
) -> list[dict]:
    sentences = split_sentences(text)

    if not sentences:
        return []

    ipa_sentences = phonemize_texts(
        texts=sentences,
        language=language,
        preserve_punctuation=True,
    )

    return [
        {
            "text": sentence,
            "ipa": clean_ipa(ipa),
        }
        for sentence, ipa in zip(
            sentences,
            ipa_sentences,
        )
    ]


def phonemize_texts(
    texts: list[str],
    language: str,
    preserve_punctuation: bool,
) -> list[str]:
    if not texts:
        return []

    kwargs = {
        "text": texts,
        "language": language,
        "backend": "espeak",
        "separator": Separator(
            phone=None,
            word=" ",
        ),
        "strip": True,
        "preserve_punctuation": preserve_punctuation,
        "with_stress": True,
        "language_switch": "remove-flags",
        "words_mismatch": "ignore",
        "njobs": 1,
    }

    try:
        result = phonemize(**kwargs)

    except RuntimeError:
        if language != "en-gb":
            raise

        kwargs["language"] = "en"
        result = phonemize(**kwargs)

    if isinstance(result, str):
        return [result]

    return list(result)


def phonemize_words(
    words: list[str],
    language: str,
) -> list[str]:
    result = phonemize_texts(
        texts=words,
        language=language,
        preserve_punctuation=False,
    )

    return [
        clean_ipa(item)
        for item in result
    ]


def clean_ipa(ipa: str) -> str:
    return re.sub(
        r"\s+",
        " ",
        ipa,
    ).strip()


def build_connected_speech(
    text: str,
    boundaries: list,
    language: str,
) -> str:
    mapped = [
        boundary
        for boundary in boundaries
        if (
            boundary.get("char_start")
            is not None
            and boundary.get("char_end")
            is not None
        )
    ]

    if not mapped:
        return (
            "No synchronized word boundaries "
            "were available for this text."
        )

    spoken_words = [
        text[
            boundary["char_start"]:
            boundary["char_end"]
        ]
        for boundary in mapped
    ]

    ipa_words = phonemize_words(
        spoken_words,
        language,
    )

    output = []

    for index, boundary in enumerate(mapped):
        word = spoken_words[index]
        output.append(word)

        if index == len(mapped) - 1:
            trailing = text[
                boundary["char_end"]:
            ].strip()

            if trailing:
                output.append(trailing)

            break

        next_boundary = mapped[index + 1]

        between = text[
            boundary["char_end"]:
            next_boundary["char_start"]
        ]

        punctuation = re.sub(
            r"\s+",
            "",
            between,
        )

        if punctuation:
            output.append(punctuation)

        gap = max(
            0.0,
            next_boundary["start"]
            - boundary["end"],
        )

        output.append(
            choose_transition(
                punctuation_between=between,
                gap=gap,
                current_ipa=ipa_words[index],
                next_ipa=ipa_words[index + 1],
            )
        )

    return "".join(output).strip()


def choose_transition(
    punctuation_between: str,
    gap: float,
    current_ipa: str,
    next_ipa: str,
) -> str:
    if re.search(
        r"[.!?]",
        punctuation_between,
    ):
        return " || "

    if re.search(
        r"[,;:]",
        punctuation_between,
    ):
        return " | "

    if gap >= 0.38:
        return " || "

    if gap >= 0.18:
        return " | "

    if should_link(
        current_ipa,
        next_ipa,
    ):
        return "‿"

    return " "


def should_link(
    current_ipa: str,
    next_ipa: str,
) -> bool:
    final_segment = last_segment(current_ipa)
    first_next = first_segment(next_ipa)

    if (
        final_segment is None
        or first_next is None
    ):
        return False

    current_is_vowel = (
        final_segment in IPA_VOWELS
    )

    next_is_vowel = (
        first_next in IPA_VOWELS
    )

    return (
        (not current_is_vowel and next_is_vowel)
        or
        (current_is_vowel and next_is_vowel)
    )


def first_segment(ipa: str):
    cleaned = clean_for_segment_detection(ipa)

    if not cleaned:
        return None

    return cleaned[0]


def last_segment(ipa: str):
    cleaned = clean_for_segment_detection(ipa)

    if not cleaned:
        return None

    return cleaned[-1]


def clean_for_segment_detection(
    ipa: str,
) -> str:
    ignored = {
        "ˈ",
        "ˌ",
        "ː",
        "ˑ",
        " ",
        ".",
        "-",
        "͡",
        "‿",
    }

    return "".join(
        char
        for char in ipa
        if char not in ignored
    )


# =============================================================
# Chunks / thought groups
# =============================================================
CHUNK_STARTERS = {
    "after",
    "although",
    "because",
    "before",
    "but",
    "however",
    "if",
    "since",
    "so",
    "though",
    "unless",
    "when",
    "whenever",
    "whereas",
    "while",
    "which",
    "who",
}

SUBJECT_PRONOUNS = {
    "he",
    "i",
    "it",
    "she",
    "they",
    "we",
    "you",
}

SOFT_CHUNK_STARTERS = {
    "a",
    "an",
    "at",
    "by",
    "for",
    "from",
    "in",
    "into",
    "my",
    "on",
    "our",
    "the",
    "their",
    "these",
    "this",
    "those",
    "through",
    "under",
    "with",
    "without",
    "your",
}


def build_chunk_guide(
    text: str,
    boundaries: list,
) -> str:
    """
    Build compact thought-group guidance.

    Each sentence stays on one line and groups are separated with `/`.
    Boundaries are deliberately conservative: punctuation and actual TTS
    pauses are preferred, then clause starters, and finally a soft split
    is added only when a group becomes too long.
    """
    sentence_spans = split_sentence_spans(text)

    if not sentence_spans:
        return "No sentences detected."

    boundary_by_start = {
        boundary["char_start"]: boundary
        for boundary in boundaries
        if boundary.get("char_start") is not None
    }

    output = []

    for sentence_start, sentence_end, sentence in sentence_spans:
        chunked = chunk_sentence(
            sentence=sentence,
            sentence_start=sentence_start,
            boundary_by_start=boundary_by_start,
        )

        output.append(chunked)

    return "\n".join(output)


def split_sentence_spans(
    text: str,
) -> list[tuple[int, int, str]]:
    spans = []

    for match in re.finditer(
        r"[^.!?]+(?:[.!?]+|$)",
        text,
    ):
        raw = match.group()

        if not raw.strip():
            continue

        leading = len(raw) - len(raw.lstrip())
        trailing = len(raw) - len(raw.rstrip())

        start = match.start() + leading
        end = match.end() - trailing

        spans.append((
            start,
            end,
            text[start:end],
        ))

    return spans


def chunk_sentence(
    sentence: str,
    sentence_start: int,
    boundary_by_start: dict,
) -> str:
    word_matches = list(
        WORD_PATTERN.finditer(sentence)
    )

    if len(word_matches) <= 3:
        return sentence.strip()

    hard_breaks = set()

    for index in range(1, len(word_matches)):
        previous = word_matches[index - 1]
        current = word_matches[index]

        between = sentence[
            previous.end():current.start()
        ]

        current_word = (
            current.group()
            .lower()
            .replace("’", "'")
        )

        # Written phrase/clause boundary.
        if re.search(r"[,;:]", between):
            hard_breaks.add(index)
            continue

        # Common clause and discourse starters.
        if (
            current_word in CHUNK_STARTERS
            and index >= 2
        ):
            hard_breaks.add(index)
            continue

        # A noticeable pause in the synthesized reference audio.
        previous_global_start = (
            sentence_start + previous.start()
        )
        current_global_start = (
            sentence_start + current.start()
        )

        previous_boundary = boundary_by_start.get(
            previous_global_start
        )
        current_boundary = boundary_by_start.get(
            current_global_start
        )

        if (
            previous_boundary is not None
            and current_boundary is not None
        ):
            gap = max(
                0.0,
                current_boundary["start"]
                - previous_boundary["end"],
            )

            if gap >= 0.20:
                hard_breaks.add(index)

    break_indexes = refine_chunk_breaks(
        word_matches=word_matches,
        hard_breaks=hard_breaks,
    )

    if not break_indexes:
        return sentence.strip()

    parts = []
    previous_char = 0

    for word_index in break_indexes:
        break_char = word_matches[
            word_index
        ].start()

        part = sentence[
            previous_char:break_char
        ].strip()

        if part:
            parts.append(part)

        previous_char = break_char

    final_part = sentence[
        previous_char:
    ].strip()

    if final_part:
        parts.append(final_part)

    return " / ".join(parts)


def refine_chunk_breaks(
    word_matches: list,
    hard_breaks: set[int],
) -> list[int]:
    """
    Keep natural boundaries, then split only oversized groups.

    Target groups are roughly 2-6 words. A soft boundary is preferably
    placed before a determiner/preposition so noun/prepositional phrases
    stay together, e.g. `I need to review / the pull request`.
    """
    total_words = len(word_matches)

    boundaries = sorted(
        index
        for index in hard_breaks
        if 2 <= index <= total_words - 2
    )

    segment_edges = [
        0,
        *boundaries,
        total_words,
    ]

    extra_breaks = []

    for start, end in zip(
        segment_edges,
        segment_edges[1:],
    ):
        extra_breaks.extend(
            split_long_chunk(
                word_matches=word_matches,
                start=start,
                end=end,
            )
        )

    return sorted(
        set(boundaries + extra_breaks)
    )


def split_long_chunk(
    word_matches: list,
    start: int,
    end: int,
) -> list[int]:
    breaks = []
    current_start = start

    while end - current_start > 6:
        minimum = current_start + 2
        maximum = min(
            end - 2,
            current_start + 6,
        )
        preferred = min(
            current_start + 4,
            maximum,
        )

        candidates = []

        for index in range(
            minimum,
            maximum + 1,
        ):
            word = (
                word_matches[index]
                .group()
                .lower()
                .replace("’", "'")
            )

            base_word = word.split("'", 1)[0]

            if (
                word in SOFT_CHUNK_STARTERS
                or base_word in SUBJECT_PRONOUNS
            ):
                candidates.append(index)

        if candidates:
            split_at = min(
                candidates,
                key=lambda index: (
                    abs(index - preferred),
                    index,
                ),
            )
        else:
            split_at = preferred

        breaks.append(split_at)
        current_start = split_at

    return breaks


def build_weak_forms(
    text: str,
    accent: str,
) -> str:
    words = [
        match.group()
        .lower()
        .replace("’", "'")
        for match in WORD_PATTERN.finditer(text)
    ]

    weak_forms = dict(
        WEAK_FORMS_COMMON
    )

    if accent == "American":
        weak_forms.update({
            "for": "/fɚ/",
            "were": "/wɚ/",
            "your": "/jɚ/",
        })

    else:
        weak_forms.update({
            "for": "/fə/",
            "were": "/wə/",
            "your": "/jə/",
        })

    output = []
    already_added = set()

    for word in words:
        if (
            word not in weak_forms
            or word in already_added
        ):
            continue

        output.append(
            f"{word} → {weak_forms[word]}"
        )

        already_added.add(word)

    if not output:
        return (
            "No common weak-form candidates "
            "were detected."
        )

    return "\n".join(output)


def build_stress_guide(
    text: str,
    language: str,
) -> str:
    words = [
        match.group()
        for match in WORD_PATTERN.finditer(text)
    ]

    if not words:
        return "No words detected."

    ipa_words = phonemize_words(
        words,
        language,
    )

    output = []
    seen = set()

    for word, ipa in zip(
        words,
        ipa_words,
    ):
        key = word.lower()

        if key in seen:
            continue

        if (
            "ˈ" not in ipa
            and "ˌ" not in ipa
        ):
            continue

        output.append(
            f"{word} → /{ipa}/"
        )

        seen.add(key)

    if not output:
        return (
            "No explicit lexical stress marks "
            "were returned for these words."
        )

    return "\n".join(output)


def build_intonation_guide(
    text: str,
) -> str:
    sentences = split_sentences(text)

    if not sentences:
        return "No sentence detected."

    output = []

    for sentence in sentences:
        arrow = classify_intonation(
            sentence
        )

        output.append(
            f"{arrow} {sentence}"
        )

        if "," in sentence:
            output.append(
                "   → keep the voice open across "
                "non-final comma phrases"
            )

    return "\n".join(output)


def classify_intonation(
    sentence: str,
) -> str:
    words = [
        match.group().lower()
        for match in WORD_PATTERN.finditer(
            sentence
        )
    ]

    if not words:
        return "→"

    first_word = words[0]

    if sentence.rstrip().endswith("?"):
        if first_word in WH_WORDS:
            return "↘"

        if first_word in YES_NO_AUXILIARIES:
            return "↗"

        return "↗"

    return "↘"
