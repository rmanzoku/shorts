"""Tests for conte module."""

import pytest

from oslo.conte import is_conte_format, parse_conte
from oslo.text_processor import IMAGE_STYLE_PREFIX, Scene, generate_image_prompt

TEST_CONTE_MARKDOWN = """# テストタイトル

## シーン 1
**映像**: 東京タワーの夜景
**ナレーション**: テスト用のナレーションです。

## シーン 2
**映像**: 渋谷のスクランブル交差点
**ナレーション**: 二つ目のシーンのテキストです。
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
