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
SUBTITLE_Y_POSITION = 0.60  # 60% from top (slightly below center)
CROSSFADE_DURATION = 0.5


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
) -> Path:
    """Compose the final video from images, audio, and subtitles.

    Pipeline:
    1. Create ImageClip per scene with Ken Burns zoom effect
    2. Concatenate with crossfade transitions
    3. Concatenate audio track
    4. Overlay subtitles from SRT
    5. Write MP4 (H.264 + AAC)
    """
    size = (config.width, config.height)

    # Step 1: Create scene clips with Ken Burns effect
    scene_clips = []
    for image_path, audio_path in zip(image_paths, audio_paths):
        audio = AudioSegment.from_mp3(str(audio_path))
        duration = audio.duration_seconds

        clip = ImageClip(str(image_path)).with_duration(duration).resized(size)
        # Subtle zoom: 1.0x to 1.05x over the clip duration
        clip = clip.with_effects([vfx.Resize(lambda t, d=duration: 1 + 0.05 * (t / d))])
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
    video = video.with_duration(full_audio.duration)
    video = video.with_audio(full_audio)

    # Step 4: Overlay subtitles with semi-transparent background
    cjk_font = _find_cjk_font()

    def make_subtitle_clip(text):
        kwargs = {
            "text": text,
            "font_size": SUBTITLE_FONT_SIZE,
            "color": SUBTITLE_COLOR,
            "bg_color": SUBTITLE_BG_COLOR,
            "stroke_color": SUBTITLE_STROKE_COLOR,
            "stroke_width": SUBTITLE_STROKE_WIDTH,
            "method": "caption",
            "size": (config.width - 100, None),
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

    final = CompositeVideoClip([video, subtitles], size=size)

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
