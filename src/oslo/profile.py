"""SNS profile management: loading, saving, listing, validation."""

import os
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import yaml
from dotenv import load_dotenv


class Platform(str, Enum):
    """Supported SNS platforms."""

    TIKTOK = "tiktok"
    YOUTUBE = "youtube"
    INSTAGRAM = "instagram"


class TikTokPrivacyLevel(str, Enum):
    """TikTok Content Posting API privacy levels."""

    PUBLIC_TO_EVERYONE = "PUBLIC_TO_EVERYONE"
    MUTUAL_FOLLOW_FRIENDS = "MUTUAL_FOLLOW_FRIENDS"
    FOLLOWER_OF_CREATOR = "FOLLOWER_OF_CREATOR"
    SELF_ONLY = "SELF_ONLY"


PROFILE_NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
PROFILES_DIR_NAME = "profiles"


@dataclass(frozen=True)
class TikTokDefaults:
    """Default posting settings for TikTok."""

    privacy_level: str = TikTokPrivacyLevel.SELF_ONLY.value
    disable_duet: bool = False
    disable_stitch: bool = False
    disable_comment: bool = False
    is_aigc: bool = True
    brand_content_toggle: bool = False
    hashtags: tuple[str, ...] = ()


@dataclass(frozen=True)
class GenerationDefaults:
    """Video generation defaults for a profile. None means 'not set'."""

    voice: str | None = None
    speed: float | None = None
    image_quality: str | None = None
    image_style_prefix: str | None = None
    image_provider: str | None = None
    max_duration: float | None = None


@dataclass(frozen=True)
class ContentGuidelines:
    """Editorial guidelines for conte creation (AI agent reference)."""

    tone: str = ""
    target_audience: str = ""
    guidelines: tuple[str, ...] = ()


@dataclass(frozen=True)
class CredentialConfig:
    """Credential reference configuration."""

    env_prefix: str
    required_vars: tuple[str, ...] = ("CLIENT_KEY", "CLIENT_SECRET")


@dataclass(frozen=True)
class Profile:
    """An SNS account profile."""

    name: str
    platform: str
    display_name: str
    description: str = ""
    language: str = "ja"
    defaults: TikTokDefaults | dict = field(default_factory=dict)
    credentials: CredentialConfig = field(
        default_factory=lambda: CredentialConfig(env_prefix="")
    )
    generation: GenerationDefaults = field(default_factory=GenerationDefaults)
    content: ContentGuidelines = field(default_factory=ContentGuidelines)


def _get_profiles_dir() -> Path:
    """Return the profiles directory relative to project root."""
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "pyproject.toml").exists():
            return current / PROFILES_DIR_NAME
        current = current.parent
    raise FileNotFoundError("Could not find project root (no pyproject.toml found)")


def validate_profile_name(name: str) -> None:
    """Validate profile name is a valid slug (lowercase alphanumeric with hyphens)."""
    if not PROFILE_NAME_PATTERN.match(name):
        raise ValueError(
            f"Invalid profile name '{name}'. "
            "Must be lowercase alphanumeric with hyphens (e.g., 'tiktok-politics')"
        )


def _parse_defaults(platform: str, defaults_dict: dict) -> TikTokDefaults | dict:
    """Parse platform-specific defaults from a raw dict."""
    if platform == Platform.TIKTOK.value:
        return TikTokDefaults(
            privacy_level=defaults_dict.get(
                "privacy_level", TikTokPrivacyLevel.SELF_ONLY.value
            ),
            disable_duet=defaults_dict.get("disable_duet", False),
            disable_stitch=defaults_dict.get("disable_stitch", False),
            disable_comment=defaults_dict.get("disable_comment", False),
            is_aigc=defaults_dict.get("is_aigc", True),
            brand_content_toggle=defaults_dict.get("brand_content_toggle", False),
            hashtags=tuple(defaults_dict.get("hashtags", [])),
        )
    return defaults_dict


