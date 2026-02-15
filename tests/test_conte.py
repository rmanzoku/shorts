"""Tests for conte module."""

import warnings

import pytest

from oslo.conte import is_conte_format, parse_conte, parse_conte_hook
from oslo.text_processor import IMAGE_STYLE_PREFIX, Scene, generate_image_prompt

TEST_CONTE_MARKDOWN = """# テストタイトル

## シーン 1
**映像**: 東京タワーの夜景
**ナレーション**: テスト用のナレーションです。
**数字**: 333m

## シーン 2
**映像**: 渋谷のスクランブル交差点
**ナレーション**: 二つ目のシーンのテキストです。
**数字**: 1日30万人
"""


def test_is_conte_format_with_japanese_headers():
    text = "## シーン 1\n**ナレーション**: テスト"
    assert is_conte_format(text)


def test_is_conte_format_with_english_headers():
    text = "## Scene 1\n**ナレーション**: Test narration"
    assert is_conte_format(text)


def test_is_conte_format_plain_text():
    text = "これは通常のテキストです。"
    assert not is_conte_format(text)


def test_parse_conte_basic():
    scenes = parse_conte(TEST_CONTE_MARKDOWN)

    assert len(scenes) == 2
    assert all(isinstance(scene, Scene) for scene in scenes)

    assert scenes[0].index == 0
    assert scenes[0].narration_text == "テスト用のナレーションです。"
    assert scenes[0].image_prompt.startswith(IMAGE_STYLE_PREFIX)
    assert "東京タワーの夜景" in scenes[0].image_prompt

    assert scenes[1].index == 1
    assert scenes[1].narration_text == "二つ目のシーンのテキストです。"
    assert scenes[1].image_prompt.startswith(IMAGE_STYLE_PREFIX)
    assert "渋谷のスクランブル交差点" in scenes[1].image_prompt


def test_parse_conte_visual_has_style_prefix():
    text = """## シーン 1
**映像**: 海辺の夕焼け
**ナレーション**: 波の音が静かに響きます。
"""
    scene = parse_conte(text)[0]
    assert IMAGE_STYLE_PREFIX in scene.image_prompt


def test_parse_conte_visual_has_no_text_suffix():
    text = """## シーン 1
**映像**: 森の中の小道
**ナレーション**: 木漏れ日が差し込んでいます。
"""
    scene = parse_conte(text)[0]
    assert "Do not include any text" in scene.image_prompt


def test_parse_conte_no_visual_fallback():
    text = """## シーン 1
**ナレーション**: 映像指定がない場合のテストです。
"""
    scene = parse_conte(text)[0]
    assert scene.image_prompt == generate_image_prompt("映像指定がない場合のテストです。")


def test_parse_conte_missing_narration():
    text = """## シーン 1
**映像**: 街の風景
"""
    with pytest.raises(ValueError, match="Narration not found in scene 1"):
        parse_conte(text)


def test_parse_conte_no_scenes():
    text = "**ナレーション**: シーンヘッダーがありません。"
    with pytest.raises(ValueError, match="No scenes found in conte markdown"):
        parse_conte(text)


def test_parse_conte_custom_style_prefix():
    custom_prefix = "Dark, dramatic, professional. "
    text = """## シーン 1
**映像**: 国会議事堂
**ナレーション**: 本日の議題を解説します。
"""
    scene = parse_conte(text, image_style_prefix=custom_prefix)[0]
    assert scene.image_prompt.startswith(custom_prefix)
    assert "国会議事堂" in scene.image_prompt
    assert not scene.image_prompt.startswith(IMAGE_STYLE_PREFIX)


def test_parse_conte_custom_style_prefix_fallback():
    custom_prefix = "Custom style. "
    text = """## シーン 1
**ナレーション**: 映像指定なしのカスタムスタイル。
"""
    scene = parse_conte(text, image_style_prefix=custom_prefix)[0]
    assert scene.image_prompt.startswith(custom_prefix)


