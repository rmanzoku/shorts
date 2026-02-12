"""Tests for profile module."""

import pytest

from oslo.profile import (
    ContentGuidelines,
    CredentialConfig,
    GenerationDefaults,
    Profile,
    TikTokDefaults,
    list_profiles,
    load_profile,
    save_profile,
    validate_credentials,
    validate_profile_name,
)

VALID_TIKTOK_YAML = """\
name: tiktok-politics
platform: tiktok
display_name: "政治解説チャンネル"
description: "政治解説ショート動画"
language: ja
defaults:
  privacy_level: PUBLIC_TO_EVERYONE
  disable_duet: false
  disable_stitch: false
  disable_comment: false
  is_aigc: true
  brand_content_toggle: false
  hashtags:
    - "#政治"
    - "#解説"
credentials:
  env_prefix: TIKTOK_POLITICS
  required_vars:
    - CLIENT_KEY
    - CLIENT_SECRET
"""

YAML_WITH_GENERATION = """\
name: tiktok-full
platform: tiktok
display_name: "Full Profile"
generation:
  voice: onyx
  speed: 0.95
  image_quality: high
  image_style_prefix: "Professional, serious tone. "
  max_duration: 60.0
content:
  tone: "です・ます調"
  target_audience: "政治に興味のある20-40代"
  guidelines:
    - "偏向表現の禁止"
    - "事実ベース"
credentials:
  env_prefix: TIKTOK_FULL
"""


class TestValidateProfileName:
    def test_valid_simple(self):
        validate_profile_name("tiktok-politics")

    def test_valid_multi_hyphen(self):
        validate_profile_name("youtube-shorts-cooking")

    def test_valid_single_word(self):
        validate_profile_name("test")

    def test_invalid_uppercase(self):
        with pytest.raises(ValueError, match="Invalid profile name"):
            validate_profile_name("TikTok-Politics")

    def test_invalid_underscore(self):
        with pytest.raises(ValueError, match="Invalid profile name"):
            validate_profile_name("tiktok_politics")

    def test_invalid_spaces(self):
        with pytest.raises(ValueError, match="Invalid profile name"):
            validate_profile_name("tiktok politics")

    def test_invalid_empty(self):
        with pytest.raises(ValueError, match="Invalid profile name"):
            validate_profile_name("")


class TestLoadProfile:
    def test_load_valid_tiktok_profile(self, tmp_path):
        (tmp_path / "tiktok-politics.yml").write_text(VALID_TIKTOK_YAML)
        profile = load_profile("tiktok-politics", profiles_dir=tmp_path)

        assert profile.name == "tiktok-politics"
        assert profile.platform == "tiktok"
        assert profile.display_name == "政治解説チャンネル"
        assert profile.language == "ja"
        assert isinstance(profile.defaults, TikTokDefaults)
        assert profile.defaults.is_aigc is True
        assert profile.defaults.privacy_level == "PUBLIC_TO_EVERYONE"
        assert "#政治" in profile.defaults.hashtags
        assert "#解説" in profile.defaults.hashtags
        assert profile.credentials.env_prefix == "TIKTOK_POLITICS"

    def test_load_nonexistent_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="Profile not found"):
            load_profile("does-not-exist", profiles_dir=tmp_path)

    def test_load_name_mismatch_raises(self, tmp_path):
        yaml_content = VALID_TIKTOK_YAML.replace(
            "name: tiktok-politics", "name: wrong-name"
        )
        (tmp_path / "tiktok-politics.yml").write_text(yaml_content)
        with pytest.raises(ValueError, match="name mismatch"):
            load_profile("tiktok-politics", profiles_dir=tmp_path)

    def test_load_minimal_profile(self, tmp_path):
        minimal = "name: minimal\nplatform: tiktok\n"
        (tmp_path / "minimal.yml").write_text(minimal)
        profile = load_profile("minimal", profiles_dir=tmp_path)
        assert profile.name == "minimal"
        assert profile.platform == "tiktok"
        assert profile.display_name == "minimal"
        assert profile.description == ""
        assert isinstance(profile.defaults, TikTokDefaults)
        assert profile.defaults.privacy_level == "SELF_ONLY"
        assert profile.defaults.is_aigc is True

    def test_load_unknown_platform_returns_dict_defaults(self, tmp_path):
        content = "name: test\nplatform: unknown\ndefaults:\n  foo: bar\n"
        (tmp_path / "test.yml").write_text(content)
        profile = load_profile("test", profiles_dir=tmp_path)
        assert isinstance(profile.defaults, dict)
        assert profile.defaults["foo"] == "bar"

    def test_load_with_generation_and_content(self, tmp_path):
        (tmp_path / "tiktok-full.yml").write_text(YAML_WITH_GENERATION)
        profile = load_profile("tiktok-full", profiles_dir=tmp_path)
        assert profile.generation.voice == "onyx"
        assert profile.generation.speed == 0.95
        assert profile.generation.image_quality == "high"
        assert profile.generation.image_style_prefix == "Professional, serious tone. "
        assert profile.generation.max_duration == 60.0
        assert profile.content.tone == "です・ます調"
        assert profile.content.target_audience == "政治に興味のある20-40代"
        assert "偏向表現の禁止" in profile.content.guidelines
        assert "事実ベース" in profile.content.guidelines

    def test_load_without_generation_uses_defaults(self, tmp_path):
        (tmp_path / "tiktok-politics.yml").write_text(VALID_TIKTOK_YAML)
        profile = load_profile("tiktok-politics", profiles_dir=tmp_path)
        assert profile.generation == GenerationDefaults()
        assert profile.content == ContentGuidelines()


