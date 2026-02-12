"""Configuration loading and validation."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from dotenv import load_dotenv

if TYPE_CHECKING:
    from oslo.profile import GenerationDefaults


@dataclass(frozen=True)
class VideoConfig:
    width: int = 1080
    height: int = 1920
    fps: int = 24
    min_duration: float = 30.0
    max_duration: float = 90.0


@dataclass(frozen=True)
class TTSConfig:
    model: str = "gpt-4o-mini-tts"
    voice: str = "nova"
    speed: float = 1.0
    output_format: str = "mp3"


@dataclass(frozen=True)
class ImageGenConfig:
    model: str = "gpt-image-1"
    size: str = "1024x1536"
    quality: str = "medium"


DEFAULT_IMAGE_STYLE_PREFIX = (
    "Cinematic vertical composition, vibrant colors, high detail, dramatic lighting. "
)


@dataclass(frozen=True)
class AppConfig:
    openai_api_key: str
    video: VideoConfig = field(default_factory=VideoConfig)
    tts: TTSConfig = field(default_factory=TTSConfig)
    image_gen: ImageGenConfig = field(default_factory=ImageGenConfig)
    image_style_prefix: str = DEFAULT_IMAGE_STYLE_PREFIX


def load_config(
    *,
    voice: str | None = None,
    speed: float | None = None,
    max_duration: float | None = None,
    image_quality: str | None = None,
    profile_defaults: GenerationDefaults | None = None,
) -> AppConfig:
    """Load configuration from environment variables and apply CLI/profile overrides.

    Priority: CLI flags > profile defaults > code defaults.
    """
    load_dotenv()

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is required")

    def _resolve(cli_val: object, profile_attr: str) -> object:
        if cli_val is not None:
            return cli_val
        if profile_defaults is not None:
            return getattr(profile_defaults, profile_attr)
        return None

    resolved_voice = _resolve(voice, "voice")
    resolved_speed = _resolve(speed, "speed")
    resolved_max_duration = _resolve(max_duration, "max_duration")
    resolved_image_quality = _resolve(image_quality, "image_quality")
    resolved_style = _resolve(None, "image_style_prefix")

    tts_kwargs: dict = {}
    if resolved_voice is not None:
        tts_kwargs["voice"] = resolved_voice
    if resolved_speed is not None:
        tts_kwargs["speed"] = resolved_speed

    video_kwargs: dict = {}
    if resolved_max_duration is not None:
        video_kwargs["max_duration"] = resolved_max_duration

    image_kwargs: dict = {}
    if resolved_image_quality is not None:
        image_kwargs["quality"] = resolved_image_quality

    style_kwargs: dict = {}
    if resolved_style is not None:
        style_kwargs["image_style_prefix"] = resolved_style

    return AppConfig(
        openai_api_key=api_key,
        video=VideoConfig(**video_kwargs),
        tts=TTSConfig(**tts_kwargs),
        image_gen=ImageGenConfig(**image_kwargs),
        **style_kwargs,
    )
