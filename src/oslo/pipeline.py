"""Pipeline orchestrator: text -> video."""

import shutil
import tempfile
from pathlib import Path

import click

from oslo.composer import compose_video
from oslo.config import AppConfig
from oslo.conte import is_conte_format, parse_conte, parse_conte_title
from oslo.image_gen import ImageGenerator
from oslo.readings import apply_readings, load_readings
from oslo.subtitles import generate_subtitles, write_srt
from oslo.text_processor import split_into_scenes
from oslo.tts import TTSClient


def generate_video(
    input_file: Path,
    output_file: Path,
    config: AppConfig,
    keep_temp: bool = False,
    verbose: bool = False,
    skip_confirm: bool = False,
) -> Path:
    """Full pipeline: text -> scenes -> audio + images + subtitles -> video."""
    text = input_file.read_text(encoding="utf-8").strip()
    if not text:
        raise click.ClickException("Input file is empty")

    title = None
    temp_dir = Path(tempfile.mkdtemp(prefix="oslo_"))
    try:
        # Stage 1: Parse conte or split text into scenes
        if input_file.suffix.lower() == ".md" or is_conte_format(text):
            if verbose:
                click.echo("Parsing conte...")
            scenes = parse_conte(text, image_style_prefix=config.image_style_prefix)
            title = parse_conte_title(text)
        else:
            if verbose:
                click.echo("Splitting text into scenes...")
            scenes = split_into_scenes(
                text,
                max_duration=config.video.max_duration,
                image_style_prefix=config.image_style_prefix,
            )
        if verbose:
            click.echo(f"  Created {len(scenes)} scenes")

        # Apply TTS reading dictionary
        readings_path = input_file.parent / "readings.yml"
        if not readings_path.exists():
            readings_path = Path.cwd() / "readings.yml"
        readings = load_readings(readings_path)
        if readings:
            if verbose:
                click.echo(f"  Applied {len(readings)} reading(s) for TTS")
            for scene in scenes:
                scene.tts_text = apply_readings(scene.narration_text, readings)

        # Confirm before API calls
        if not skip_confirm:
            ai_image_count = sum(1 for s in scenes if not s.library_image)
            lib_image_count = sum(1 for s in scenes if s.library_image)
            click.echo(f"\n  Scenes: {len(scenes)}")
            click.echo(
                f"  API calls: {len(scenes)} TTS + {ai_image_count} image generation"
            )
            if lib_image_count:
                click.echo(f"  Library images: {lib_image_count} (no API cost)")
            if not click.confirm("  Proceed with API calls?", default=True):
                raise click.Abort()

        # Stage 2: Generate narration audio
        if verbose:
            click.echo("Generating narration audio...")
        tts_client = TTSClient(config.openai_api_key, config.tts)
        audio_paths = tts_client.generate_all_scenes(scenes, temp_dir, verbose=verbose)

        # Stage 3: Generate background images
        if verbose:
            click.echo("Generating background images...")
        image_gen = ImageGenerator(config.openai_api_key, config.image_gen, config.video)
        image_paths = image_gen.generate_all_scenes(scenes, temp_dir, verbose=verbose)

        # Stage 4: Generate subtitles
        if verbose:
            click.echo("Generating subtitles...")
        subtitle_entries = generate_subtitles(scenes, audio_paths)
        srt_path = write_srt(subtitle_entries, temp_dir / "subtitles.srt")

        # Stage 5: Compose final video
        if verbose:
            click.echo("Composing video...")
        stat_overlays = [s.stat_overlay for s in scenes]
        compose_video(
            image_paths=image_paths,
            audio_paths=audio_paths,
            srt_path=srt_path,
            output_path=output_file,
            config=config.video,
            title=title,
            hook_text=title,
            stat_overlays=stat_overlays,
        )

        return output_file

    finally:
        if keep_temp:
            click.echo(f"Temporary files kept at: {temp_dir}")
        else:
            shutil.rmtree(temp_dir, ignore_errors=True)
