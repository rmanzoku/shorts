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
    help="Image generation quality (OpenAI only)",
)
@click.option(
    "--image-provider",
    type=click.Choice(["openai", "gemini"]),
    default=None,
    help="Image generation provider (default: gemini)",
)
@click.option(
    "--keep-temp",
    is_flag=True,
    default=False,
    help="Keep intermediate files (audio, images, SRT) after completion",
)
@click.option("-v", "--verbose", is_flag=True, default=False, help="Enable verbose output")
@click.option("-y", "--yes", is_flag=True, default=False, help="Skip confirmation prompt")
@click.option(
    "--profile",
    "profile_name",
    type=str,
    default=None,
    help="Profile name for generation defaults (e.g., tiktok-politics)",
)
def generate(
    input_file, output, voice, speed, max_duration, image_quality, image_provider,
    keep_temp, verbose, yes, profile_name,
):
    """Generate a short video from a text file."""
    from oslo.pipeline import generate_video

    profile_defaults = None
    if profile_name:
        from oslo.profile import load_profile

        prof = load_profile(profile_name)
        profile_defaults = prof.generation
        if verbose:
            click.echo(f"Using profile: {profile_name}")

    if output is None:
        output = input_file.with_suffix(".mp4")

    config = load_config(
        voice=voice,
        speed=speed,
        max_duration=max_duration,
        image_quality=image_quality,
        image_provider=image_provider,
        profile_defaults=profile_defaults,
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


@main.group()
def profile():
    """Manage SNS account profiles."""


@profile.command("list")
def profile_list():
    """List all profiles."""
    from oslo.profile import list_profiles

    names = list_profiles()
    if not names:
        click.echo("No profiles found. Create one with: oslo profile create")
        return

    click.echo(f"Profiles ({len(names)}):")
    for name in names:
        click.echo(f"  {name}")


@profile.command("show")
@click.argument("name")
def profile_show(name):
    """Show profile details."""
    from oslo.profile import TikTokDefaults, load_profile, validate_credentials

    prof = load_profile(name)

    click.echo(f"Profile: {prof.name}")
    click.echo(f"  Platform:     {prof.platform}")
    click.echo(f"  Display name: {prof.display_name}")
    click.echo(f"  Description:  {prof.description}")
    click.echo(f"  Language:     {prof.language}")

    if isinstance(prof.defaults, TikTokDefaults):
        click.echo("  Defaults:")
        click.echo(f"    Privacy:          {prof.defaults.privacy_level}")
        click.echo(f"    AI content:       {prof.defaults.is_aigc}")
        click.echo(f"    Disable duet:     {prof.defaults.disable_duet}")
        click.echo(f"    Disable stitch:   {prof.defaults.disable_stitch}")
        click.echo(f"    Disable comment:  {prof.defaults.disable_comment}")
        click.echo(f"    Hashtags:         {', '.join(prof.defaults.hashtags)}")

    from oslo.profile import GenerationDefaults

    if prof.generation != GenerationDefaults():
        click.echo("  Generation:")
        gen = prof.generation
        if gen.voice is not None:
            click.echo(f"    Voice:            {gen.voice}")
        if gen.speed is not None:
            click.echo(f"    Speed:            {gen.speed}")
        if gen.image_quality is not None:
            click.echo(f"    Image quality:    {gen.image_quality}")
        if gen.image_style_prefix is not None:
            click.echo(f"    Image style:      {gen.image_style_prefix[:60]}...")
        if gen.max_duration is not None:
            click.echo(f"    Max duration:     {gen.max_duration}s")

    if prof.content.tone or prof.content.target_audience or prof.content.guidelines:
        click.echo("  Content:")
        if prof.content.tone:
            click.echo(f"    Tone:             {prof.content.tone}")
        if prof.content.target_audience:
            click.echo(f"    Target audience:  {prof.content.target_audience}")
        if prof.content.guidelines:
            click.echo("    Guidelines:")
            for g in prof.content.guidelines:
                click.echo(f"      - {g}")

    cred_status = validate_credentials(prof)
    click.echo("  Credentials:")
    for var, present in cred_status.items():
        status = "SET" if present else "MISSING"
        click.echo(f"    {var}: {status}")


@profile.command("create")
@click.option("--name", prompt="Profile name (e.g., tiktok-politics)", type=str)
@click.option(
    "--platform",
    prompt="Platform",
    type=click.Choice(["tiktok", "youtube", "instagram"]),
)
@click.option("--display-name", prompt="Display name", type=str)
@click.option("--description", prompt="Description", type=str, default="")
def profile_create(name, platform, display_name, description):
    """Create a new profile interactively."""
    from oslo.profile import (
        CredentialConfig,
        Profile,
        TikTokDefaults,
        list_profiles,
        save_profile,
        validate_profile_name,
    )

    validate_profile_name(name)

    if name in list_profiles():
        raise click.ClickException(f"Profile '{name}' already exists")

    env_prefix = name.upper().replace("-", "_")

    if platform == "tiktok":
        defaults = TikTokDefaults()
    else:
        defaults = {}

    prof = Profile(
        name=name,
        platform=platform,
        display_name=display_name,
        description=description,
        defaults=defaults,
        credentials=CredentialConfig(
            env_prefix=env_prefix,
            required_vars=("CLIENT_KEY", "CLIENT_SECRET"),
        ),
    )

    path = save_profile(prof)
    click.echo(f"Profile saved to {path}")
    click.echo("Add credentials to .env:")
    click.echo(f"  {env_prefix}_CLIENT_KEY=<your-client-key>")
    click.echo(f"  {env_prefix}_CLIENT_SECRET=<your-client-secret>")


@profile.command("validate")
@click.argument("name")
def profile_validate(name):
    """Validate profile and check credentials."""
    from oslo.profile import load_profile, validate_credentials

    prof = load_profile(name)
    click.echo(f"Profile '{name}' loaded successfully.")

    cred_status = validate_credentials(prof)
    all_ok = all(cred_status.values())

    for var, present in cred_status.items():
        icon = "+" if present else "-"
        status = "OK" if present else "MISSING"
        click.echo(f"  [{icon}] {var}: {status}")

    if all_ok:
        click.echo("All credentials present.")
    else:
        missing = [v for v, ok in cred_status.items() if not ok]
        click.echo(f"Missing {len(missing)} credential(s). Add them to .env")


@main.group()
def library():
    """画像ライブラリを管理する。"""


@library.command("add")
@click.argument("image_path", type=click.Path(exists=True, path_type=Path))
@click.option("--slug", type=str, default=None, help="カスタムスラッグ（省略時は自動連番）")
@click.option("--source", type=str, default="", help="出典・ソース")
@click.option(
    "--skip-analysis",
    is_flag=True,
    default=False,
    help="GPT-4o vision による自動メタデータ抽出をスキップ",
)
def library_add(image_path, slug, source, skip_analysis):
    """画像をライブラリに追加する。"""
    from oslo.library import add_image, analyze_image

    tags = ()
    description = ""

    if not skip_analysis:
        import json
        import os

        import openai
        from dotenv import load_dotenv

        load_dotenv()
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise click.ClickException(
                "OPENAI_API_KEY が必要です（--skip-analysis でスキップ可能）"
            )

        click.echo("画像を分析中...")
        try:
            result = analyze_image(api_key, image_path)
            tags = tuple(result.get("tags", []))
            description = result.get("description", "")
            click.echo(f"  タグ: {', '.join(tags)}")
            click.echo(f"  説明: {description}")
        except (
            json.JSONDecodeError, openai.APIError, openai.APIConnectionError,
        ) as e:
            click.echo(f"  分析に失敗しました: {e}")
            click.echo("  空のメタデータで続行します。")

    meta = add_image(
        image_path,
        slug=slug,
        tags=tags,
        description=description,
        source=source,
    )
    click.echo(f"追加しました: {meta.slug} ({meta.path})")


@library.command("list")
@click.option("--tag", type=str, default=None, help="タグでフィルタ")
def library_list(tag):
    """ライブラリの画像一覧を表示する。"""
    from oslo.library import list_images, search_images

    if tag:
        images = search_images([tag])
    else:
        images = list_images()

    if not images:
        click.echo("画像がありません。oslo library add で追加してください。")
        return

    click.echo(f"Images ({len(images)}):")
    for img in images:
        tags_str = ", ".join(img.tags) if img.tags else ""
        desc_str = img.description[:40] if img.description else ""
        click.echo(f"  {img.slug:<20} [{tags_str}]  {desc_str}")


@library.command("show")
@click.argument("slug")
def library_show(slug):
    """画像のメタデータを表示する。"""
    from oslo.library import load_image_meta

    meta = load_image_meta(slug)
    click.echo(f"Image: {meta.slug}")
    click.echo(f"  File:        {meta.path}")
    click.echo(f"  Tags:        {', '.join(meta.tags)}")
    click.echo(f"  Description: {meta.description}")
    click.echo(f"  Source:      {meta.source}")
    click.echo(f"  Added:       {meta.added}")