class TestSaveProfile:
    def test_save_and_reload(self, tmp_path):
        profile = Profile(
            name="tiktok-test",
            platform="tiktok",
            display_name="Test Channel",
            description="A test channel",
            defaults=TikTokDefaults(
                privacy_level="PUBLIC_TO_EVERYONE",
                hashtags=("#test", "#oslo"),
            ),
            credentials=CredentialConfig(env_prefix="TIKTOK_TEST"),
        )
        save_profile(profile, profiles_dir=tmp_path)
        loaded = load_profile("tiktok-test", profiles_dir=tmp_path)
        assert loaded.name == profile.name
        assert loaded.platform == profile.platform
        assert loaded.display_name == profile.display_name
        assert loaded.description == profile.description
        assert loaded.defaults.hashtags == ("#test", "#oslo")
        assert loaded.defaults.privacy_level == "PUBLIC_TO_EVERYONE"

    def test_save_creates_directory(self, tmp_path):
        subdir = tmp_path / "new-profiles"
        profile = Profile(
            name="test",
            platform="tiktok",
            display_name="Test",
            credentials=CredentialConfig(env_prefix="TEST"),
        )
        path = save_profile(profile, profiles_dir=subdir)
        assert path.exists()
        assert subdir.exists()


class TestListProfiles:
    def test_empty_directory(self, tmp_path):
        assert list_profiles(profiles_dir=tmp_path) == []

    def test_lists_yml_files_only(self, tmp_path):
        (tmp_path / "alpha.yml").write_text("name: alpha\nplatform: tiktok\n")
        (tmp_path / "beta.yml").write_text("name: beta\nplatform: youtube\n")
        (tmp_path / "not-a-profile.txt").write_text("ignore me")
        result = list_profiles(profiles_dir=tmp_path)
        assert result == ["alpha", "beta"]

    def test_sorted_alphabetically(self, tmp_path):
        (tmp_path / "zzz.yml").write_text("name: zzz\n")
        (tmp_path / "aaa.yml").write_text("name: aaa\n")
        assert list_profiles(profiles_dir=tmp_path) == ["aaa", "zzz"]

    def test_nonexistent_directory(self, tmp_path):
        assert list_profiles(profiles_dir=tmp_path / "nonexistent") == []


