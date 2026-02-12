"""TTS reading dictionary: replace kanji with readings for correct pronunciation."""

from pathlib import Path

import yaml


def load_readings(path: Path) -> dict[str, str]:
    """Load readings.yml and return a flat {kanji: reading} dictionary.

    The YAML file is organized by category (e.g. 人名, 地名) but the
    returned dictionary is flat for simple string replacement.
    Returns an empty dict if the file does not exist.
    """
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not data or not isinstance(data, dict):
        return {}
    readings: dict[str, str] = {}
    for entries in data.values():
        if isinstance(entries, dict):
            for kanji, reading in entries.items():
                readings[str(kanji)] = str(reading)
    return readings


def apply_readings(text: str, readings: dict[str, str]) -> str:
    """Replace dictionary entries in text with their readings."""
    for kanji, reading in readings.items():
        text = text.replace(kanji, reading)
    return text
