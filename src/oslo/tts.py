"""OpenAI Text-to-Speech client."""

from pathlib import Path

import click
from openai import OpenAI

from oslo.config import TTSConfig
from oslo.text_processor import Scene
from oslo.utils import retry_on_rate_limit


class TTSClient:
    def __init__(self, api_key: str, config: TTSConfig):
        self.client = OpenAI(api_key=api_key)
        self.config = config

    @retry_on_rate_limit()
    def generate_speech(self, text: str, output_path: Path) -> Path:
        """Generate speech audio for the given text using streaming response."""
        with self.client.audio.speech.with_streaming_response.create(
            model=self.config.model,
            voice=self.config.voice,
            input=text,
            speed=self.config.speed,
            response_format=self.config.output_format,
        ) as response:
            response.stream_to_file(str(output_path))
        return output_path

    def generate_all_scenes(
        self, scenes: list[Scene], temp_dir: Path, verbose: bool = False
    ) -> list[Path]:
        """Generate audio for all scenes. Returns list of audio file paths."""
        audio_paths = []
        for scene in scenes:
            if verbose:
                click.echo(f"  Generating audio for scene {scene.index + 1}/{len(scenes)}...")
            audio_path = temp_dir / f"scene_{scene.index:03d}.mp3"
            self.generate_speech(scene.narration_text, audio_path)
            audio_paths.append(audio_path)
        return audio_paths
