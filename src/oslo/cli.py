"""CLI entry point for Oslo."""

from pathlib import Path

import click

from oslo.config import load_config


@click.group()
@click.version_option(package_name="oslo")
def main():
    """Oslo - Generate short videos from text."""


@main.command()
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    default=None,
    help="Output video file path. Defaults to <input_name>.mp4",
)
@click.option(
    "--voice",
    type=str,
    default=None,
    help="TTS voice: alloy, ash, ballad, coral, echo, fable, nova, onyx, sage, shimmer",
)
@click.option("--speed", type=float, default=None, help="TTS speed (0.25-4.0, default 1.0)")
@click.option(
    "--max-duration",
    type=float,
    default=None,
    help="Maximum video duration in seconds (default 90)",
)
@click.option(
    "--image-quality",
    type=click.Choice(["low", "medium", "high"]),
    default=None,
    help="Image generation quality",
)
@click.option(
    "--keep-temp",
    is_flag=True,
    default=False,
    help="Keep intermediate files (audio, images, SRT) after completion",
)
@click.option("-v", "--verbose", is_flag=True, default=False, help="Enable verbose output")
@click.option("-y", "--yes", is_flag=True, default=False, help="Skip confirmation prompt")
def generate(
    input_file, output, voice, speed, max_duration, image_quality, keep_temp, verbose, yes
):
    """Generate a short video from a text file."""
    from oslo.pipeline import generate_video

    if output is None:
        output = input_file.with_suffix(".mp4")

    config = load_config(
        voice=voice,
        speed=speed,
        max_duration=max_duration,
        image_quality=image_quality,
    )

    generate_video(
        input_file=input_file,
        output_file=output,
        config=config,
        keep_temp=keep_temp,
        verbose=verbose,
        skip_confirm=yes,
    )
    click.echo(f"Video saved to {output}")