def load_profile(name: str, profiles_dir: Path | None = None) -> Profile:
    """Load a profile from a YAML file by name."""
    validate_profile_name(name)
    directory = profiles_dir or _get_profiles_dir()
    path = directory / f"{name}.yml"

    if not path.exists():
        raise FileNotFoundError(f"Profile not found: {path}")

    data = yaml.safe_load(path.read_text(encoding="utf-8"))

    if data.get("name") != name:
        raise ValueError(
            f"Profile name mismatch: filename is '{name}' "
            f"but YAML contains '{data.get('name')}'"
        )

    cred_data = data.get("credentials", {})
    credentials = CredentialConfig(
        env_prefix=cred_data.get("env_prefix", name.upper().replace("-", "_")),
        required_vars=tuple(
            cred_data.get("required_vars", ["CLIENT_KEY", "CLIENT_SECRET"])
        ),
    )

    defaults = _parse_defaults(
        data.get("platform", ""),
        data.get("defaults", {}),
    )

    gen_data = data.get("generation", {})
    generation = GenerationDefaults(
        voice=gen_data.get("voice"),
        speed=gen_data.get("speed"),
        image_quality=gen_data.get("image_quality"),
        image_style_prefix=gen_data.get("image_style_prefix"),
        image_provider=gen_data.get("image_provider"),
        max_duration=gen_data.get("max_duration"),
    )

    content_data = data.get("content", {})
    content = ContentGuidelines(
        tone=content_data.get("tone", ""),
        target_audience=content_data.get("target_audience", ""),
        guidelines=tuple(content_data.get("guidelines", [])),
    )

    return Profile(
        name=data["name"],
        platform=data["platform"],
        display_name=data.get("display_name", name),
        description=data.get("description", ""),
        language=data.get("language", "ja"),
        defaults=defaults,
        credentials=credentials,
        generation=generation,
        content=content,
    )


def save_profile(profile: Profile, profiles_dir: Path | None = None) -> Path:
    """Save a profile to a YAML file."""
    validate_profile_name(profile.name)
    directory = profiles_dir or _get_profiles_dir()
    directory.mkdir(parents=True, exist_ok=True)

    data: dict = {
        "name": profile.name,
        "platform": profile.platform,
        "display_name": profile.display_name,
        "description": profile.description,
        "language": profile.language,
    }

    if isinstance(profile.defaults, TikTokDefaults):
        data["defaults"] = {
            "privacy_level": profile.defaults.privacy_level,
            "disable_duet": profile.defaults.disable_duet,
            "disable_stitch": profile.defaults.disable_stitch,
            "disable_comment": profile.defaults.disable_comment,
            "is_aigc": profile.defaults.is_aigc,
            "brand_content_toggle": profile.defaults.brand_content_toggle,
            "hashtags": list(profile.defaults.hashtags),
        }
    elif isinstance(profile.defaults, dict):
        data["defaults"] = profile.defaults

    # Serialize generation defaults (only non-None values)
    gen_dict = {}
    for fld in (
        "voice", "speed", "image_quality", "image_style_prefix", "image_provider",
        "max_duration",
    ):
        val = getattr(profile.generation, fld)
        if val is not None:
            gen_dict[fld] = val
    if gen_dict:
        data["generation"] = gen_dict

    # Serialize content guidelines (only non-empty values)
    content_dict: dict = {}
    if profile.content.tone:
        content_dict["tone"] = profile.content.tone
    if profile.content.target_audience:
        content_dict["target_audience"] = profile.content.target_audience
    if profile.content.guidelines:
        content_dict["guidelines"] = list(profile.content.guidelines)
    if content_dict:
        data["content"] = content_dict

    data["credentials"] = {
        "env_prefix": profile.credentials.env_prefix,
        "required_vars": list(profile.credentials.required_vars),
    }

    path = directory / f"{profile.name}.yml"
    path.write_text(
        yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    return path


def list_profiles(profiles_dir: Path | None = None) -> list[str]:
    """List all profile names (stems of .yml files in profiles/)."""
    directory = profiles_dir or _get_profiles_dir()
    if not directory.exists():
        return []
    return sorted(p.stem for p in directory.glob("*.yml"))


def validate_credentials(profile: Profile) -> dict[str, bool]:
    """Check which required env vars are set for the profile."""
    load_dotenv()
    result = {}
    for var_suffix in profile.credentials.required_vars:
        full_var = f"{profile.credentials.env_prefix}_{var_suffix}"
        result[full_var] = bool(os.environ.get(full_var))
    return result
