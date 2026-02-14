"""Video composition using MoviePy."""

import platform
from pathlib import Path

from moviepy import (
    AudioFileClip,
    CompositeVideoClip,
    ImageClip,
    TextClip,
    concatenate_audioclips,
    vfx,
)
from moviepy.video.tools.subtitles import SubtitlesClip
from pydub import AudioSegment

from oslo.config import VideoConfig

SUBTITLE_FONT_SIZE = 85
SUBTITLE_COLOR = "white"
SUBTITLE_STROKE_COLOR = "black"
SUBTITLE_STROKE_WIDTH = 3
SUBTITLE_BG_COLOR = (0, 0, 0, 153)  # Semi-transparent black (60% opacity)
SUBTITLE_MARGIN = (20, 15)  # Horizontal, vertical padding
SUBTITLE_Y_POSITION = 0.65  # 65% from top (lower area, clear of title/stat overlays)
CROSSFADE_DURATION = 0.5
HOOK_FONT_SIZE = 120
HOOK_DURATION = 1.5  # seconds
HOOK_BG_COLOR = (0, 0, 0, 255)  # Solid black
STAT_FONT_SIZE = 120
STAT_COLOR = "white"
STAT_STROKE_COLOR = "black"
STAT_STROKE_WIDTH = 5
STAT_BG_COLOR = (0, 0, 0, 180)  # Semi-transparent black
STAT_Y_POSITION = 0.30  # 30% from top (above subtitles)
ZOOM_FACTOR = 0.12  # 12% zoom range for Ken Burns effect
TITLE_FONT_SIZE = 85
TITLE_COLOR = "white"
TITLE_STROKE_WIDTH = 4
TITLE_BG_COLOR = (230, 180, 0, 230)  # Near-opaque yellow/orange bar
TITLE_Y_POSITION = 0.15  # 15% from top (below TikTok header)


