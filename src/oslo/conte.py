"""Conte (storyboard) Markdown parser."""

import re

from oslo.text_processor import IMAGE_STYLE_PREFIX, Scene, generate_image_prompt

_SCENE_HEADER_PATTERN = re.compile(r"^##\s*(?:シーン|Scene)\b.*$", re.MULTILINE)
_VISUAL_PATTERN = re.compile(r"\*\*映像\*\*\s*[:：]\s*(.+?)(?=\n\*\*|$)", re.DOTALL)
_NARRATION_PATTERN = re.compile(
    r"\*\*ナレーション\*\*\s*[:：]\s*(.+?)(?=\n\*\*|$)",
    re.DOTALL,
)
_TITLE_PATTERN = re.compile(r"^#\s+(.+)$", re.MULTILINE)
_NO_TEXT_SUFFIX = "Do not include any text, words, or letters in the image."


def parse_conte_title(text: str) -> str | None:
    """Extract the title (first H1 heading) from conte markdown."""
    match = _TITLE_PATTERN.search(text)
    return match.group(1).strip() if match else None


def is_conte_format(text: str) -> bool:
    """Return True when the input has at least one conte scene header."""
    return bool(_SCENE_HEADER_PATTERN.search(text))


def parse_conte(text: str) -> list[Scene]:
    """Parse conte markdown and return a list of Scene objects."""
    matches = list(_SCENE_HEADER_PATTERN.finditer(text))
    if not matches:
        raise ValueError("No scenes found in conte markdown")

    scenes: list[Scene] = []
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[start:end].strip()

        narration_text = _extract_required_narration(block, i + 1)
        visual_text = _extract_visual(block)

        if visual_text:
            image_prompt = f"{IMAGE_STYLE_PREFIX}{visual_text} {_NO_TEXT_SUFFIX}"
        else:
            image_prompt = generate_image_prompt(narration_text)

        scenes.append(
            Scene(
                index=i,
                narration_text=narration_text,
                image_prompt=image_prompt,
            )
        )

    if not scenes:
        raise ValueError("No scenes found in conte markdown")

    return scenes


def _extract_visual(block: str) -> str | None:
    """Extract visual description from a single scene block."""
    match = _VISUAL_PATTERN.search(block)
    if not match:
        return None
    visual_text = match.group(1).strip()
    return visual_text or None


def _extract_required_narration(block: str, scene_number: int) -> str:
    """Extract narration from a single scene block or raise ValueError."""
    match = _NARRATION_PATTERN.search(block)
    if not match or not match.group(1).strip():
        raise ValueError(f"Narration not found in scene {scene_number}")
    return match.group(1).strip()
