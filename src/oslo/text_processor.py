"""Text parsing, scene splitting, and image prompt generation."""

import re
from dataclasses import dataclass, field

# CJK character ranges for detection
_CJK_RANGES = (
    "\u3000-\u303f"  # CJK punctuation
    "\u3040-\u309f"  # Hiragana
    "\u30a0-\u30ff"  # Katakana
    "\u4e00-\u9fff"  # CJK Unified Ideographs
    "\uf900-\ufaff"  # CJK Compatibility Ideographs
)
_CJK_PATTERN = re.compile(f"[{_CJK_RANGES}]")

# Speaking rates
DEFAULT_WPM = 150.0  # English words per minute
DEFAULT_CPM = 350.0  # Japanese characters per minute

# Style prefix for consistent image generation across scenes
IMAGE_STYLE_PREFIX = (
    "Cinematic vertical composition, vibrant colors, high detail, dramatic lighting. "
)

# Minimum characters for a segment to stand alone (Japanese)
MIN_SEGMENT_CHARS = 30
# Minimum words for a segment to stand alone (English)
MIN_SEGMENT_WORDS = 10
# Characters per subtitle chunk for Japanese
JP_CHARS_PER_SUBTITLE = 12


def _is_cjk_dominant(text: str) -> bool:
    """Check if text is primarily CJK (Japanese/Chinese/Korean)."""
    cjk_count = len(_CJK_PATTERN.findall(text))
    return cjk_count > len(text) * 0.2


def _segment_length(text: str) -> int:
    """Return a language-aware length metric for a text segment."""
    if _is_cjk_dominant(text):
        return len(text.strip())
    return len(text.split())


def _min_segment_size(text: str) -> int:
    """Return the minimum segment size threshold based on language."""
    if _is_cjk_dominant(text):
        return MIN_SEGMENT_CHARS
    return MIN_SEGMENT_WORDS


def _split_for_subtitles(text: str) -> list[str]:
    """Split text into subtitle-sized chunks, handling both CJK and English."""
    if _is_cjk_dominant(text):
        clean = re.sub(r"\s+", "", text)
        # Split on punctuation boundaries first (keeps punctuation with preceding text)
        parts = re.split(r"(?<=[。、！？，])", clean)
        parts = [p for p in parts if p]
        # Re-split chunks that are too long at natural break points
        max_chars = 20
        merge_max = 22
        chunks = []
        for part in parts:
            while len(part) > max_chars:
                pos = _find_jp_break(part, max_chars)
                chunks.append(part[:pos])
                part = part[pos:]
            if part:
                chunks.append(part)
        # Merge very short chunks (3 chars or less) into previous
        # Cap at 2 display lines (~22 chars) to prevent orphaned fragments
        if len(chunks) > 1:
            merged = [chunks[0]]
            for c in chunks[1:]:
                if len(c) <= 3 and len(merged[-1]) + len(c) <= merge_max:
                    merged[-1] += c
                else:
                    merged.append(c)
            chunks = merged
        return chunks
    return text.split()


# Characters that indicate natural break points in Japanese.
# Split AFTER these characters (particles, verb endings, etc.)
_JP_BREAK_CHARS = set("はがをにでともへのてただるいす")

# Never break immediately before these characters
_NO_BREAK_BEFORE = set("ーッャュョァィゥェォ」）")

# Character pairs (prev, next) that should not be split across chunks
_NO_BREAK_PAIRS = {("す", "る"), ("い", "う"), ("で", "し")}


