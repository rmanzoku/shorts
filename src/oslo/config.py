"""Configuration loading and validation."""

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv


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


@dataclass(frozen=True)
class AppConfig:
    openai_api_key: str
    video: VideoConfig = field(default_factory=VideoConfig)
    tts: TTSConfig = field(default_factory=TTSConfig)
    image_gen: ImageGenConfig = field(default_factory=ImageGenConfig)


def load_config(
    *,
    voice: str | None = None,
    speed: float | None = None,
    max_duration: float | None = None,
    image_quality: str | None = None,
) -> AppConfig:
    """Load configuration from environment variables and apply CLI overrides."""
    load_dotenv()

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is required")

    tts_kwargs: dict = {}
    if voice is not None:
        tts_kwargs["voice"] = voice
    if speed is not None:
        tts_kwargs["speed"] = speed

    video_kwargs: dict = {}
    if max_duration is not None:
        video_kwargs["max_duration"] = max_duration

    image_kwargs: dict = {}
    if image_quality is not None:
        image_kwargs["quality"] = image_quality

    return AppConfig(
        openai_api_key=api_key,
        video=VideoConfig(**video_kwargs),
        tts=TTSConfig(**tts_kwargs),
        image_gen=ImageGenConfig(**image_kwargs),
    )
