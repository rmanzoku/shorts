"""Conte (storyboard) Markdown parser."""

import re
import warnings

from oslo.text_processor import IMAGE_STYLE_PREFIX, Scene, generate_image_prompt

_SCENE_HEADER_PATTERN = re.compile(r"^##\s*(?:シーン|Scene)\b.*$", re.MULTILINE)
_ANY_H2_PATTERN = re.compile(r"^##\s", re.MULTILINE)
_VISUAL_PATTERN = re.compile(r"\*\*映像\*\*\s*[:：]\s*(.+?)(?=\n\*\*|$)", re.DOTALL)
_NARRATION_PATTERN = re.compile(
    r"\*\*ナレーション\*\*\s*[:：]\s*(.+?)(?=\n\*\*|$)",
    re.DOTALL,
)
_STAT_PATTERN = re.compile(
    r"\*\*数字\*\*\s*[:：]\s*(.+?)(?=\n\*\*|$)",
    re.DOTALL,
)
_LIBRARY_IMAGE_PATTERN = re.compile(
    r"\*\*画像\*\*\s*[:：]\s*(.+?)(?=\n\*\*|$)",
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


def parse_conte(text: str, image_style_prefix: str | None = None) -> list[Scene]:
    """Parse conte markdown and return a list of Scene objects."""
    style_prefix = image_style_prefix or IMAGE_STYLE_PREFIX
    matches = list(_SCENE_HEADER_PATTERN.finditer(text))
    if not matches:
        raise ValueError("No scenes found in conte markdown")

    # Use all ## headers as block boundaries (not just scene headers)
    all_h2_starts = [m.start() for m in _ANY_H2_PATTERN.finditer(text)]

    scenes: list[Scene] = []
    for i, match in enumerate(matches):
        start = match.end()
        # Find the next ## header of any kind after this scene header
        end = len(text)
        for h2_start in all_h2_starts:
            if h2_start > match.start():
                end = h2_start
                break
        block = text[start:end].strip()

        narration_text = _extract_required_narration(block, i + 1)
        visual_text = _extract_visual(block)
        stat_overlay = _extract_stat_overlay(block)
        library_image = _extract_library_image(block)

        if stat_overlay is None:
            warnings.warn(
                f"**数字** field missing in scene {i + 1}",
                stacklevel=2,
            )

        if library_image and visual_text:
            warnings.warn(
                f"Scene {i + 1}: **画像** overrides **映像** (AI generation skipped)",
                stacklevel=2,
            )

        if visual_text:
            image_prompt = f"{style_prefix}{visual_text} {_NO_TEXT_SUFFIX}"
        else:
            image_prompt = generate_image_prompt(narration_text, image_style_prefix)

        scenes.append(
            Scene(
                index=i,
                narration_text=narration_text,
                image_prompt=image_prompt,
                stat_overlay=stat_overlay,
                library_image=library_image,
            )
        )

    if not scenes:
        raise ValueError("No scenes found in conte markdown")

    return scenes


def _extract_stat_overlay(block: str) -> str | None:
    """Extract stat overlay text from a single scene block."""
    match = _STAT_PATTERN.search(block)
    if not match:
        return None
    stat_text = match.group(1).strip()
    return stat_text or None


def _extract_visual(block: str) -> str | None:
    """Extract visual description from a single scene block."""
    match = _VISUAL_PATTERN.search(block)
    if not match:
        return None
    visual_text = match.group(1).strip()
    return visual_text or None


def _extract_library_image(block: str) -> str | None:
    """Extract library image slug from a scene block."""
    match = _LIBRARY_IMAGE_PATTERN.search(block)
    if not match:
        return None
    slug = match.group(1).strip()
    return slug or None


def _extract_required_narration(block: str, scene_number: int) -> str:
    """Extract narration from a single scene block or raise ValueError."""
    match = _NARRATION_PATTERN.search(block)
    if not match or not match.group(1).strip():
        raise ValueError(f"Narration not found in scene {scene_number}")
    return match.group(1).strip()