class TestValidateCredentials:
    def test_all_present(self, monkeypatch):
        monkeypatch.setenv("TEST_CLIENT_KEY", "key123")
        monkeypatch.setenv("TEST_CLIENT_SECRET", "secret456")
        profile = Profile(
            name="test",
            platform="tiktok",
            display_name="Test",
            credentials=CredentialConfig(
                env_prefix="TEST",
                required_vars=("CLIENT_KEY", "CLIENT_SECRET"),
            ),
        )
        result = validate_credentials(profile)
        assert result == {"TEST_CLIENT_KEY": True, "TEST_CLIENT_SECRET": True}

    def test_some_missing(self, monkeypatch):
        monkeypatch.setenv("TEST_CLIENT_KEY", "key123")
        monkeypatch.delenv("TEST_CLIENT_SECRET", raising=False)
        profile = Profile(
            name="test",
            platform="tiktok",
            display_name="Test",
            credentials=CredentialConfig(
                env_prefix="TEST",
                required_vars=("CLIENT_KEY", "CLIENT_SECRET"),
            ),
        )
        result = validate_credentials(profile)
        assert result["TEST_CLIENT_KEY"] is True
        assert result["TEST_CLIENT_SECRET"] is False


class TestTikTokDefaults:
    def test_default_values(self):
        defaults = TikTokDefaults()
        assert defaults.privacy_level == "SELF_ONLY"
        assert defaults.is_aigc is True
        assert defaults.disable_duet is False
        assert defaults.disable_stitch is False
        assert defaults.disable_comment is False
        assert defaults.brand_content_toggle is False
        assert defaults.hashtags == ()

    def test_frozen(self):
        defaults = TikTokDefaults()
        with pytest.raises(AttributeError):
            defaults.is_aigc = False


class TestGenerationDefaults:
    def test_all_none_by_default(self):
        gen = GenerationDefaults()
        assert gen.voice is None
        assert gen.speed is None
        assert gen.image_quality is None
        assert gen.image_style_prefix is None
        assert gen.max_duration is None

    def test_frozen(self):
        gen = GenerationDefaults(voice="alloy")
        with pytest.raises(AttributeError):
            gen.voice = "nova"


class TestContentGuidelines:
    def test_empty_by_default(self):
        content = ContentGuidelines()
        assert content.tone == ""
        assert content.target_audience == ""
        assert content.guidelines == ()

    def test_frozen(self):
        content = ContentGuidelines(tone="test")
        with pytest.raises(AttributeError):
            content.tone = "changed"


class TestSaveProfileWithGeneration:
    def test_roundtrip_with_generation_and_content(self, tmp_path):
        profile = Profile(
            name="tiktok-roundtrip",
            platform="tiktok",
            display_name="Roundtrip Test",
            defaults=TikTokDefaults(),
            credentials=CredentialConfig(env_prefix="TEST"),
            generation=GenerationDefaults(
                voice="onyx",
                speed=0.9,
                image_quality="high",
                image_style_prefix="Dark, dramatic. ",
                max_duration=60.0,
            ),
            content=ContentGuidelines(
                tone="です・ます調",
                target_audience="20-40代",
                guidelines=("ルール1", "ルール2"),
            ),
        )
        save_profile(profile, profiles_dir=tmp_path)
        loaded = load_profile("tiktok-roundtrip", profiles_dir=tmp_path)
        assert loaded.generation.voice == "onyx"
        assert loaded.generation.speed == 0.9
        assert loaded.generation.image_style_prefix == "Dark, dramatic. "
        assert loaded.content.tone == "です・ます調"
        assert loaded.content.guidelines == ("ルール1", "ルール2")

    def test_save_omits_empty_generation(self, tmp_path):
        profile = Profile(
            name="tiktok-empty",
            platform="tiktok",
            display_name="Empty Gen",
            credentials=CredentialConfig(env_prefix="TEST"),
        )
        path = save_profile(profile, profiles_dir=tmp_path)
        content = path.read_text()
        assert "generation" not in content
        assert "content" not in content