def _find_cjk_font() -> str | None:
    """Find a CJK-capable font on the system."""
    if platform.system() == "Darwin":
        candidates = [
            "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
            "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        ]
    else:
        candidates = [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        ]
    for font in candidates:
        if Path(font).exists():
            return font
    return None


def compose_video(
    image_paths: list[Path],
    audio_paths: list[Path],
    srt_path: Path,
    output_path: Path,
    config: VideoConfig,
    title: str | None = None,
    hook_text: str | None = None,
    stat_overlays: list[str | None] | None = None,
) -> Path:
    """Compose the final video from images, audio, and subtitles.

    Pipeline:
    0. (Optional) Create hook frame with title text
    1. Create ImageClip per scene with Ken Burns zoom effect
    2. Concatenate with crossfade transitions
    3. Concatenate audio track
    4. Overlay subtitles from SRT
    5. Write MP4 (H.264 + AAC)
    """
    size = (config.width, config.height)
    cjk_font = _find_cjk_font()

    # Step 0: Create hook frame (text-only opening slide)
    hook_clip = None
    if hook_text:
        hook_kwargs = {
            "text": hook_text,
            "font_size": HOOK_FONT_SIZE,
            "color": "white",
            "bg_color": HOOK_BG_COLOR,
            "method": "caption",
            "size": (config.width - 120, None),
            "margin": (40, 30),
            "text_align": "center",
        }
        if cjk_font:
            hook_kwargs["font"] = cjk_font
        hook_clip = (
            TextClip(**hook_kwargs)
            .with_duration(HOOK_DURATION)
            .with_position("center")
        )
        # Create a black background for the hook frame
        hook_bg = (
            ImageClip(
                TextClip(
                    text=" ",
                    font_size=1,
                    color="black",
                    bg_color=HOOK_BG_COLOR,
                    size=size,
                ).get_frame(0)
            )
            .with_duration(HOOK_DURATION)
        )
        hook_clip = CompositeVideoClip([hook_bg, hook_clip], size=size)

    # Step 1: Create scene clips with Ken Burns effect
    scene_clips = []
    for i, (image_path, audio_path) in enumerate(zip(image_paths, audio_paths)):
        audio = AudioSegment.from_mp3(str(audio_path))
        duration = audio.duration_seconds

        clip = ImageClip(str(image_path)).with_duration(duration).resized(size)
        # Alternating zoom: even scenes zoom in, odd scenes zoom out
        if i % 2 == 0:
            clip = clip.with_effects(
                [vfx.Resize(lambda t, d=duration: 1 + ZOOM_FACTOR * (t / d))]
            )
        else:
            clip = clip.with_effects(
                [vfx.Resize(lambda t, d=duration: 1 + ZOOM_FACTOR * (1 - t / d))]
            )
        scene_clips.append(clip)

    # Step 2: Concatenate scenes with crossfade
    if len(scene_clips) > 1:
        timed_clips = [scene_clips[0]]
        cumulative = scene_clips[0].duration
        for clip in scene_clips[1:]:
            timed_clips.append(
                clip.with_start(cumulative - CROSSFADE_DURATION).with_effects(
                    [vfx.CrossFadeIn(CROSSFADE_DURATION)]
                )
            )
            cumulative += clip.duration - CROSSFADE_DURATION
        video = CompositeVideoClip(timed_clips, size=size)
    else:
        video = scene_clips[0]

    # Step 3: Concatenate audio and sync video duration
    audio_clips = [AudioFileClip(str(p)) for p in audio_paths]
    full_audio = concatenate_audioclips(audio_clips)

    # If hook frame exists, prepend it before the main video
    hook_duration = 0.0
    if hook_clip is not None:
        hook_duration = HOOK_DURATION
        video = video.with_start(hook_duration)
        video = CompositeVideoClip([hook_clip, video], size=size)
        # Pad audio with silence for the hook frame
        silence = AudioSegment.silent(duration=int(hook_duration * 1000))
        first_audio_raw = AudioSegment.from_mp3(str(audio_paths[0]))
        padded = silence + first_audio_raw
        import tempfile

        padded_path = Path(tempfile.mktemp(suffix=".mp3"))
        padded.export(str(padded_path), format="mp3")
        padded_audio_clip = AudioFileClip(str(padded_path))
        remaining_clips = [AudioFileClip(str(p)) for p in audio_paths[1:]]
        full_audio = concatenate_audioclips([padded_audio_clip] + remaining_clips)
        audio_clips = [padded_audio_clip] + remaining_clips
    video = video.with_duration(full_audio.duration)
    video = video.with_audio(full_audio)

    # Step 4: Overlay subtitles with semi-transparent background

    def make_subtitle_clip(text):
        kwargs = {
            "text": text,
            "font_size": SUBTITLE_FONT_SIZE,
            "color": SUBTITLE_COLOR,
            "bg_color": SUBTITLE_BG_COLOR,
            "stroke_color": SUBTITLE_STROKE_COLOR,
            "stroke_width": SUBTITLE_STROKE_WIDTH,
            "method": "caption",
            "size": (config.width - 200, None),
            "margin": SUBTITLE_MARGIN,
            "text_align": "center",
        }
        if cjk_font:
            kwargs["font"] = cjk_font
        return TextClip(**kwargs)

    subtitles = SubtitlesClip(
        str(srt_path),
        make_textclip=make_subtitle_clip,
        encoding="utf-8",
    )
    subtitles = subtitles.with_position(
        ("center", SUBTITLE_Y_POSITION), relative=True
    )

    layers = [video, subtitles]

    # Step 4.5: Overlay stat numbers per scene
    if stat_overlays:
        scene_start = hook_duration
        for idx, (audio_path, stat_text) in enumerate(
            zip(audio_paths, stat_overlays)
        ):
            if not stat_text:
                audio_seg = AudioSegment.from_mp3(str(audio_path))
                scene_start += audio_seg.duration_seconds
                if idx < len(audio_paths) - 1:
                    scene_start -= CROSSFADE_DURATION
                continue
            audio_seg = AudioSegment.from_mp3(str(audio_path))
            scene_dur = audio_seg.duration_seconds
            stat_kwargs = {
                "text": stat_text,
                "font_size": STAT_FONT_SIZE,
                "color": STAT_COLOR,
                "bg_color": STAT_BG_COLOR,
                "stroke_color": STAT_STROKE_COLOR,
                "stroke_width": STAT_STROKE_WIDTH,
                "method": "caption",
                "size": (config.width - 160, None),
                "margin": (30, 20),
                "text_align": "center",
            }
            if cjk_font:
                stat_kwargs["font"] = cjk_font
            # Display stat in the middle 60% of the scene
            fade_in_start = scene_start + scene_dur * 0.2
            stat_display_dur = scene_dur * 0.6
            stat_clip = (
                TextClip(**stat_kwargs)
                .with_duration(stat_display_dur)
                .with_start(fade_in_start)
                .with_position(("center", STAT_Y_POSITION), relative=True)
                .with_effects([vfx.CrossFadeIn(0.3)])
            )
            layers.append(stat_clip)
            scene_start += scene_dur
            if idx < len(audio_paths) - 1:
                scene_start -= CROSSFADE_DURATION

    # Step 4.6: Overlay title at the top of the screen
    if title:
        title_kwargs = {
            "text": title,
            "font_size": TITLE_FONT_SIZE,
            "color": TITLE_COLOR,
            "bg_color": TITLE_BG_COLOR,
            "stroke_color": SUBTITLE_STROKE_COLOR,
            "stroke_width": TITLE_STROKE_WIDTH,
            "method": "caption",
            "size": (config.width - 80, None),
            "margin": SUBTITLE_MARGIN,
            "text_align": "center",
        }
        if cjk_font:
            title_kwargs["font"] = cjk_font
        title_clip = (
            TextClip(**title_kwargs)
            .with_duration(video.duration)
            .with_position(("center", TITLE_Y_POSITION), relative=True)
        )
        layers.append(title_clip)

    final = CompositeVideoClip(layers, size=size)

    # Step 5: Write output
    final.write_videofile(
        str(output_path),
        fps=config.fps,
        codec="libx264",
        audio_codec="aac",
        preset="medium",
        threads=4,
    )

    # Cleanup
    for clip in audio_clips:
        clip.close()
    full_audio.close()
    video.close()
    final.close()

    return output_path
