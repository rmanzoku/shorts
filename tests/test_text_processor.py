"""Tests for text_processor module."""

from oslo.text_processor import (
    Scene,
    _is_cjk_dominant,
    _split_for_subtitles,
    estimate_duration,
    generate_image_prompt,
    split_into_scenes,
    truncate_to_duration,
)


class TestCJKDetection:
    def test_japanese_text(self):
        assert _is_cjk_dominant("これは日本語のテストです。")

    def test_english_text(self):
        assert not _is_cjk_dominant("This is an English test.")

    def test_mixed_mostly_japanese(self):
        assert _is_cjk_dominant("AIが変える未来の働き方について解説します。")

    def test_empty_text(self):
        assert not _is_cjk_dominant("")


class TestEstimateDuration:
    def test_english_estimation(self):
        # 150 words at 150 wpm = 60 seconds
        text = " ".join(["word"] * 150)
        assert estimate_duration(text) == 60.0

    def test_english_short_text(self):
        text = "Hello world"
        assert estimate_duration(text) == (2 / 150) * 60

    def test_empty_text(self):
        assert estimate_duration("") == 0.0

    def test_japanese_estimation(self):
        # 350 chars at 350 cpm = 60 seconds
        text = "あ" * 350
        assert abs(estimate_duration(text) - 60.0) < 0.1

    def test_japanese_short(self):
        text = "これはテストです。"
        duration = estimate_duration(text)
        assert duration > 0


class TestTruncateToDuration:
    def test_short_text_unchanged(self):
        text = "This is a short text."
        result = truncate_to_duration(text, max_duration=60.0)
        assert result == text

    def test_long_english_truncated(self):
        sentences = ["This is sentence number one. "] * 50
        text = "".join(sentences)
        result = truncate_to_duration(text, max_duration=90.0)
        assert len(result.split()) <= 225 + 10

    def test_truncates_at_sentence_boundary(self):
        text = "First sentence. Second sentence. Third sentence. "
        text += "Fourth sentence. Fifth sentence. Sixth sentence."
        result = truncate_to_duration(text, max_duration=5.0)
        assert result.endswith(".")

    def test_japanese_short_unchanged(self):
        text = "これは短いテストです。"
        result = truncate_to_duration(text, max_duration=60.0)
        assert result == text


class TestSplitForSubtitles:
    def test_english_splits_on_spaces(self):
        result = _split_for_subtitles("Hello world foo bar")
        assert result == ["Hello", "world", "foo", "bar"]

    def test_japanese_splits_on_punctuation(self):
        text = "これは日本語のテストです。字幕を正しく分割できるか確認します。"
        result = _split_for_subtitles(text)
        assert len(result) >= 2
        # Should split on 。 not mid-word
        assert result[0] == "これは日本語のテストです。"
        assert result[1] == "字幕を正しく分割できるか確認します。"

    def test_japanese_long_chunk_resplit(self):
        text = "これはとても長い文章で句読点がないまま続いていくような特殊なケースです。"
        result = _split_for_subtitles(text)
        # max 22 chars (18 base + 4 for merging short trailing fragments)
        for chunk in result:
            assert len(chunk) <= 22

    def test_japanese_short_chunk_merged(self):
        text = "はい、了解。"
        result = _split_for_subtitles(text)
        # "はい、" (3 chars) + "了解。" (3 chars) should merge
        assert len(result) == 1


class TestSplitIntoScenes:
    def test_english_returns_scenes(self):
        text = (
            "Paragraph one about topic A.\n\n"
            "Paragraph two about topic B.\n\n"
            "Paragraph three about topic C."
        )
        scenes = split_into_scenes(text)
        assert all(isinstance(s, Scene) for s in scenes)
        assert len(scenes) >= 1

    def test_scene_has_narration_and_prompt(self):
        text = (
            "This is a test paragraph with enough words to form a scene.\n\n"
            "Another paragraph here with more content to work with.\n\n"
            "Third paragraph for good measure with additional words."
        )
        scenes = split_into_scenes(text)
        for scene in scenes:
            assert scene.narration_text
            assert scene.image_prompt
            assert len(scene.words) > 0

    def test_scene_indices_sequential(self):
        text = "First part.\n\nSecond part.\n\nThird part."
        scenes = split_into_scenes(text)
        for i, scene in enumerate(scenes):
            assert scene.index == i

    def test_empty_text_raises(self):
        import pytest

        with pytest.raises(ValueError, match="empty"):
            split_into_scenes("")

    def test_single_sentence(self):
        text = "Just one sentence about a single topic."
        scenes = split_into_scenes(text)
        assert len(scenes) >= 1
        assert scenes[0].narration_text == text

    def test_max_duration_respected(self):
        text = " ".join(["word"] * 500)
        scenes = split_into_scenes(text, max_duration=30.0)
        total_words = sum(len(s.words) for s in scenes)
        max_words_for_30s = int((30.0 / 60.0) * 150) + 10
        assert total_words <= max_words_for_30s

    def test_japanese_multiple_scenes(self):
        text = (
            "AIが変える未来の働き方について解説します。人工知能の急速な発展が進んでいます。\n\n"
            "企業の多くがAIを業務に導入し始めており、様々な場面で活用されています。\n\n"
            "新しいスキルの習得が求められています。プログラミングやデータリテラシーが重要です。\n\n"
            "未来の職場では、人間とAIが互いの強みを活かしながら協力する姿が当たり前になります。"
        )
        scenes = split_into_scenes(text)
        assert len(scenes) >= 3, f"Expected >= 3 scenes, got {len(scenes)}"

    def test_japanese_scene_has_subtitle_chunks(self):
        text = (
            "人工知能の急速な発展により、私たちの働き方は大きく変わろうとしています。\n\n"
            "企業の多くがAIを業務に導入し始めています。データ分析や文書作成に活用されています。\n\n"
            "未来の職場では、人間とAIが協力する姿が当たり前になるかもしれません。"
        )
        scenes = split_into_scenes(text)
        for scene in scenes:
            assert len(scene.words) >= 1
            # Japanese chunks should be punctuation-based, max 22 chars
            # (18 base + 4 for merging short trailing fragments)
            for chunk in scene.words:
                assert len(chunk) <= 22


class TestGenerateImagePrompt:
    def test_contains_style_prefix(self):
        prompt = generate_image_prompt("A cat sitting on a wall")
        assert "Cinematic" in prompt
        assert "cat sitting" in prompt

    def test_long_text_truncated(self):
        long_text = "word " * 200
        prompt = generate_image_prompt(long_text)
        assert len(prompt) < 600
