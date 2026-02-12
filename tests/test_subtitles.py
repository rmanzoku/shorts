"""Tests for subtitles module."""

from oslo.subtitles import SubtitleEntry, _format_time, write_srt


class TestFormatTime:
    def test_zero(self):
        assert _format_time(0.0) == "00:00:00,000"

    def test_one_second(self):
        assert _format_time(1.0) == "00:00:01,000"

    def test_with_milliseconds(self):
        assert _format_time(1.5) == "00:00:01,500"

    def test_minutes(self):
        assert _format_time(65.0) == "00:01:05,000"

    def test_hours(self):
        assert _format_time(3661.5) == "01:01:01,500"


class TestWriteSrt:
    def test_writes_valid_srt(self, tmp_path):
        entries = [
            SubtitleEntry(index=1, start_time=0.0, end_time=2.5, text="Hello world"),
            SubtitleEntry(index=2, start_time=2.5, end_time=5.0, text="Second line"),
        ]
        output = tmp_path / "test.srt"
        write_srt(entries, output)

        content = output.read_text()
        assert "1\n" in content
        assert "00:00:00,000 --> 00:00:02,500" in content
        assert "Hello world" in content
        assert "2\n" in content
        assert "Second line" in content

    def test_empty_entries(self, tmp_path):
        output = tmp_path / "empty.srt"
        write_srt([], output)
        assert output.read_text() == ""