def _find_jp_break(text: str, max_pos: int) -> int:
    """Find the best position to break Japanese text near max_pos.

    Searches backward from max_pos for a particle or verb ending,
    falling back to max_pos if no good break point is found.
    """
    # Search backward from max_pos to ~40% of max_pos
    min_search = max(max_pos * 2 // 5, 4)
    for i in range(max_pos, min_search, -1):
        if text[i - 1] in _JP_BREAK_CHARS:
            # Don't break if next char is a prolonged sound, small kana, or closing bracket
            if i < len(text) and text[i] in _NO_BREAK_BEFORE:
                continue
            # Don't break between tightly-bound character pairs
            if i < len(text) and (text[i - 1], text[i]) in _NO_BREAK_PAIRS:
                continue
            return i
    return max_pos


@dataclass
class Scene:
    """A single scene in the video."""

    index: int
    narration_text: str
    image_prompt: str
    tts_text: str = ""
    words: list[str] = field(default_factory=list)
    stat_overlay: str | None = None
    library_image: str | None = None

    def __post_init__(self):
        if not self.tts_text:
            self.tts_text = self.narration_text
        if not self.words:
            self.words = _split_for_subtitles(self.narration_text)


def estimate_duration(text: str) -> float:
    """Estimate speaking duration in seconds based on text content."""
    if _is_cjk_dominant(text):
        char_count = len(re.sub(r"\s+", "", text))
        return (char_count / DEFAULT_CPM) * 60.0
    word_count = len(text.split())
    return (word_count / DEFAULT_WPM) * 60.0


def truncate_to_duration(text: str, max_duration: float) -> str:
    """Truncate text to fit within max_duration.

    Truncates at sentence boundary nearest to the limit.
    """
    if estimate_duration(text) <= max_duration:
        return text

    if _is_cjk_dominant(text):
        max_chars = int((max_duration / 60.0) * DEFAULT_CPM)
        truncated = text[:max_chars]
    else:
        max_words = int((max_duration / 60.0) * DEFAULT_WPM)
        words = text.split()
        truncated = " ".join(words[:max_words])

    # Find the last sentence-ending punctuation
    last_period = max(
        truncated.rfind("。"), truncated.rfind("."),
        truncated.rfind("！"), truncated.rfind("？"),
    )
    if last_period > len(truncated) // 2:
        return truncated[: last_period + 1]
    return truncated


def _split_into_paragraphs(text: str) -> list[str]:
    """Split text into paragraphs (double newline or paragraph-like boundaries)."""
    paragraphs = re.split(r"\n\s*\n", text.strip())
    return [p.strip() for p in paragraphs if p.strip()]


def _split_into_sentences(text: str) -> list[str]:
    """Split text into sentences, handling both Japanese and English punctuation."""
    parts = re.split(r"(?<=[。．.！!？?\n])\s*", text.strip())
    return [s.strip() for s in parts if s.strip()]


def _merge_short_segments(segments: list[str]) -> list[str]:
    """Merge segments that are too short into neighboring ones."""
    if not segments:
        return segments

    # Determine threshold from first segment's language
    full_text = "".join(segments)
    min_size = _min_segment_size(full_text)

    merged = [segments[0]]
    for seg in segments[1:]:
        if _segment_length(merged[-1]) < min_size:
            merged[-1] = merged[-1] + "\n" + seg
        else:
            merged.append(seg)

    # If the last segment is too short, merge with previous
    if len(merged) > 1 and _segment_length(merged[-1]) < min_size:
        merged[-2] = merged[-2] + "\n" + merged[-1]
        merged.pop()

    return merged


def generate_image_prompt(
    narration_text: str, image_style_prefix: str | None = None
) -> str:
    """Generate a visual scene description for image generation.

    Avoids including narration text directly to prevent
    the model from rendering garbled text in the image.
    """
    prefix = image_style_prefix or IMAGE_STYLE_PREFIX
    content = narration_text[:300]
    return (
        f"{prefix}Do not include any text, words, or letters in the image. "
        f"Visual scene inspired by: {content}"
    )


def split_into_scenes(
    text: str, max_duration: float = 90.0, image_style_prefix: str | None = None
) -> list[Scene]:
    """Split input text into scenes suitable for video generation.

    Strategy:
    1. Clean and normalize the text
    2. Truncate if text exceeds max_duration
    3. Split into paragraphs, then sentences if needed
    4. Target 3-6 scenes of roughly equal length
    5. Generate an image prompt for each scene
    """
    text = text.strip()
    if not text:
        raise ValueError("Input text is empty")

    # Truncate to fit duration
    text = truncate_to_duration(text, max_duration)

    # Try paragraph-based splitting first
    segments = _split_into_paragraphs(text)

    # If too few paragraphs, split into sentences
    if len(segments) < 3:
        all_sentences = []
        for para in segments:
            all_sentences.extend(_split_into_sentences(para))
        segments = all_sentences

    # If still too few, just use what we have
    if len(segments) < 2:
        segments = [text]

    # If too many segments, merge to target 3-6 scenes
    target_scenes = min(6, max(3, len(segments)))
    if len(segments) > target_scenes:
        group_size = len(segments) / target_scenes
        merged = []
        for i in range(target_scenes):
            start = int(i * group_size)
            end = int((i + 1) * group_size)
            merged.append("\n".join(segments[start:end]))
        segments = merged

    # Merge very short segments
    segments = _merge_short_segments(segments)

    # Create Scene objects
    scenes = []
    for i, segment in enumerate(segments):
        scenes.append(
            Scene(
                index=i,
                narration_text=segment,
                image_prompt=generate_image_prompt(segment, image_style_prefix),
            )
        )

    return scenes
