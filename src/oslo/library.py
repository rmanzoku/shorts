"""Image library: storage, metadata, and retrieval."""

import base64
import json
import re
import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml
from openai import OpenAI

from oslo.utils import retry_on_rate_limit

LIBRARY_DIR_NAME = "images"
SUPPORTED_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")
_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:[_-][a-z0-9]+)*$")

_ANALYSIS_PROMPT = """\
この画像を分析し、以下のJSON形式で回答してください:
{"tags": ["タグ1", "タグ2", ...], "description": "画像の説明文"}

タグには以下を含めてください:
- 人物がいれば氏名（わかる場合）
- 所属組織・政党
- 表情・感情（怒り、笑顔、真剣、困惑、驚きなど）
- 場面（国会答弁、記者会見、街頭演説など）
- 場所（わかる場合）
- その他特徴的な要素

JSONのみを出力し、他のテキストは含めないでください。"""


@dataclass(frozen=True)
class ImageMeta:
    """Metadata for a library image."""

    slug: str
    path: Path
    tags: tuple[str, ...] = ()
    description: str = ""
    source: str = ""
    added: str = ""


def _get_library_dir() -> Path:
    """Return the images directory relative to project root."""
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "pyproject.toml").exists():
            return current / LIBRARY_DIR_NAME
        current = current.parent
    raise FileNotFoundError("Could not find project root (no pyproject.toml found)")


def validate_slug(slug: str) -> None:
    """Validate that a slug is safe and follows the naming convention."""
    if not _SLUG_PATTERN.match(slug):
        raise ValueError(
            f"Invalid slug '{slug}'. "
            "Must be lowercase alphanumeric with hyphens/underscores (e.g., '001_kokkai')"
        )


def resolve_image_path(slug: str, library_dir: Path | None = None) -> Path:
    """Resolve a slug to its image file path."""
    validate_slug(slug)
    directory = library_dir or _get_library_dir()
    for ext in SUPPORTED_EXTENSIONS:
        path = directory / f"{slug}{ext}"
        if path.exists():
            return path
    raise FileNotFoundError(
        f"Image not found for slug '{slug}' in {directory}"
    )


def load_image_meta(slug: str, library_dir: Path | None = None) -> ImageMeta:
    """Load metadata for a single image by slug."""
    directory = library_dir or _get_library_dir()
    image_path = resolve_image_path(slug, directory)
    yml_path = directory / f"{slug}.yml"

    if yml_path.exists():
        data = yaml.safe_load(yml_path.read_text(encoding="utf-8")) or {}
    else:
        data = {}

    return ImageMeta(
        slug=slug,
        path=image_path,
        tags=tuple(data.get("tags", [])),
        description=data.get("description", ""),
        source=str(data.get("source", "")),
        added=str(data.get("added", "")),
    )


def list_images(library_dir: Path | None = None) -> list[ImageMeta]:
    """List all images in the library with metadata."""
    directory = library_dir or _get_library_dir()
    if not directory.exists():
        return []

    slugs: set[str] = set()
    for ext in SUPPORTED_EXTENSIONS:
        for path in directory.glob(f"*{ext}"):
            slugs.add(path.stem)

    results = []
    for slug in sorted(slugs):
        results.append(load_image_meta(slug, directory))
    return results


def search_images(
    tags: list[str], library_dir: Path | None = None
) -> list[ImageMeta]:
    """Search images by tag (AND matching — all tags must be present)."""
    all_images = list_images(library_dir)
    tag_set = {t.lower() for t in tags}
    return [
        img
        for img in all_images
        if tag_set <= {t.lower() for t in img.tags}
    ]


def _next_slug_number(library_dir: Path) -> int:
    """Return the next available 3-digit number for auto-numbering."""
    max_num = 0
    for ext in SUPPORTED_EXTENSIONS:
        for path in library_dir.glob(f"*{ext}"):
            stem = path.stem
            if len(stem) >= 3 and stem[:3].isdigit():
                max_num = max(max_num, int(stem[:3]))
    return max_num + 1


def add_image(
    source_path: Path,
    *,
    slug: str | None = None,
    tags: tuple[str, ...] = (),
    description: str = "",
    source: str = "",
    library_dir: Path | None = None,
) -> ImageMeta:
    """Copy an image to the library and create its YAML sidecar."""
    directory = library_dir or _get_library_dir()
    directory.mkdir(parents=True, exist_ok=True)

    ext = source_path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported image format '{ext}'. "
            f"Supported: {', '.join(SUPPORTED_EXTENSIONS)}"
        )

    if slug is None:
        num = _next_slug_number(directory)
        # Sanitize filename to safe slug characters
        base = re.sub(r"[^a-z0-9-]", "-", source_path.stem.lower())
        base = re.sub(r"-+", "-", base).strip("-")
        if not base:
            base = "image"
        slug = f"{num:03d}_{base}"
    else:
        validate_slug(slug)

    dest_path = directory / f"{slug}{ext}"
    if dest_path.exists():
        raise FileExistsError(f"Image already exists: {dest_path}")

    shutil.copy2(source_path, dest_path)

    meta = ImageMeta(
        slug=slug,
        path=dest_path,
        tags=tags,
        description=description,
        source=source,
        added=date.today().isoformat(),
    )
    _save_meta(meta, directory)
    return meta


def _save_meta(meta: ImageMeta, library_dir: Path) -> Path:
    """Write metadata to a YAML sidecar file."""
    data = {
        "tags": list(meta.tags),
        "description": meta.description,
        "source": meta.source,
        "added": meta.added,
    }
    yml_path = library_dir / f"{meta.slug}.yml"
    yml_path.write_text(
        yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    return yml_path


@retry_on_rate_limit()
def analyze_image(api_key: str, image_path: Path) -> dict[str, object]:
    """Analyze an image with GPT-4o vision and return tags + description."""
    image_bytes = image_path.read_bytes()
    b64 = base64.b64encode(image_bytes).decode()

    suffix = image_path.suffix.lower()
    media_types = {
        ".png": "image/png", ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg", ".webp": "image/webp",
    }
    media_type = media_types.get(suffix, "image/png")

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{media_type};base64,{b64}"},
                    },
                    {"type": "text", "text": _ANALYSIS_PROMPT},
                ],
            }
        ],
        max_tokens=500,
    )

    content = response.choices[0].message.content
    if not content:
        return {"tags": [], "description": ""}

    raw = content.strip()
    # Extract JSON object: find first { and last }
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        raw = raw[start : end + 1]

    result = json.loads(raw)
    return {
        "tags": result.get("tags", []),
        "description": result.get("description", ""),
    }
