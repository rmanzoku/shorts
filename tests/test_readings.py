"""Tests for readings module."""

from oslo.readings import apply_readings, load_readings


class TestLoadReadings:
    def test_load_basic(self, tmp_path):
        content = "人名:\n  安野貴博: あんのたかひろ\n"
        (tmp_path / "readings.yml").write_text(content, encoding="utf-8")
        readings = load_readings(tmp_path / "readings.yml")
        assert readings == {"安野貴博": "あんのたかひろ"}

    def test_load_multiple_categories(self, tmp_path):
        content = "人名:\n  田中太郎: たなかたろう\n地名:\n  御茶ノ水: おちゃのみず\n"
        (tmp_path / "readings.yml").write_text(content, encoding="utf-8")
        readings = load_readings(tmp_path / "readings.yml")
        assert readings == {"田中太郎": "たなかたろう", "御茶ノ水": "おちゃのみず"}

    def test_load_nonexistent_returns_empty(self, tmp_path):
        readings = load_readings(tmp_path / "nonexistent.yml")
        assert readings == {}

    def test_load_empty_file(self, tmp_path):
        (tmp_path / "readings.yml").write_text("", encoding="utf-8")
        readings = load_readings(tmp_path / "readings.yml")
        assert readings == {}


class TestApplyReadings:
    def test_single_replacement(self):
        result = apply_readings("安野貴博氏が", {"安野貴博": "あんのたかひろ"})
        assert result == "あんのたかひろ氏が"

    def test_multiple_replacements(self):
        text = "安野貴博氏は御茶ノ水で演説した。"
        readings = {"安野貴博": "あんのたかひろ", "御茶ノ水": "おちゃのみず"}
        result = apply_readings(text, readings)
        assert result == "あんのたかひろ氏はおちゃのみずで演説した。"

    def test_no_match(self):
        result = apply_readings("テストテキスト", {"安野貴博": "あんのたかひろ"})
        assert result == "テストテキスト"

    def test_empty_readings(self):
        result = apply_readings("安野貴博氏が", {})
        assert result == "安野貴博氏が"
