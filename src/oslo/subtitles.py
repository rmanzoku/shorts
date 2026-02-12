"""Subtitle generation and SRT file writing."""

from dataclasses import dataclass
from pathlib import Path

from pydub import AudioSegment

from oslo.text_processor import Scene, _is_cjk_dominant


@dataclass
class SubtitleEntry:
    index: int
    start_time: float  # seconds
    end_time: float  # seconds
    text: str


def generate_subtitles(
    scenes: list[Scene],
    audio_paths: list[Path],
    words_per_subtitle: int = 6,
) -> list[SubtitleEntry]:
    """Generate subtitle entries with timing based on actual audio durations.

    For CJK text, scene.words are already properly-sized chunks (≤18 chars)
    and should not be further grouped. For English, words are grouped by
    words_per_subtitle. Timing is weighted by character count.
    """
    entries = []
    subtitle_index = 1
    cumulative_time = 0.0

    for scene, audio_path in zip(scenes, audio_paths):
        audio = AudioSegment.from_mp3(str(audio_path))
        scene_duration = audio.duration_seconds

        words = scene.words
        if not words:
            cumulative_time += scene_duration
            continue

        # CJK: words are already subtitle-sized chunks, use directly
        # English: group words into subtitle chunks
        is_cjk = _is_cjk_dominant(scene.narration_text)
        if is_cjk:
            chunks = words
        else:
            chunks = []
            for i in range(0, len(words), words_per_subtitle):
                chunks.append(" ".join(words[i : i + words_per_subtitle]))

        # Character-count weighted timing with minimum display guarantee
        char_counts = [len(c) for c in chunks]
        total_chars = sum(char_counts)
        n_chunks = len(chunks)
        min_display = 1.0  # seconds
        guaranteed = min_display * n_chunks
        remaining = scene_duration - guaranteed

        if remaining > 0 and total_chars > 0:
            durations = [
                min_display + (count / total_chars) * remaining
                for count in char_counts
            ]
        else:
            durations = [scene_duration / n_chunks] * n_chunks

        for i, chunk_text in enumerate(chunks):
            start = cumulative_time + sum(durations[:i])
            end = start + durations[i]
            entries.append(
                SubtitleEntry(
                    index=subtitle_index,
                    start_time=start,
                    end_time=end,
                    text=chunk_text,
                )
            )
            subtitle_index += 1

        cumulative_time += scene_duration

    return entries


def write_srt(entries: list[SubtitleEntry], output_path: Path) -> Path:
    """Write subtitle entries to an SRT file."""
    lines = []
    for entry in entries:
        lines.append(str(entry.index))
        lines.append(f"{_format_time(entry.start_time)} --> {_format_time(entry.end_time)}")
        lines.append(entry.text)
        lines.append("")
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def _format_time(seconds: float) -> str:
    """Format seconds to SRT time format: HH:MM:SS,mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