def test_parse_conte_ignores_non_scene_h2_sections():
    """## 説明 etc. should not be included in the last scene's narration."""
    text = """# タイトル

## シーン 1
**映像**: 東京タワー
**ナレーション**: 最初のシーンです。
**数字**: 333m

## シーン 2
**映像**: 富士山
**ナレーション**: 最後のシーンです。
**数字**: 3776m

## 説明
これは説明欄のテキストです。
ハッシュタグやメタデータが入ります。
"""
    scenes = parse_conte(text)
    assert len(scenes) == 2
    assert scenes[1].narration_text == "最後のシーンです。"
    assert "説明" not in scenes[1].narration_text
    assert "ハッシュタグ" not in scenes[1].narration_text


def test_parse_conte_stat_overlay():
    """Scenes with **数字**: field should have stat_overlay set."""
    scenes = parse_conte(TEST_CONTE_MARKDOWN)
    assert scenes[0].stat_overlay == "333m"
    assert scenes[1].stat_overlay == "1日30万人"


def test_parse_conte_stat_overlay_missing_warns():
    """Missing **数字**: field should emit a warning."""
    text = """## シーン 1
**映像**: 海辺の夕焼け
**ナレーション**: 波の音が静かに響きます。
"""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        scene = parse_conte(text)[0]
        assert scene.stat_overlay is None
        assert len(w) == 1
        assert "**数字** field missing in scene 1" in str(w[0].message)


def test_parse_conte_stat_overlay_with_full_width_colon():
    """**数字**： (full-width colon) should also be parsed."""
    text = """## シーン 1
**映像**: テスト
**ナレーション**: テストです。
**数字**： 100万人
"""
    scene = parse_conte(text)[0]
    assert scene.stat_overlay == "100万人"


def test_parse_conte_library_image():
    """**画像**: slug should set library_image on Scene."""
    text = """## シーン 1
**画像**: 001_kokkai
**ナレーション**: テスト用のナレーションです。
**数字**: 100
"""
    scene = parse_conte(text)[0]
    assert scene.library_image == "001_kokkai"


def test_parse_conte_library_image_overrides_visual():
    """When both **画像** and **映像** are present, library_image takes priority with warning."""
    text = """## シーン 1
**画像**: 001_kokkai
**映像**: 東京タワーの夜景
**ナレーション**: テスト用のナレーションです。
**数字**: 100
"""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        scene = parse_conte(text)[0]
        assert scene.library_image == "001_kokkai"
        assert "東京タワーの夜景" in scene.image_prompt
        override_warnings = [x for x in w if "**画像** overrides **映像**" in str(x.message)]
        assert len(override_warnings) == 1


def test_parse_conte_no_library_image_backward_compat():
    """Existing contes without **画像** should have library_image=None."""
    scenes = parse_conte(TEST_CONTE_MARKDOWN)
    for scene in scenes:
        assert scene.library_image is None


class TestParseConteHook:
    """Tests for parse_conte_hook function."""

    def test_hook_extracted(self):
        text = """# タイトル

**フック**: 年4兆円が非課税？

## シーン 1
**ナレーション**: テストです。
"""
        assert parse_conte_hook(text) == "年4兆円が非課税？"

    def test_hook_with_full_width_colon(self):
        text = """# タイトル

**フック**： 手取り、実は○○万円

## シーン 1
**ナレーション**: テストです。
"""
        assert parse_conte_hook(text) == "手取り、実は○○万円"

    def test_hook_missing_returns_none(self):
        assert parse_conte_hook(TEST_CONTE_MARKDOWN) is None

    def test_hook_not_confused_with_scene_fields(self):
        """Hook-like text inside a scene block should not be extracted."""
        text = """# タイトル

## シーン 1
**フック**: シーン内のフック
**ナレーション**: テストです。
"""
        assert parse_conte_hook(text) is None

    def test_hook_plain_text_returns_none(self):
        assert parse_conte_hook("これは通常のテキストです。") is None
